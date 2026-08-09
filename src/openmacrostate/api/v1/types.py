"""Small public value objects used by plugin API v1."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from openmacrostate.api.v1.errors import ContractError

SCHEMA_VERSION = "1.0.0"
_RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{1,255}$")
_ABSOLUTE_URI = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:[^\s]+$")
_OBSERVATION_FIELDS = {
    "schema_version",
    "observation_id",
    "series_id",
    "source_id",
    "artifact_id",
    "observed_at",
    "released_at",
    "vintage_at",
    "ingested_at",
    "value",
    "unit",
    "revision_of",
    "quality",
    "extensions",
}
_ARTIFACT_FIELDS = {
    "schema_version",
    "artifact_id",
    "source_id",
    "retrieved_at",
    "source_published_at",
    "sha256",
    "byte_length",
    "media_type",
    "storage_uri",
    "license",
    "extensions",
}
_LICENSE_FIELDS = {
    "license_id",
    "terms_url",
    "redistribution",
    "commercial_use",
    "attribution",
    "reviewed_at",
}


def parse_timestamp(value: str, *, field: str = "timestamp") -> datetime:
    """Parse an RFC3339 timestamp and require an explicit timezone."""
    if not isinstance(value, str) or not _RFC3339.fullmatch(value):
        raise ContractError(f"{field} must be a non-empty RFC3339 string")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ContractError(f"{field} is not a valid RFC3339 timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"{field} must include a timezone: {value}")
    return parsed.astimezone(timezone.utc)


def require_stable_id(value: Any, *, field: str) -> str:
    """Validate a portable identifier used by the public v1 wire schema."""
    if not isinstance(value, str) or not _STABLE_ID.fullmatch(value):
        raise ContractError(f"{field} is not a valid stable identifier")
    return value


def require_fields(record: Mapping[str, Any], fields: tuple[str, ...], *, kind: str) -> None:
    missing = [field for field in fields if field not in record]
    if missing:
        raise ContractError(f"{kind} missing required fields: {', '.join(missing)}")
    if record.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(
            f"{kind} schema_version must be {SCHEMA_VERSION}, got {record.get('schema_version')!r}"
        )


@dataclass(frozen=True, slots=True)
class Observation:
    observation_id: str
    series_id: str
    source_id: str
    artifact_id: str
    observed_at: datetime
    released_at: datetime
    vintage_at: datetime
    ingested_at: datetime
    value: Any
    unit: str
    raw: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, record: Mapping[str, Any]) -> Observation:
        require_fields(
            record,
            (
                "schema_version",
                "observation_id",
                "series_id",
                "source_id",
                "artifact_id",
                "observed_at",
                "released_at",
                "vintage_at",
                "ingested_at",
                "value",
                "unit",
            ),
            kind="observation",
        )
        unknown_fields = sorted(set(record) - _OBSERVATION_FIELDS)
        if unknown_fields:
            raise ContractError(f"observation has unknown fields: {', '.join(unknown_fields)}")
        observation_id = require_stable_id(record["observation_id"], field="observation_id")
        series_id = require_stable_id(record["series_id"], field="series_id")
        source_id = require_stable_id(record["source_id"], field="source_id")
        artifact_id = require_stable_id(record["artifact_id"], field="artifact_id")
        unit = record["unit"]
        if not isinstance(unit, str) or not unit:
            raise ContractError("unit must be a non-empty string")
        if "extensions" in record and not isinstance(record["extensions"], Mapping):
            raise ContractError("observation.extensions must be an object")
        value = record["value"]
        if not isinstance(value, (int, float, str, bool, type(None))) or (
            isinstance(value, float) and not isfinite(value)
        ):
            raise ContractError("observation.value must be a finite JSON scalar")
        quality = record.get("quality")
        if quality is not None and quality not in {"reported", "derived", "synthetic", "unknown"}:
            raise ContractError("observation.quality is invalid")
        revision_of = record.get("revision_of")
        if revision_of is not None:
            require_stable_id(revision_of, field="observation.revision_of")
        released_at = parse_timestamp(str(record["released_at"]), field="released_at")
        vintage_at = parse_timestamp(str(record["vintage_at"]), field="vintage_at")
        ingested_at = parse_timestamp(str(record["ingested_at"]), field="ingested_at")
        if vintage_at < released_at:
            raise ContractError("vintage_at must not precede released_at")
        if ingested_at < released_at or ingested_at < vintage_at:
            raise ContractError("ingested_at must not precede released_at or vintage_at")
        return cls(
            observation_id=observation_id,
            series_id=series_id,
            source_id=source_id,
            artifact_id=artifact_id,
            observed_at=parse_timestamp(str(record["observed_at"]), field="observed_at"),
            released_at=released_at,
            vintage_at=vintage_at,
            ingested_at=ingested_at,
            value=value,
            unit=unit,
            raw=dict(record),
        )

    def cutoff_reasons(
        self, cutoff: datetime, *, require_ingested_by_cutoff: bool = False
    ) -> tuple[str, ...]:
        """Return every knowledge-time reason that makes the observation ineligible."""
        checks: tuple[tuple[str, datetime], ...] = (
            ("released_after_information_cutoff", self.released_at),
            ("vintage_after_information_cutoff", self.vintage_at),
        )
        if require_ingested_by_cutoff:
            checks += (("ingested_after_information_cutoff", self.ingested_at),)
        return tuple(reason for reason, timestamp in checks if timestamp > cutoff)

    def is_eligible(self, cutoff: datetime, *, require_ingested_by_cutoff: bool = False) -> bool:
        return not self.cutoff_reasons(
            cutoff, require_ingested_by_cutoff=require_ingested_by_cutoff
        )


@dataclass(frozen=True, slots=True)
class Artifact:
    artifact_id: str
    source_id: str
    retrieved_at: datetime
    source_published_at: datetime | None
    sha256: str
    byte_length: int
    media_type: str
    storage_uri: str | None
    license: Mapping[str, Any]
    extensions: Mapping[str, Any]
    raw: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, record: Mapping[str, Any]) -> Artifact:
        require_fields(
            record,
            (
                "schema_version",
                "artifact_id",
                "source_id",
                "retrieved_at",
                "sha256",
                "byte_length",
                "media_type",
                "license",
            ),
            kind="artifact",
        )
        unknown = sorted(set(record) - _ARTIFACT_FIELDS)
        if unknown:
            raise ContractError(f"artifact has unknown fields: {', '.join(unknown)}")
        artifact_id = require_stable_id(record["artifact_id"], field="artifact_id")
        source_id = require_stable_id(record["source_id"], field="source_id")
        retrieved_at = parse_timestamp(str(record["retrieved_at"]), field="retrieved_at")
        published_value = record.get("source_published_at")
        source_published_at = (
            None
            if published_value is None
            else parse_timestamp(str(published_value), field="source_published_at")
        )
        if source_published_at is not None and source_published_at > retrieved_at:
            raise ContractError("source_published_at must not follow retrieved_at")
        digest = record["sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ContractError("artifact.sha256 must be a lowercase SHA-256 digest")
        byte_length = record["byte_length"]
        if isinstance(byte_length, bool) or not isinstance(byte_length, int) or byte_length < 0:
            raise ContractError("artifact.byte_length must be a non-negative integer")
        media_type = record["media_type"]
        if not isinstance(media_type, str) or not media_type:
            raise ContractError("artifact.media_type must be a non-empty string")
        storage_uri = record.get("storage_uri")
        if storage_uri is not None and (not isinstance(storage_uri, str) or not storage_uri):
            raise ContractError("artifact.storage_uri must be null or a non-empty string")
        license_record = record["license"]
        if not isinstance(license_record, Mapping):
            raise ContractError("artifact.license must be an object")
        unknown_license_fields = sorted(set(license_record) - _LICENSE_FIELDS)
        if unknown_license_fields:
            raise ContractError(
                "artifact.license has unknown fields: " + ", ".join(unknown_license_fields)
            )
        if not isinstance(license_record.get("license_id"), str) or not license_record.get(
            "license_id"
        ):
            raise ContractError("artifact.license.license_id is required")
        if license_record.get("redistribution") not in {
            "allowed",
            "restricted",
            "forbidden",
            "unknown",
        }:
            raise ContractError("artifact.license.redistribution is invalid")
        if "commercial_use" in license_record and license_record["commercial_use"] not in {
            "allowed",
            "restricted",
            "forbidden",
            "unknown",
        }:
            raise ContractError("artifact.license.commercial_use is invalid")
        terms_url = license_record.get("terms_url")
        if terms_url is not None and (
            not isinstance(terms_url, str) or not _ABSOLUTE_URI.fullmatch(terms_url)
        ):
            raise ContractError("artifact.license.terms_url must be an absolute URI or null")
        attribution = license_record.get("attribution")
        if attribution is not None and not isinstance(attribution, str):
            raise ContractError("artifact.license.attribution must be a string or null")
        reviewed_at = license_record.get("reviewed_at")
        if reviewed_at is not None:
            parse_timestamp(str(reviewed_at), field="artifact.license.reviewed_at")
        extensions = record.get("extensions", {})
        if not isinstance(extensions, Mapping):
            raise ContractError("artifact.extensions must be an object")
        return cls(
            artifact_id=artifact_id,
            source_id=source_id,
            retrieved_at=retrieved_at,
            source_published_at=source_published_at,
            sha256=digest,
            byte_length=byte_length,
            media_type=media_type,
            storage_uri=storage_uri,
            license=dict(license_record),
            extensions=dict(extensions),
            raw=dict(record),
        )

    def authenticates_historical_version(
        self, cutoff: datetime, *, allow_synthetic_fixture: bool = False
    ) -> bool:
        """Verify a proof bound to this exact artifact.

        The pre-alpha runtime only implements the synthetic-fixture verifier. A
        future archive/signature verifier must be explicit; arbitrary metadata
        cannot promote a real late-ingested artifact into point-in-time evidence.
        """
        proof = self.extensions.get("availability_proof")
        if not isinstance(proof, Mapping) or proof.get("verified") is not True:
            return False
        released_at = proof.get("version_released_at")
        method = proof.get("method")
        if (
            proof.get("proof_type") != "synthetic_fixture"
            or not allow_synthetic_fixture
            or self.extensions.get("fixture_kind") != "synthetic"
            or proof.get("source_id") != self.source_id
            or proof.get("artifact_sha256") != self.sha256
            or not isinstance(proof.get("verified_by"), str)
            or not proof.get("verified_by")
            or not isinstance(released_at, str)
            or not isinstance(method, str)
            or not method
            or self.source_published_at is None
        ):
            return False
        try:
            proof_release = parse_timestamp(released_at, field="version_released_at")
            return proof_release == self.source_published_at and proof_release <= cutoff
        except ContractError:
            return False
