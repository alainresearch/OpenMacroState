"""Policy-enforced execution and case-bundle output for built-in connectors."""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

from openmacrostate import __version__
from openmacrostate.api.v1.connector_types import (
    FetchRequest,
    FrozenArtifact,
    ObservationDraft,
    TransportResponse,
)
from openmacrostate.api.v1.errors import ContractError
from openmacrostate.api.v1.interfaces import Connector
from openmacrostate.api.v1.types import (
    SCHEMA_VERSION,
    Artifact,
    Observation,
    parse_timestamp,
    require_stable_id,
)
from openmacrostate.runtime.case import evaluate_case
from openmacrostate.runtime.http import HttpTransport, LiveHttpTransport, RecordedHttpTransport
from openmacrostate.runtime.jsonio import (
    canonical_json_bytes,
    sha256_bytes,
    write_bytes_atomic,
    write_json,
    write_jsonl,
    write_text_atomic,
)

MAX_CONNECTOR_BYTES = 4 * 1024 * 1024
CONNECTOR_CAPTURE_RULESET_VERSION = "openmacrostate-connector-capture/2"
_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?$")
_SPEC_FIELDS = {
    "schema_version",
    "plugin_id",
    "plugin_version",
    "api_version",
    "source_ids",
    "allowed_hosts",
    "required_secret_names",
    "license",
}
_LICENSE_FIELDS = {
    "license_id",
    "terms_url",
    "redistribution",
    "commercial_use",
    "attribution",
    "reviewed_at",
}
_COMPLETION_MARKER = ".openmacrostate-capture.json"
_INCOMPLETE_MARKER = ".openmacrostate-incomplete"


@dataclass(frozen=True, slots=True)
class ConnectorCapture:
    case_dir: Path
    case_id: str
    collection_id: str
    artifact_id: str
    observation_ids: tuple[str, ...]
    raw_sha256: str
    retrieved_at: str
    capture_mode: str
    recording_kind: str


def _as_string_tuple(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise ContractError(f"connector spec {field} must be an array of non-empty strings")
    result = tuple(value)
    if len(result) != len(set(result)):
        raise ContractError(f"connector spec {field} must not contain duplicates")
    return result


def validate_connector_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    if set(spec) != _SPEC_FIELDS:
        raise ContractError("connector spec has unknown or missing fields")
    if spec.get("schema_version") != SCHEMA_VERSION or spec.get("api_version") != "1":
        raise ContractError("connector spec has an unsupported schema or API version")
    plugin_id = require_stable_id(spec.get("plugin_id"), field="connector.plugin_id")
    plugin_version = spec.get("plugin_version")
    if (
        not isinstance(plugin_version, str)
        or re.fullmatch(r"\d+\.\d+\.\d+", plugin_version) is None
    ):
        raise ContractError("connector spec plugin_version must be MAJOR.MINOR.PATCH")
    source_ids = _as_string_tuple(spec.get("source_ids"), field="source_ids")
    if len(source_ids) != 1:
        raise ContractError("connector v1 capture requires exactly one source_id")
    for source_id in source_ids:
        require_stable_id(source_id, field="connector.source_ids")
    allowed_hosts = _as_string_tuple(spec.get("allowed_hosts"), field="allowed_hosts")
    for host in allowed_hosts:
        if host != host.lower() or _HOST.fullmatch(host) is None or host.endswith("."):
            raise ContractError("connector allowed_hosts must be exact lowercase DNS names")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ContractError("connector allowed_hosts must not contain IP literals")
    required_secrets = _as_string_tuple(
        spec.get("required_secret_names"), field="required_secret_names"
    )
    if required_secrets:
        raise ContractError("built-in connector v1 does not permit secrets")
    license_record = spec.get("license")
    if not isinstance(license_record, Mapping) or set(license_record) != _LICENSE_FIELDS:
        raise ContractError("connector spec license has unknown or missing fields")
    artifact_probe = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": "artifact:license:probe",
        "source_id": source_ids[0],
        "retrieved_at": str(license_record.get("reviewed_at")),
        "source_published_at": None,
        "sha256": "0" * 64,
        "byte_length": 0,
        "media_type": "application/octet-stream",
        "storage_uri": None,
        "license": dict(license_record),
    }
    Artifact.from_mapping(artifact_probe)
    return {
        **dict(spec),
        "source_ids": source_ids,
        "allowed_hosts": allowed_hosts,
        "required_secret_names": required_secrets,
        "license": dict(license_record),
        "plugin_id": plugin_id,
    }


def validate_fetch_request(request: FetchRequest, *, allowed_hosts: Iterable[str]) -> None:
    if request.method != "GET":
        raise ContractError("connector HTTP method must be GET")
    if request.accept not in {"application/json", "text/html"}:
        raise ContractError("connector Accept media type is not permitted")
    if (
        isinstance(request.max_bytes, bool)
        or not isinstance(request.max_bytes, int)
        or request.max_bytes < 1
        or request.max_bytes > MAX_CONNECTOR_BYTES
    ):
        raise ContractError("connector byte limit is invalid")
    try:
        parsed = urlsplit(request.url)
        port = parsed.port
    except ValueError as exc:
        raise ContractError("connector URL is malformed") from exc
    if parsed.scheme != "https":
        raise ContractError("connector URL must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ContractError("connector URL must not contain credentials")
    if parsed.hostname is None or parsed.hostname != parsed.hostname.lower():
        raise ContractError("connector URL must contain a lowercase DNS host")
    if parsed.hostname.endswith(".") or _HOST.fullmatch(parsed.hostname) is None:
        raise ContractError("connector URL host is not a canonical DNS name")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise ContractError("connector URL must not use an IP literal")
    if parsed.hostname not in frozenset(allowed_hosts):
        raise ContractError("connector URL host is absent from the exact allowlist")
    if port not in {None, 443}:
        raise ContractError("connector URL may use only the default HTTPS port")
    if parsed.fragment:
        raise ContractError("connector URL must not contain a fragment")
    if not parsed.path.startswith("/"):
        raise ContractError("connector URL path must be absolute")


def _media_type(headers: Mapping[str, str]) -> str:
    content_type = headers.get("content-type")
    if not isinstance(content_type, str) or not content_type:
        raise ContractError("connector response lacks Content-Type")
    return content_type.split(";", 1)[0].strip().lower()


def _freeze_response(
    response: TransportResponse,
    request: FetchRequest,
    *,
    source_id: str,
    allowed_hosts: tuple[str, ...],
    core_retrieved_at: str,
    capture_mode: str,
    recording_kind: str,
    source_authentication: str,
    transport_time_core_observed: bool,
) -> FrozenArtifact:
    if response.status_code != 200:
        raise ContractError(f"connector response status must be 200, got {response.status_code}")
    if response.final_url != request.url:
        raise ContractError("connector response redirected; redirects are forbidden")
    validate_fetch_request(
        FetchRequest(request.method, response.final_url, request.accept, request.max_bytes),
        allowed_hosts=allowed_hosts,
    )
    if len(response.body) > request.max_bytes or len(response.body) > MAX_CONNECTOR_BYTES:
        raise ContractError("connector response exceeds its byte limit")
    media_type = _media_type(response.headers)
    if media_type != request.accept:
        raise ContractError(
            f"connector response media type {media_type!r} does not match {request.accept!r}"
        )
    transport_time = parse_timestamp(response.retrieved_at, field="transport_retrieved_at_claim")
    core_time = parse_timestamp(core_retrieved_at, field="core_retrieved_at")
    if core_time < transport_time:
        raise ContractError("core retrieval time must not precede the transport time claim")
    digest = sha256_bytes(response.body)
    return FrozenArtifact(
        source_id=source_id,
        request_url=request.url,
        final_url=response.final_url,
        status_code=response.status_code,
        media_type=media_type,
        response_headers=MappingProxyType(dict(response.headers)),
        retrieved_at=core_retrieved_at,
        transport_retrieved_at_claim=response.retrieved_at,
        body=response.body,
        sha256=digest,
        byte_length=len(response.body),
        capture_mode=capture_mode,
        recording_kind=recording_kind,
        source_authentication=source_authentication,
        transport_time_core_observed=transport_time_core_observed,
    )


def _absolute_without_resolving(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _overlaps(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


def validate_new_output_directory(
    output_directory: str | Path, *, protected_paths: Iterable[str | Path] = ()
) -> Path:
    output = _absolute_without_resolving(Path(output_directory))
    if ".." in output.parts:
        raise ContractError("connector output path must not contain parent traversal")
    if output.name in {"", ".", ".."}:
        raise ContractError("connector output must name a new directory")
    if output.exists() or output.is_symlink():
        raise ContractError("connector output directory already exists; capture never overwrites")
    parent = output.parent
    if not parent.exists() or not parent.is_dir():
        raise ContractError("connector output parent must be an existing directory")
    current = parent
    while True:
        if current.is_symlink():
            raise ContractError("connector output path must not traverse a symbolic link")
        if current == current.parent:
            break
        current = current.parent
    resolved_output = output.resolve(strict=False)
    for protected_value in protected_paths:
        protected = Path(protected_value).resolve()
        if _overlaps(resolved_output, protected):
            raise ContractError("connector output must not overlap an input path")
    return output


def _observation_record(
    draft: ObservationDraft,
    *,
    source_id: str,
    artifact_id: str,
    retrieved_at: str,
) -> dict[str, Any]:
    require_stable_id(draft.series_id, field="observation.series_id")
    seed = {
        "series_id": draft.series_id,
        "observed_at": draft.observed_at,
        "released_at": draft.released_at,
        "value": draft.value,
        "unit": draft.unit,
        "artifact_id": artifact_id,
    }
    identifier = f"observation:sha256:{sha256_bytes(canonical_json_bytes(seed))}"
    extensions = dict(draft.extensions)
    extensions.update(
        {
            "vintage_time_basis": "conservative_retrieval_time",
            "ingestion_time_basis": (
                "capture_registration_uses_core_retrieval_time_no_independent_clock"
            ),
        }
    )
    record = {
        "schema_version": SCHEMA_VERSION,
        "observation_id": identifier,
        "series_id": draft.series_id,
        "source_id": source_id,
        "artifact_id": artifact_id,
        "observed_at": draft.observed_at,
        "released_at": draft.released_at,
        "vintage_at": retrieved_at,
        "ingested_at": retrieved_at,
        "value": draft.value,
        "unit": draft.unit,
        "quality": draft.quality,
        "extensions": extensions,
    }
    Observation.from_mapping(record)
    return record


def _write_capture_bundle(
    output: Path,
    *,
    spec: Mapping[str, Any],
    request: FetchRequest,
    artifact: FrozenArtifact,
    artifact_record: dict[str, Any],
    observations: list[dict[str, Any]],
    case_id: str,
    collection: dict[str, Any],
) -> None:
    try:
        output.mkdir(mode=0o700)
    except OSError as exc:
        raise ContractError(f"cannot reserve connector output directory: {exc}") from exc
    write_text_atomic(output / _INCOMPLETE_MARKER, "capture incomplete\n")
    write_bytes_atomic(output / artifact_record["storage_uri"], artifact.body)
    write_jsonl(output / "inputs" / "artifacts.jsonl", [artifact_record])
    write_jsonl(output / "inputs" / "observations.jsonl", observations)
    write_jsonl(output / "inputs" / "claims.jsonl", [])
    write_jsonl(output / "inputs" / "predictions.jsonl", [])
    write_json(output / "collection.json", collection)
    license_notice = f"""# Source data notice

The captured SOFR data is not licensed under this repository's Apache-2.0 code license.

License: {spec["license"]["license_id"]}
Terms: {spec["license"]["terms_url"]}
Attribution: © {artifact.retrieved_at[:4]} Federal Reserve Bank of New York.
Content from the New York Fed is subject to the Terms of Use at newyorkfed.org.

The SOFR Data is subject to the Terms of Use posted at newyorkfed.org. The New York
Fed is not responsible for publication of the SOFR Data by OpenMacroState, does not
sanction or endorse any particular republication, and has no liability for your use.

The normalized observations are an OpenMacroState transformation of the captured
response, not New York Fed-authored records.
OpenMacroState is not affiliated with the New York Fed. The New York Fed does not
sanction, endorse, or recommend any products or services offered by
OpenMacroState.
"""
    write_text_atomic(output / "LICENSES.md", license_notice)
    if artifact.source_authentication == "core_observed_https":
        description = (
            "A live HTTPS response observed by the OpenMacroState core; it is not "
            "an authenticated historical vintage."
        )
    else:
        description = (
            "Recorded bytes asserted by an unverified receipt; source identity, receipt time, "
            "and completeness are not authenticated by the OpenMacroState core."
        )
    case = {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "title": "FRBNY SOFR official-source capture",
        "description": description,
        "information_cutoff": artifact.retrieved_at,
        "fixture_kind": "licensed_public",
        "artifacts_file": "inputs/artifacts.jsonl",
        "observations_file": "inputs/observations.jsonl",
        "claims_file": "inputs/claims.jsonl",
        "predictions_file": "inputs/predictions.jsonl",
        "extensions": {
            "historical_evidence": False,
            "real_source_data": artifact.source_authentication == "core_observed_https",
            "complete_source_response": (
                artifact.source_authentication == "core_observed_https"
                and artifact.recording_kind == "complete_response"
            ),
            "recording_completeness_claim": artifact.recording_kind,
            "source_authentication": artifact.source_authentication,
            "availability_scope": "prospective_from_core_retrieval",
            "offline": artifact.capture_mode == "recorded",
            "checksums_file": "checksums/sha256.json",
            "licenses_file": "LICENSES.md",
            "connector_id": spec["plugin_id"],
            "connector_version": spec["plugin_version"],
            "capture_mode": artifact.capture_mode,
            "point_in_time_scope": "known_at_retrieval_not_at_value_date",
            "cutoff_policy": {
                "availability_mode": "prospective_capture",
                "eligible_when": (
                    "released_at <= information_cutoff AND vintage_at <= information_cutoff "
                    "AND ingested_at <= information_cutoff"
                ),
                "observed_at_is_not_sufficient": True,
                "post_cutoff_disposition": "quarantine",
                "transitive_claim_policy": (
                    "reject a claim if any evidence observation is not eligible"
                ),
            },
        },
    }
    write_json(output / "case.json", case)
    checksummed_paths = (
        "LICENSES.md",
        artifact_record["storage_uri"],
        "case.json",
        "collection.json",
        "inputs/artifacts.jsonl",
        "inputs/claims.jsonl",
        "inputs/observations.jsonl",
        "inputs/predictions.jsonl",
    )
    entries = []
    for relative in sorted(checksummed_paths):
        data = (output / relative).read_bytes()
        entries.append({"path": relative, "bytes": len(data), "sha256": sha256_bytes(data)})
    write_json(
        output / "checksums" / "sha256.json",
        {
            "schema_version": SCHEMA_VERSION,
            "algorithm": "sha256",
            "generated_for_case_id": case_id,
            "files": entries,
        },
    )
    evaluate_case(output)
    (output / _INCOMPLETE_MARKER).unlink()
    write_json(
        output / _COMPLETION_MARKER,
        {
            "schema_version": SCHEMA_VERSION,
            "generator": "openmacrostate.connector",
            "case_id": case_id,
            "collection_id": collection["collection_id"],
            "complete": True,
        },
    )


def run_connector(
    connector: Connector,
    request_record: Mapping[str, Any],
    transport: HttpTransport,
    output_directory: str | Path,
    *,
    protected_paths: Iterable[str | Path] = (),
    clock: Callable[[], str] | None = None,
) -> ConnectorCapture:
    """Execute one trusted built-in connector through the core policy boundary."""
    from openmacrostate.connectors import is_builtin_connector_instance

    if not is_builtin_connector_instance(connector):
        raise ContractError("connector must be an exact review-trusted built-in instance")
    if type(transport) is LiveHttpTransport:
        capture_mode = "live"
        recording_kind = "complete_response"
        source_authentication = "core_observed_https"
        transport_time_core_observed = True
    elif type(transport) is RecordedHttpTransport:
        capture_mode = "recorded"
        recording_kind = transport.recording_kind
        source_authentication = "unverified_recording"
        transport_time_core_observed = False
    else:
        raise ContractError(
            "connector transport must be an exact core-owned LiveHttpTransport "
            "or RecordedHttpTransport"
        )
    output = validate_new_output_directory(output_directory, protected_paths=protected_paths)
    spec = validate_connector_spec(connector.spec)
    connector_ruleset_version = connector.ruleset_version
    if not isinstance(connector_ruleset_version, str) or not connector_ruleset_version:
        raise ContractError("connector ruleset_version must be a non-empty string")
    plans = connector.plan(request_record)
    if len(plans) != 1:
        raise ContractError("connector v1 capture requires exactly one fetch plan")
    request = plans[0]
    validate_fetch_request(request, allowed_hosts=spec["allowed_hosts"])
    response = transport.fetch(request)
    core_retrieved_at = (
        clock()
        if clock is not None
        else datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )
    source_id = str(spec["source_ids"][0])
    artifact = _freeze_response(
        response,
        request,
        source_id=source_id,
        allowed_hosts=spec["allowed_hosts"],
        core_retrieved_at=core_retrieved_at,
        capture_mode=capture_mode,
        recording_kind=recording_kind,
        source_authentication=source_authentication,
        transport_time_core_observed=transport_time_core_observed,
    )
    drafts = tuple(connector.normalize(artifact))
    if any(not isinstance(draft, ObservationDraft) for draft in drafts):
        raise ContractError("connector normalize must yield ObservationDraft values")
    artifact_id = f"artifact:sha256:{artifact.sha256}"
    raw_suffix = ".json" if artifact.media_type == "application/json" else ".html"
    storage_uri = f"artifacts/{artifact.sha256}{raw_suffix}"
    artifact_extensions = {
        "connector_id": spec["plugin_id"],
        "connector_version": spec["plugin_version"],
        "request": {"method": request.method, "url": request.url, "accept": request.accept},
        "retrieval": {
            "capture_mode": artifact.capture_mode,
            "recording_completeness_claim": artifact.recording_kind,
            "final_url": artifact.final_url,
            "http_status": artifact.status_code,
            "response_headers": dict(artifact.response_headers),
            "hash_authority": "openmacrostate-core",
            "transport_retrieved_at_claim": artifact.transport_retrieved_at_claim,
            "transport_time_core_observed": artifact.transport_time_core_observed,
            "source_authentication": artifact.source_authentication,
        },
        "test_only_excerpt": artifact.recording_kind == "test_only_excerpt",
        "historical_version_authenticated": False,
        "source_published_at_basis": "unknown_for_exact_response_version",
        "transformation": "raw_response_preserved; normalized_observations_are_derived_records",
    }
    artifact_record = {
        "schema_version": SCHEMA_VERSION,
        "artifact_id": artifact_id,
        "source_id": source_id,
        "retrieved_at": artifact.retrieved_at,
        "source_published_at": None,
        "sha256": artifact.sha256,
        "byte_length": artifact.byte_length,
        "media_type": artifact.media_type,
        "storage_uri": storage_uri,
        "license": dict(spec["license"]),
        "extensions": artifact_extensions,
    }
    Artifact.from_mapping(artifact_record)
    observations = [
        _observation_record(
            draft,
            source_id=source_id,
            artifact_id=artifact_id,
            retrieved_at=artifact.retrieved_at,
        )
        for draft in drafts
    ]
    if len({record["observation_id"] for record in observations}) != len(observations):
        raise ContractError("connector produced duplicate normalized observations")
    observation_ids = [record["observation_id"] for record in observations]
    normalized_observations_sha256 = sha256_bytes(canonical_json_bytes(observations))
    capture_digest = sha256_bytes(
        canonical_json_bytes(
            {
                "capture_ruleset_version": CONNECTOR_CAPTURE_RULESET_VERSION,
                "engine_version": __version__,
                "wire_schema_version": SCHEMA_VERSION,
                "connector": {
                    "id": spec["plugin_id"],
                    "version": spec["plugin_version"],
                    "ruleset_version": connector_ruleset_version,
                },
                "request": {
                    "method": request.method,
                    "url": request.url,
                    "accept": request.accept,
                    "max_bytes": request.max_bytes,
                },
                "core_retrieved_at": artifact.retrieved_at,
                "transport": {
                    "capture_mode": artifact.capture_mode,
                    "recording_completeness_claim": artifact.recording_kind,
                    "transport_retrieved_at_claim": artifact.transport_retrieved_at_claim,
                    "transport_time_core_observed": artifact.transport_time_core_observed,
                    "source_authentication": artifact.source_authentication,
                    "final_url": artifact.final_url,
                    "status_code": artifact.status_code,
                    "headers": artifact.response_headers,
                    "media_type": artifact.media_type,
                    "byte_length": artifact.byte_length,
                },
                "artifact": {
                    "sha256": artifact.sha256,
                    "license": spec["license"],
                },
                "normalized_observations_sha256": normalized_observations_sha256,
                "observation_ids": observation_ids,
            }
        )
    )
    case_id = f"capture-frbny-sofr-{capture_digest[:16]}"
    collection_id = f"collection:frbny-sofr:{capture_digest[:16]}"
    collection = {
        "schema_version": SCHEMA_VERSION,
        "collection_id": collection_id,
        "case_id": case_id,
        "connector_id": spec["plugin_id"],
        "connector_version": spec["plugin_version"],
        "connector_ruleset_version": connector_ruleset_version,
        "capture_ruleset_version": CONNECTOR_CAPTURE_RULESET_VERSION,
        "engine_version": __version__,
        "capture_mode": artifact.capture_mode,
        "recording_completeness_claim": artifact.recording_kind,
        "source_authentication": artifact.source_authentication,
        "request": {"method": request.method, "url": request.url, "accept": request.accept},
        "retrieved_at": artifact.retrieved_at,
        "transport_retrieved_at_claim": artifact.transport_retrieved_at_claim,
        "transport_time_core_observed": artifact.transport_time_core_observed,
        "artifact_id": artifact_id,
        "observation_ids": observation_ids,
        "normalized_observations_sha256": normalized_observations_sha256,
        "raw_sha256": artifact.sha256,
        "byte_length": artifact.byte_length,
    }
    _write_capture_bundle(
        output,
        spec=spec,
        request=request,
        artifact=artifact,
        artifact_record=artifact_record,
        observations=observations,
        case_id=case_id,
        collection=collection,
    )
    return ConnectorCapture(
        case_dir=output.resolve(),
        case_id=case_id,
        collection_id=collection_id,
        artifact_id=artifact_id,
        observation_ids=tuple(record["observation_id"] for record in observations),
        raw_sha256=artifact.sha256,
        retrieved_at=artifact.retrieved_at,
        capture_mode=artifact.capture_mode,
        recording_kind=artifact.recording_kind,
    )
