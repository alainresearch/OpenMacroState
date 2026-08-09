"""Immutable values exchanged across the connector/core trust boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class FetchRequest:
    """A declarative HTTP request which the core may accept or reject."""

    method: str
    url: str
    accept: str
    max_bytes: int


@dataclass(frozen=True, slots=True)
class TransportResponse:
    """Bytes and minimal provenance returned by a core-owned transport."""

    status_code: int
    final_url: str
    headers: Mapping[str, str]
    retrieved_at: str
    body: bytes


@dataclass(frozen=True, slots=True)
class FrozenArtifact:
    """Exact response bytes after core policy checks and SHA-256 calculation."""

    source_id: str
    request_url: str
    final_url: str
    status_code: int
    media_type: str
    response_headers: Mapping[str, str]
    retrieved_at: str
    transport_retrieved_at_claim: str
    body: bytes
    sha256: str
    byte_length: int
    capture_mode: str
    recording_kind: str
    source_authentication: str
    transport_time_core_observed: bool


@dataclass(frozen=True, slots=True)
class ObservationDraft:
    """Source semantics proposed by a connector before core provenance is added."""

    series_id: str
    observed_at: str
    released_at: str
    value: Any
    unit: str
    quality: str = "reported"
    extensions: Mapping[str, Any] = field(default_factory=dict)
