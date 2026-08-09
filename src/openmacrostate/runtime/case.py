"""Deterministic, reveal-separated evaluation of OpenMacroState bundles."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any

from openmacrostate import __version__
from openmacrostate.api.v1.errors import CaseValidationError, ContractError
from openmacrostate.api.v1.types import (
    SCHEMA_VERSION,
    Artifact,
    Observation,
    parse_timestamp,
    require_fields,
    require_stable_id,
)
from openmacrostate.runtime.jsonio import (
    MAX_JSON_BYTES,
    canonical_json_bytes,
    load_json,
    load_json_bytes,
    load_jsonl_bytes,
    normalize_json_value,
    sha256_bytes,
)

RULESET_VERSION = "openmacrostate-replay/2"
CANONICALIZATION = "openmacrostate-canonical-json-v1"
_CASE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]+$")

_CASE_FIELDS = {
    "schema_version",
    "case_id",
    "title",
    "description",
    "information_cutoff",
    "fixture_kind",
    "artifacts_file",
    "observations_file",
    "claims_file",
    "predictions_file",
    "extensions",
}
_CLAIM_FIELDS = {
    "schema_version",
    "claim_id",
    "statement",
    "claim_type",
    "as_of",
    "information_cutoff",
    "evidence_ids",
    "status",
    "limitations",
    "alternative_explanations",
    "falsifiers",
    "extensions",
}
_PREDICTION_FIELDS = {
    "schema_version",
    "prediction_id",
    "statement",
    "probability",
    "made_at",
    "resolution_time",
    "outcome_id",
    "model_id",
    "rationale_claim_ids",
    "extensions",
}
_OUTCOME_FIELDS = {
    "schema_version",
    "outcome_id",
    "resolved_at",
    "value",
    "source_id",
    "artifact_id",
    "extensions",
}
_REVEAL_FIELDS = {
    "schema_version",
    "reveal_id",
    "case_id",
    "not_before",
    "outcomes_file",
    "artifacts_file",
    "checksums_file",
    "extensions",
}


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_json(item) for item in value)
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _reject_unknown_fields(
    record: Mapping[str, Any], allowed_fields: set[str], *, kind: str
) -> None:
    unknown = sorted(set(record) - allowed_fields)
    if unknown:
        raise CaseValidationError(f"{kind} has unknown fields: {', '.join(unknown)}")


def _require_mapping(value: Any, *, kind: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CaseValidationError(f"{kind} must be a JSON object")
    return value


def _require_non_empty_string(record: Mapping[str, Any], field: str, *, kind: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value:
        raise CaseValidationError(f"{kind}.{field} must be a non-empty string")
    return value


def _require_string_list(value: Any, *, field: str, unique: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise CaseValidationError(f"{field} must be an array of strings")
    if unique and len(value) != len(set(value)):
        raise CaseValidationError(f"{field} must not contain duplicates")
    return value


def _ensure_unique(records: list[dict[str, Any]], id_field: str, *, kind: str) -> None:
    seen: set[str] = set()
    for record in records:
        identifier = record.get(id_field)
        if not isinstance(identifier, str) or not identifier:
            raise CaseValidationError(f"{kind} has an invalid {id_field}")
        if identifier in seen:
            raise CaseValidationError(f"duplicate {kind} {id_field}: {identifier}")
        seen.add(identifier)


def _bundle_path(bundle_dir: Path, relative_path: str, *, field: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise CaseValidationError(f"{field} must be a non-empty relative path")
    relative = Path(relative_path)
    if relative.is_absolute():
        raise CaseValidationError(f"{field} must be relative to its bundle")
    root = bundle_dir.resolve()
    candidate = root / relative
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise CaseValidationError(f"{field} must not traverse a symbolic link")
    resolved = candidate.resolve()
    if resolved == root or root not in resolved.parents:
        raise CaseValidationError(f"{field} escapes its bundle: {relative_path}")
    return resolved


@dataclass(frozen=True, slots=True)
class _VerifiedBundle:
    files: tuple[Mapping[str, Any], ...]
    contents: Mapping[str, bytes]
    manifest_sha256: str


def _verify_bundle(
    bundle_dir: Path,
    manifest_name: str,
    *,
    expected_case_id: str,
    required_files: set[str],
) -> _VerifiedBundle:
    manifest_path = _bundle_path(bundle_dir, manifest_name, field="checksums_file")
    try:
        manifest_bytes = manifest_path.read_bytes()
    except OSError as exc:
        raise CaseValidationError(f"cannot read checksum manifest {manifest_path}: {exc}") from exc
    manifest = _require_mapping(
        load_json_bytes(manifest_bytes, source=str(manifest_path)), kind="checksum manifest"
    )
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise CaseValidationError("checksum manifest has an unsupported schema_version")
    if manifest.get("algorithm") != "sha256":
        raise CaseValidationError("checksum manifest algorithm must be sha256")
    declared_case_id = manifest.get("generated_for_case_id", manifest.get("case_id"))
    if declared_case_id != expected_case_id:
        raise CaseValidationError("checksum manifest case_id does not match the bundle")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise CaseValidationError("checksum manifest files must be a non-empty array")

    verified: list[Mapping[str, Any]] = []
    contents: dict[str, bytes] = {}
    seen_paths: set[str] = set()
    seen_resolved: set[Path] = set()
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise CaseValidationError(f"checksum entry {position} must be an object")
        relative_path = entry.get("path")
        if not isinstance(relative_path, str) or not relative_path:
            raise CaseValidationError(f"checksum entry {position} has no path")
        if relative_path in seen_paths:
            raise CaseValidationError(f"duplicate checksum path: {relative_path}")
        seen_paths.add(relative_path)
        path = _bundle_path(bundle_dir, relative_path, field="checksum path")
        if path in seen_resolved:
            raise CaseValidationError(f"duplicate resolved checksum path: {relative_path}")
        seen_resolved.add(path)
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise CaseValidationError(f"cannot read checksummed file {path}: {exc}") from exc
        if len(data) > MAX_JSON_BYTES:
            raise CaseValidationError(f"checksummed file is too large: {relative_path}")
        expected_bytes = entry.get("bytes")
        if isinstance(expected_bytes, bool) or not isinstance(expected_bytes, int):
            raise CaseValidationError(f"invalid byte length for {relative_path}")
        if len(data) != expected_bytes:
            raise CaseValidationError(
                f"byte length mismatch for {relative_path}: "
                f"expected {expected_bytes}, got {len(data)}"
            )
        expected_digest = entry.get("sha256")
        if (
            not isinstance(expected_digest, str)
            or len(expected_digest) != 64
            or any(character not in "0123456789abcdef" for character in expected_digest)
        ):
            raise CaseValidationError(f"invalid SHA-256 for {relative_path}")
        actual_digest = sha256_bytes(data)
        if actual_digest != expected_digest:
            raise CaseValidationError(
                f"SHA-256 mismatch for {relative_path}: "
                f"expected {expected_digest}, got {actual_digest}"
            )
        contents[relative_path] = data
        verified.append(
            _freeze_json(
                {
                    "path": relative_path,
                    "bytes": len(data),
                    "sha256": actual_digest,
                    "verified": True,
                }
            )
        )
    missing = sorted(required_files - seen_paths)
    if missing:
        raise CaseValidationError(f"checksum manifest omits required files: {', '.join(missing)}")
    return _VerifiedBundle(
        files=tuple(verified),
        contents=MappingProxyType(contents),
        manifest_sha256=sha256_bytes(manifest_bytes),
    )


def _parse_case(record: dict[str, Any]) -> dict[str, Any]:
    try:
        require_fields(
            record,
            (
                "schema_version",
                "case_id",
                "title",
                "description",
                "information_cutoff",
                "fixture_kind",
                "artifacts_file",
                "observations_file",
                "claims_file",
                "predictions_file",
            ),
            kind="case",
        )
        require_stable_id(record["case_id"], field="case_id")
        parse_timestamp(str(record["information_cutoff"]), field="information_cutoff")
    except ContractError as exc:
        raise CaseValidationError(str(exc)) from exc
    _reject_unknown_fields(record, _CASE_FIELDS, kind="case")
    if not _CASE_ID.fullmatch(str(record["case_id"])):
        raise CaseValidationError("case.case_id must use lowercase portable characters")
    for field in (
        "title",
        "description",
        "artifacts_file",
        "observations_file",
        "claims_file",
        "predictions_file",
    ):
        _require_non_empty_string(record, field, kind="case")
    if record["fixture_kind"] not in {"synthetic", "licensed_public", "restricted_reference"}:
        raise CaseValidationError(f"unsupported fixture_kind: {record['fixture_kind']!r}")
    extensions = record.get("extensions", {})
    if not isinstance(extensions, dict):
        raise CaseValidationError("case.extensions must be an object")
    cutoff_policy = extensions.get("cutoff_policy")
    if not isinstance(cutoff_policy, dict):
        raise CaseValidationError("case.extensions.cutoff_policy must be an object")
    if cutoff_policy.get("availability_mode") not in {
        "prospective_capture",
        "retrospective_authenticated",
    }:
        raise CaseValidationError(
            "cutoff_policy.availability_mode must be prospective_capture or "
            "retrospective_authenticated"
        )
    if not isinstance(extensions.get("checksums_file"), str):
        raise CaseValidationError("case.extensions.checksums_file is required")
    return record


def _parse_artifacts(
    records: list[dict[str, Any]],
    *,
    bundle_dir: Path,
    verified_contents: Mapping[str, bytes],
) -> dict[str, Artifact]:
    _ensure_unique(records, "artifact_id", kind="artifact")
    result: dict[str, Artifact] = {}
    for record in records:
        try:
            artifact = Artifact.from_mapping(record)
        except ContractError as exc:
            raise CaseValidationError(str(exc)) from exc
        if artifact.storage_uri is None:
            raise CaseValidationError(
                f"artifact {artifact.artifact_id} must preserve a storage_uri in a case bundle"
            )
        artifact_path = _bundle_path(bundle_dir, artifact.storage_uri, field="artifact.storage_uri")
        relative_path = artifact_path.relative_to(bundle_dir.resolve()).as_posix()
        data = verified_contents.get(relative_path)
        if data is None:
            raise CaseValidationError(
                f"artifact {artifact.artifact_id} storage_uri is absent from the checksum manifest"
            )
        if len(data) != artifact.byte_length or sha256_bytes(data) != artifact.sha256:
            raise CaseValidationError(
                f"artifact {artifact.artifact_id} metadata does not match its preserved bytes"
            )
        result[artifact.artifact_id] = artifact
    return result


def _validate_claim(record: dict[str, Any]) -> None:
    try:
        require_fields(
            record,
            (
                "schema_version",
                "claim_id",
                "statement",
                "claim_type",
                "as_of",
                "information_cutoff",
                "evidence_ids",
                "limitations",
                "falsifiers",
            ),
            kind="claim",
        )
        require_stable_id(record["claim_id"], field="claim_id")
        parse_timestamp(str(record["as_of"]), field="claim.as_of")
        parse_timestamp(str(record["information_cutoff"]), field="claim.information_cutoff")
    except ContractError as exc:
        raise CaseValidationError(str(exc)) from exc
    _reject_unknown_fields(record, _CLAIM_FIELDS, kind="claim")
    _require_non_empty_string(record, "statement", kind="claim")
    if record["claim_type"] not in {"fact", "inference", "assumption", "unknown"}:
        raise CaseValidationError(f"claim {record['claim_id']} has invalid claim_type")
    if "status" in record and record["status"] not in {
        "candidate",
        "supported",
        "weakened",
        "invalidated",
        "unknown",
    }:
        raise CaseValidationError(f"claim {record['claim_id']} has invalid status")
    evidence_ids = _require_string_list(
        record["evidence_ids"], field="claim.evidence_ids", unique=True
    )
    if record["claim_type"] in {"fact", "inference"} and not evidence_ids:
        raise CaseValidationError(f"claim {record['claim_id']} requires evidence")
    for identifier in evidence_ids:
        try:
            require_stable_id(identifier, field="claim.evidence_ids")
        except ContractError as exc:
            raise CaseValidationError(str(exc)) from exc
    _require_string_list(record["limitations"], field="claim.limitations")
    if "alternative_explanations" in record:
        _require_string_list(
            record["alternative_explanations"], field="claim.alternative_explanations"
        )
    if not isinstance(record["falsifiers"], list):
        raise CaseValidationError("claim.falsifiers must be an array")
    for falsifier in record["falsifiers"]:
        if not isinstance(falsifier, dict):
            raise CaseValidationError("claim.falsifiers entries must be objects")
        _reject_unknown_fields(
            falsifier, {"description", "observable", "window"}, kind="claim.falsifier"
        )
        _require_non_empty_string(falsifier, "description", kind="claim.falsifier")
        _require_non_empty_string(falsifier, "observable", kind="claim.falsifier")
        if "window" in falsifier and falsifier["window"] is not None:
            _require_non_empty_string(falsifier, "window", kind="claim.falsifier")
    if "extensions" in record and not isinstance(record["extensions"], dict):
        raise CaseValidationError("claim.extensions must be an object")


def _validate_prediction(record: dict[str, Any]) -> None:
    try:
        require_fields(
            record,
            (
                "schema_version",
                "prediction_id",
                "statement",
                "probability",
                "made_at",
                "resolution_time",
                "outcome_id",
            ),
            kind="prediction",
        )
        require_stable_id(record["prediction_id"], field="prediction_id")
        require_stable_id(record["outcome_id"], field="outcome_id")
        made_at = parse_timestamp(str(record["made_at"]), field="prediction.made_at")
        resolution_time = parse_timestamp(
            str(record["resolution_time"]), field="prediction.resolution_time"
        )
    except ContractError as exc:
        raise CaseValidationError(str(exc)) from exc
    _reject_unknown_fields(record, _PREDICTION_FIELDS, kind="prediction")
    _require_non_empty_string(record, "statement", kind="prediction")
    probability = record["probability"]
    if (
        isinstance(probability, bool)
        or not isinstance(probability, int | float)
        or not math.isfinite(float(probability))
    ):
        raise CaseValidationError(
            f"prediction {record['prediction_id']} probability must be finite and numeric"
        )
    if not 0 <= float(probability) <= 1:
        raise CaseValidationError(
            f"prediction {record['prediction_id']} probability must be in [0, 1]"
        )
    if resolution_time <= made_at:
        raise CaseValidationError(
            f"prediction {record['prediction_id']} resolution_time must follow made_at"
        )
    if "model_id" in record and record["model_id"] is not None:
        try:
            require_stable_id(record["model_id"], field="model_id")
        except ContractError as exc:
            raise CaseValidationError(str(exc)) from exc
    if "rationale_claim_ids" in record:
        rationale_ids = _require_string_list(
            record["rationale_claim_ids"],
            field="prediction.rationale_claim_ids",
            unique=True,
        )
        for identifier in rationale_ids:
            try:
                require_stable_id(identifier, field="prediction.rationale_claim_ids")
            except ContractError as exc:
                raise CaseValidationError(str(exc)) from exc
    if "extensions" in record and not isinstance(record["extensions"], dict):
        raise CaseValidationError("prediction.extensions must be an object")


@dataclass(frozen=True, slots=True)
class CaseEvaluation:
    """A deeply frozen pre-reveal result; no outcome path or bytes are retained."""

    case_dir: Path
    case: Mapping[str, Any]
    artifacts: tuple[Mapping[str, Any], ...]
    accepted_observations: tuple[Mapping[str, Any], ...]
    quarantined_observations: tuple[Mapping[str, Any], ...]
    accepted_claims: tuple[Mapping[str, Any], ...]
    rejected_claims: tuple[Mapping[str, Any], ...]
    accepted_predictions: tuple[Mapping[str, Any], ...]
    rejected_predictions: tuple[Mapping[str, Any], ...]
    verified_files: tuple[Mapping[str, Any], ...]
    research_manifest_sha256: str
    frozen_at: str
    sealed_content_sha256: str = ""

    def __post_init__(self) -> None:
        computed = sha256_bytes(canonical_json_bytes(self._audit_manifest()))
        if self.sealed_content_sha256 and self.sealed_content_sha256 != computed:
            raise CaseValidationError("CaseEvaluation content does not match its sealed root")
        object.__setattr__(self, "sealed_content_sha256", computed)

    @property
    def case_id(self) -> str:
        return str(self.case["case_id"])

    @property
    def information_cutoff(self) -> str:
        return str(self.case["information_cutoff"])

    def _audit_manifest(self) -> dict[str, Any]:
        """Return the validator-only state, including excluded plaintext."""
        return normalize_json_value(
            {
                "ruleset": RULESET_VERSION,
                "canonicalization": CANONICALIZATION,
                "engine_version": __version__,
                "wire_schema_version": SCHEMA_VERSION,
                "case": self.case,
                "research_integrity": {
                    "manifest_sha256": self.research_manifest_sha256,
                    "files": self.verified_files,
                },
                "artifacts": self.artifacts,
                "accepted_observations": self.accepted_observations,
                "quarantined_observations": self.quarantined_observations,
                "accepted_claims": self.accepted_claims,
                "rejected_claims": self.rejected_claims,
                "accepted_predictions": self.accepted_predictions,
                "rejected_predictions": self.rejected_predictions,
            }
        )

    def _eligible_manifest(self) -> dict[str, Any]:
        """Return the only plaintext research view safe for downstream analysis."""
        eligible_artifact_ids = {
            str(record["artifact_id"]) for record in self.accepted_observations
        }
        eligible_artifacts = tuple(
            record
            for record in self.artifacts
            if str(record["artifact_id"]) in eligible_artifact_ids
        )
        return normalize_json_value(
            {
                "ruleset": RULESET_VERSION,
                "canonicalization": CANONICALIZATION,
                "engine_version": __version__,
                "wire_schema_version": SCHEMA_VERSION,
                "case": self.case,
                "research_integrity": {
                    "manifest_sha256": self.research_manifest_sha256,
                },
                "artifacts": eligible_artifacts,
                "observations": self.accepted_observations,
                "claims": self.accepted_claims,
                "predictions": self.accepted_predictions,
                "exclusion_counts": {
                    "observations": len(self.quarantined_observations),
                    "claims": len(self.rejected_claims),
                    "predictions": len(self.rejected_predictions),
                },
            }
        )

    def _verify_seal(self) -> None:
        digest = sha256_bytes(canonical_json_bytes(self._audit_manifest()))
        if digest != self.sealed_content_sha256:
            raise CaseValidationError("CaseEvaluation changed after it was sealed")

    def snapshot(self) -> dict[str, Any]:
        self._verify_seal()
        eligible_content = self._eligible_manifest()
        digest = sha256_bytes(canonical_json_bytes(eligible_content))
        return {
            "schema_version": SCHEMA_VERSION,
            "snapshot_id": f"snapshot:{self.case_id}:{digest[:16]}",
            "case_id": self.case_id,
            "information_cutoff": self.information_cutoff,
            "created_at": self.frozen_at,
            "observation_ids": [record["observation_id"] for record in self.accepted_observations],
            "content_sha256": digest,
            "extensions": {
                "replay_as_of": self.information_cutoff,
                "content_hash_scope": "extensions.eligible_content",
                "canonicalization": CANONICALIZATION,
                "ruleset": RULESET_VERSION,
                "audit_sha256": self.sealed_content_sha256,
                "audit_hash_scope": "validator-held full audit state; excluded plaintext omitted",
                "accepted_claim_ids": [record["claim_id"] for record in self.accepted_claims],
                "accepted_prediction_ids": [
                    record["prediction_id"] for record in self.accepted_predictions
                ],
                "eligible_content": eligible_content,
            },
        }

    def summary(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "information_cutoff": self.information_cutoff,
            "fixture_kind": self.case["fixture_kind"],
            "historical_evidence": bool(
                self.case.get("extensions", {}).get("historical_evidence", False)
            ),
            "artifacts": len(self.artifacts),
            "accepted_observations": len(self.accepted_observations),
            "quarantined_observations": len(self.quarantined_observations),
            "accepted_claims": len(self.accepted_claims),
            "rejected_claims": len(self.rejected_claims),
            "accepted_predictions": len(self.accepted_predictions),
            "rejected_predictions": len(self.rejected_predictions),
            "verified_research_files": len(self.verified_files),
        }


def evaluate_case(case_directory: str | Path) -> CaseEvaluation:
    """Verify and freeze research inputs without reading any reveal bundle."""
    case_dir = Path(case_directory).resolve()
    if not case_dir.is_dir():
        raise CaseValidationError(f"case directory does not exist: {case_dir}")
    case_path = _bundle_path(case_dir, "case.json", field="case file")
    initial_case = _parse_case(_require_mapping(load_json(case_path), kind="case"))
    manifest_name = str(initial_case["extensions"]["checksums_file"])
    required_files = {
        "case.json",
        str(initial_case["artifacts_file"]),
        str(initial_case["observations_file"]),
        str(initial_case["claims_file"]),
        str(initial_case["predictions_file"]),
    }
    verified_bundle = _verify_bundle(
        case_dir,
        manifest_name,
        expected_case_id=str(initial_case["case_id"]),
        required_files=required_files,
    )
    verified_case = _parse_case(
        _require_mapping(
            load_json_bytes(verified_bundle.contents["case.json"], source="case.json"),
            kind="case",
        )
    )
    if verified_case != initial_case:
        raise CaseValidationError("case.json changed while its bundle was being verified")
    cutoff = parse_timestamp(str(verified_case["information_cutoff"]), field="information_cutoff")
    mode = str(verified_case["extensions"]["cutoff_policy"]["availability_mode"])

    artifacts_name = str(verified_case["artifacts_file"])
    raw_artifacts = load_jsonl_bytes(
        verified_bundle.contents[artifacts_name], source=artifacts_name
    )
    artifact_by_id = _parse_artifacts(
        raw_artifacts, bundle_dir=case_dir, verified_contents=verified_bundle.contents
    )

    observations_name = str(verified_case["observations_file"])
    raw_observations = load_jsonl_bytes(
        verified_bundle.contents[observations_name], source=observations_name
    )
    _ensure_unique(raw_observations, "observation_id", kind="observation")
    observation_by_id: dict[str, Observation] = {}
    raw_observation_by_id: dict[str, dict[str, Any]] = {}
    for raw in raw_observations:
        try:
            observation = Observation.from_mapping(raw)
        except ContractError as exc:
            raise CaseValidationError(str(exc)) from exc
        artifact = artifact_by_id.get(observation.artifact_id)
        if artifact is None:
            raise CaseValidationError(
                f"observation {observation.observation_id} references missing artifact "
                f"{observation.artifact_id}"
            )
        if observation.source_id != artifact.source_id:
            raise CaseValidationError(
                f"observation {observation.observation_id} source_id does not match its artifact"
            )
        if observation.ingested_at < artifact.retrieved_at:
            raise CaseValidationError(
                f"observation {observation.observation_id} was ingested before "
                "its artifact retrieval"
            )
        observation_by_id[observation.observation_id] = observation
        raw_observation_by_id[observation.observation_id] = raw

    def cutoff_reasons(observation: Observation, at: datetime) -> tuple[str, ...]:
        require_ingested = mode == "prospective_capture"
        reasons = list(observation.cutoff_reasons(at, require_ingested_by_cutoff=require_ingested))
        if mode == "retrospective_authenticated" and observation.ingested_at > at:
            artifact = artifact_by_id[observation.artifact_id]
            if not artifact.authenticates_historical_version(
                at, allow_synthetic_fixture=verified_case["fixture_kind"] == "synthetic"
            ):
                reasons.append("post_cutoff_ingestion_without_availability_proof")
        return tuple(reasons)

    accepted_observations: list[dict[str, Any]] = []
    quarantined_observations: list[dict[str, Any]] = []
    for raw in raw_observations:
        observation = observation_by_id[str(raw["observation_id"])]
        reasons = cutoff_reasons(observation, cutoff)
        if reasons:
            quarantined_observations.append(
                {
                    **raw,
                    "quarantine": {"primary_reason": reasons[0], "reasons": list(reasons)},
                }
            )
        else:
            accepted_observations.append(raw)

    claims_name = str(verified_case["claims_file"])
    raw_claims = load_jsonl_bytes(verified_bundle.contents[claims_name], source=claims_name)
    _ensure_unique(raw_claims, "claim_id", kind="claim")
    accepted_claims: list[dict[str, Any]] = []
    rejected_claims: list[dict[str, Any]] = []
    accepted_claim_ids: set[str] = set()
    all_claim_ids = {str(record["claim_id"]) for record in raw_claims}
    claim_by_id = {str(record["claim_id"]): record for record in raw_claims}
    all_observation_ids = set(observation_by_id)
    for record in raw_claims:
        _validate_claim(record)
        reasons: list[str] = []
        claim_cutoff = parse_timestamp(
            str(record["information_cutoff"]), field="claim.information_cutoff"
        )
        claim_as_of = parse_timestamp(str(record["as_of"]), field="claim.as_of")
        if claim_cutoff > cutoff:
            reasons.append("claim_information_cutoff_after_case_cutoff")
        if claim_as_of > claim_cutoff:
            reasons.append("claim_as_of_after_information_cutoff")
        evidence_ids = [str(identifier) for identifier in record["evidence_ids"]]
        unknown_evidence = sorted(set(evidence_ids) - all_observation_ids)
        ineligible_evidence = sorted(
            identifier
            for identifier in set(evidence_ids) - set(unknown_evidence)
            if cutoff_reasons(observation_by_id[identifier], claim_cutoff)
        )
        if unknown_evidence:
            reasons.append("unknown_evidence")
        if ineligible_evidence:
            reasons.append("ineligible_evidence_at_claim_cutoff")
        if reasons:
            rejected_claims.append(
                {
                    **record,
                    "rejection": {
                        "reasons": reasons,
                        "unknown_evidence_ids": unknown_evidence,
                        "ineligible_evidence_ids": ineligible_evidence,
                    },
                }
            )
        else:
            accepted_claim_ids.add(str(record["claim_id"]))
            accepted_claims.append(record)

    predictions_name = str(verified_case["predictions_file"])
    raw_predictions = load_jsonl_bytes(
        verified_bundle.contents[predictions_name], source=predictions_name
    )
    _ensure_unique(raw_predictions, "prediction_id", kind="prediction")
    accepted_predictions: list[dict[str, Any]] = []
    rejected_predictions: list[dict[str, Any]] = []
    for record in raw_predictions:
        _validate_prediction(record)
        reasons: list[str] = []
        made_at = parse_timestamp(str(record["made_at"]), field="prediction.made_at")
        if made_at > cutoff:
            reasons.append("prediction_made_after_information_cutoff")
        rationale_ids = record.get("rationale_claim_ids", [])
        if not isinstance(rationale_ids, list):
            raise CaseValidationError(
                f"prediction {record['prediction_id']} rationale_claim_ids must be an array"
            )
        rationale_set = set(map(str, rationale_ids))
        unknown_claims = sorted(rationale_set - all_claim_ids)
        rejected_rationales = sorted(rationale_set - accepted_claim_ids - set(unknown_claims))
        late_rationales = sorted(
            identifier
            for identifier in rationale_set & accepted_claim_ids
            if max(
                parse_timestamp(
                    str(claim_by_id[identifier]["information_cutoff"]),
                    field="claim.information_cutoff",
                ),
                parse_timestamp(
                    str(claim_by_id[identifier]["as_of"]),
                    field="claim.as_of",
                ),
            )
            > made_at
        )
        extensions = record.get("extensions", {})
        evidence_ids = extensions.get("evidence_ids", []) if isinstance(extensions, dict) else []
        if not isinstance(evidence_ids, list):
            raise CaseValidationError(
                f"prediction {record['prediction_id']} extensions.evidence_ids must be an array"
            )
        evidence_set = set(map(str, evidence_ids))
        unknown_evidence = sorted(evidence_set - all_observation_ids)
        ineligible_evidence = sorted(
            identifier
            for identifier in evidence_set - set(unknown_evidence)
            if cutoff_reasons(observation_by_id[identifier], made_at)
        )
        if unknown_claims:
            reasons.append("unknown_rationale_claim")
        if rejected_rationales:
            reasons.append("rejected_rationale_claim")
        if late_rationales:
            reasons.append("rationale_claim_not_available_at_prediction_time")
        if unknown_evidence:
            reasons.append("unknown_evidence")
        if ineligible_evidence:
            reasons.append("ineligible_evidence_at_prediction_time")
        if reasons:
            rejected_predictions.append(
                {
                    **record,
                    "rejection": {
                        "reasons": reasons,
                        "unknown_claim_ids": unknown_claims,
                        "rejected_claim_ids": rejected_rationales,
                        "late_claim_ids": late_rationales,
                        "unknown_evidence_ids": unknown_evidence,
                        "ineligible_evidence_ids": ineligible_evidence,
                    },
                }
            )
        else:
            accepted_predictions.append(record)

    return CaseEvaluation(
        case_dir=case_dir,
        case=_freeze_json(verified_case),
        artifacts=tuple(_freeze_json(record) for record in raw_artifacts),
        accepted_observations=tuple(_freeze_json(record) for record in accepted_observations),
        quarantined_observations=tuple(_freeze_json(record) for record in quarantined_observations),
        accepted_claims=tuple(_freeze_json(record) for record in accepted_claims),
        rejected_claims=tuple(_freeze_json(record) for record in rejected_claims),
        accepted_predictions=tuple(_freeze_json(record) for record in accepted_predictions),
        rejected_predictions=tuple(_freeze_json(record) for record in rejected_predictions),
        verified_files=verified_bundle.files,
        research_manifest_sha256=verified_bundle.manifest_sha256,
        frozen_at=_utc_now(),
    )


def _parse_reveal(record: dict[str, Any], *, expected_case_id: str) -> dict[str, Any]:
    try:
        require_fields(
            record,
            (
                "schema_version",
                "reveal_id",
                "case_id",
                "not_before",
                "outcomes_file",
                "artifacts_file",
                "checksums_file",
            ),
            kind="reveal",
        )
        require_stable_id(record["reveal_id"], field="reveal_id")
        require_stable_id(record["case_id"], field="case_id")
        parse_timestamp(str(record["not_before"]), field="reveal.not_before")
    except ContractError as exc:
        raise CaseValidationError(str(exc)) from exc
    _reject_unknown_fields(record, _REVEAL_FIELDS, kind="reveal")
    if not _CASE_ID.fullmatch(str(record["reveal_id"])):
        raise CaseValidationError("reveal.reveal_id must use lowercase portable characters")
    if not _CASE_ID.fullmatch(str(record["case_id"])):
        raise CaseValidationError("reveal.case_id must use lowercase portable characters")
    if record["case_id"] != expected_case_id:
        raise CaseValidationError("reveal bundle belongs to a different case")
    for field in ("outcomes_file", "artifacts_file", "checksums_file"):
        _require_non_empty_string(record, field, kind="reveal")
    if "extensions" in record and not isinstance(record["extensions"], dict):
        raise CaseValidationError("reveal.extensions must be an object")
    return record


def score_case(
    evaluation: CaseEvaluation,
    reveal_directory: str | Path,
    *,
    evaluation_at: str,
) -> dict[str, Any]:
    """Open a separately supplied reveal bundle only after its time gate."""
    evaluation._verify_seal()
    try:
        evaluation_time = parse_timestamp(evaluation_at, field="evaluation_at")
    except ContractError as exc:
        raise CaseValidationError(str(exc)) from exc
    if evaluation_time > datetime.now(timezone.utc):
        raise CaseValidationError("evaluation_at cannot be in the future")
    reveal_dir = Path(reveal_directory).resolve()
    if not reveal_dir.is_dir():
        raise CaseValidationError(f"reveal directory does not exist: {reveal_dir}")
    if reveal_dir == evaluation.case_dir:
        raise CaseValidationError("research and reveal bundles must be separate directories")

    reveal_path = _bundle_path(reveal_dir, "reveal.json", field="reveal file")
    initial_reveal = _parse_reveal(
        _require_mapping(load_json(reveal_path), kind="reveal"),
        expected_case_id=evaluation.case_id,
    )
    not_before = parse_timestamp(str(initial_reveal["not_before"]), field="reveal.not_before")
    if evaluation_time < not_before:
        raise CaseValidationError(
            "reveal is embargoed: evaluation_at is earlier than reveal.not_before"
        )

    manifest_name = str(initial_reveal["checksums_file"])
    required_files = {
        "reveal.json",
        str(initial_reveal["artifacts_file"]),
        str(initial_reveal["outcomes_file"]),
    }
    verified_bundle = _verify_bundle(
        reveal_dir,
        manifest_name,
        expected_case_id=evaluation.case_id,
        required_files=required_files,
    )
    verified_reveal = _parse_reveal(
        _require_mapping(
            load_json_bytes(verified_bundle.contents["reveal.json"], source="reveal.json"),
            kind="reveal",
        ),
        expected_case_id=evaluation.case_id,
    )
    if verified_reveal != initial_reveal:
        raise CaseValidationError("reveal.json changed while its bundle was being verified")

    artifacts_name = str(verified_reveal["artifacts_file"])
    reveal_artifacts = load_jsonl_bytes(
        verified_bundle.contents[artifacts_name], source=artifacts_name
    )
    artifact_by_id = _parse_artifacts(
        reveal_artifacts, bundle_dir=reveal_dir, verified_contents=verified_bundle.contents
    )
    outcomes_name = str(verified_reveal["outcomes_file"])
    outcomes = load_jsonl_bytes(verified_bundle.contents[outcomes_name], source=outcomes_name)
    _ensure_unique(outcomes, "outcome_id", kind="outcome")
    outcome_by_id: dict[str, dict[str, Any]] = {}
    for record in outcomes:
        try:
            require_fields(
                record,
                (
                    "schema_version",
                    "outcome_id",
                    "resolved_at",
                    "value",
                    "source_id",
                    "artifact_id",
                ),
                kind="outcome",
            )
            require_stable_id(record["outcome_id"], field="outcome_id")
            resolved_at = parse_timestamp(str(record["resolved_at"]), field="outcome.resolved_at")
        except ContractError as exc:
            raise CaseValidationError(str(exc)) from exc
        _reject_unknown_fields(record, _OUTCOME_FIELDS, kind="outcome")
        for field in ("source_id", "artifact_id"):
            try:
                require_stable_id(record[field], field=f"outcome.{field}")
            except ContractError as exc:
                raise CaseValidationError(str(exc)) from exc
        outcome_value = record["value"]
        if not isinstance(outcome_value, (int, float, str, bool, type(None))) or (
            isinstance(outcome_value, float) and not math.isfinite(outcome_value)
        ):
            raise CaseValidationError("outcome.value must be a finite JSON scalar")
        if resolved_at > evaluation_time:
            raise CaseValidationError(
                f"outcome {record['outcome_id']} was unresolved at evaluation_at"
            )
        artifact_id = str(record["artifact_id"])
        artifact = artifact_by_id.get(artifact_id)
        if artifact is None:
            raise CaseValidationError(
                f"outcome {record['outcome_id']} references missing artifact {artifact_id}"
            )
        if record["source_id"] != artifact.source_id:
            raise CaseValidationError(
                f"outcome {record['outcome_id']} source_id does not match its artifact"
            )
        if artifact.source_published_at is None:
            raise CaseValidationError(
                f"outcome {record['outcome_id']} artifact lacks source_published_at"
            )
        if artifact.source_published_at > evaluation_time:
            raise CaseValidationError(
                f"outcome {record['outcome_id']} artifact was published after evaluation_at"
            )
        if (
            artifact.retrieved_at > evaluation_time
            and not artifact.authenticates_historical_version(
                evaluation_time,
                allow_synthetic_fixture=verified_reveal.get("extensions", {}).get("fixture_kind")
                == "synthetic",
            )
        ):
            raise CaseValidationError(
                f"outcome {record['outcome_id']} artifact was retrieved after evaluation_at "
                "without a bound availability proof"
            )
        if "extensions" in record and not isinstance(record["extensions"], dict):
            raise CaseValidationError("outcome.extensions must be an object")
        outcome_by_id[str(record["outcome_id"])] = record

    scores: list[dict[str, Any]] = []
    for prediction in evaluation.accepted_predictions:
        outcome_id = str(prediction["outcome_id"])
        outcome = outcome_by_id.get(outcome_id)
        if outcome is None:
            raise CaseValidationError(
                f"prediction {prediction['prediction_id']} references missing outcome {outcome_id}"
            )
        resolved_at = parse_timestamp(str(outcome["resolved_at"]), field="outcome.resolved_at")
        made_at = parse_timestamp(str(prediction["made_at"]), field="prediction.made_at")
        resolution_time = parse_timestamp(
            str(prediction["resolution_time"]), field="prediction.resolution_time"
        )
        if resolved_at <= made_at:
            raise CaseValidationError(f"outcome {outcome_id} resolved before prediction was made")
        if resolved_at > resolution_time:
            raise CaseValidationError(f"outcome {outcome_id} resolved after prediction deadline")
        outcome_value = outcome["value"]
        if isinstance(outcome_value, bool):
            outcome_value = int(outcome_value)
        if outcome_value not in (0, 1):
            raise CaseValidationError(
                f"outcome {outcome_id} must be binary for probability scoring"
            )
        probability = float(prediction["probability"])
        brier = (probability - outcome_value) ** 2
        if (outcome_value == 1 and probability == 0) or (outcome_value == 0 and probability == 1):
            log_loss: float | None = None
        elif outcome_value == 1:
            log_loss = -math.log(probability)
        else:
            log_loss = -math.log1p(-probability)
        scores.append(
            {
                "prediction_id": prediction["prediction_id"],
                "outcome_id": outcome_id,
                "probability": probability,
                "outcome_value": outcome_value,
                "brier_score": brier,
                "binary_log_loss": log_loss,
                "binary_log_loss_is_infinite": log_loss is None,
                "resolved_at": outcome["resolved_at"],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": evaluation.case_id,
        "phase": "post_reveal_scoring",
        "evaluation_at": evaluation_at,
        "reveal": {
            "reveal_id": verified_reveal["reveal_id"],
            "not_before": verified_reveal["not_before"],
            "manifest_sha256": verified_bundle.manifest_sha256,
            "verified_files": list(verified_bundle.files),
        },
        "scores": scores,
    }
