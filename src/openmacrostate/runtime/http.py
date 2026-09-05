"""Core-owned HTTP transports for live capture and deterministic replay."""

from __future__ import annotations

import math
import ssl
import urllib.error
import urllib.request
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Protocol

from openmacrostate.api.v1.connector_types import FetchRequest, TransportResponse
from openmacrostate.api.v1.errors import ContractError
from openmacrostate.api.v1.types import SCHEMA_VERSION, parse_timestamp
from openmacrostate.runtime.jsonio import load_json, sha256_bytes

_RESPONSE_HEADERS = frozenset({"content-type", "date", "etag", "last-modified"})


class HttpTransport(Protocol):
    """Transport interface injected into the connector runner."""

    def fetch(self, request: FetchRequest) -> TransportResponse: ...


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _filtered_headers(headers: Mapping[str, str]) -> Mapping[str, str]:
    filtered: dict[str, str] = {}
    for name, value in headers.items():
        normalized = name.lower()
        if normalized in _RESPONSE_HEADERS:
            filtered[normalized] = str(value)
    return MappingProxyType(filtered)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class LiveHttpTransport:
    """Minimal no-proxy HTTPS client. Network use must be selected by the CLI."""

    __slots__ = ("_timeout_seconds",)

    def __init__(self, *, timeout_seconds: float = 20.0) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
            or timeout_seconds > 120
        ):
            raise ContractError("live HTTP timeout must be finite and between 0 and 120 seconds")
        self._timeout_seconds = float(timeout_seconds)

    def fetch(self, request: FetchRequest) -> TransportResponse:
        wire_request = urllib.request.Request(
            request.url,
            headers={
                "Accept": request.accept,
                "Accept-Encoding": "identity",
                "User-Agent": "OpenMacroState/connector-v1 (+https://github.com/alainresearch/openmacrostate)",
            },
            method=request.method,
        )
        # Build the no-proxy, verified-TLS opener inside the core-owned fetch path.
        # Keeping an opener on the instance would let callers replace it while the
        # runner still classified this exact transport type as authenticated live I/O.
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
            _NoRedirect(),
        )
        try:
            with opener.open(wire_request, timeout=self._timeout_seconds) as response:
                content_length = response.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        declared_length = int(content_length)
                    except ValueError as exc:
                        raise ContractError("HTTP Content-Length is not an integer") from exc
                    if declared_length < 0 or declared_length > request.max_bytes:
                        raise ContractError("HTTP response exceeds the connector byte limit")
                chunks: list[bytes] = []
                size = 0
                while True:
                    chunk = response.read(min(64 * 1024, request.max_bytes - size + 1))
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > request.max_bytes:
                        raise ContractError("HTTP response exceeds the connector byte limit")
                    chunks.append(chunk)
                retrieved_at = _utc_now()
                parse_timestamp(retrieved_at, field="retrieved_at")
                return TransportResponse(
                    status_code=int(response.status),
                    final_url=str(response.geturl()),
                    headers=_filtered_headers(dict(response.headers.items())),
                    retrieved_at=retrieved_at,
                    body=b"".join(chunks),
                )
        except ContractError:
            raise
        except urllib.error.HTTPError as exc:
            raise ContractError(
                f"HTTP request failed closed with status {exc.code}; redirects are disabled"
            ) from exc
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise ContractError(f"HTTP retrieval failed: {exc}") from exc


class RecordedHttpTransport:
    """Replay one recorded response after verifying its exact bytes and request."""

    def __init__(self, recording_path: str | Path) -> None:
        self.recording_path = Path(recording_path).absolute()
        if self.recording_path.is_symlink() or not self.recording_path.is_file():
            raise ContractError("recording must be a regular file, not a symbolic link")
        if self.recording_path.lstat().st_nlink != 1:
            raise ContractError("recording must not be hard linked")
        record = load_json(self.recording_path)
        if not isinstance(record, dict):
            raise ContractError("HTTP recording must be a JSON object")
        allowed = {"schema_version", "recording_kind", "request", "response"}
        if set(record) != allowed or record.get("schema_version") != SCHEMA_VERSION:
            raise ContractError("HTTP recording has unsupported or unknown top-level fields")
        if record.get("recording_kind") not in {"complete_response", "test_only_excerpt"}:
            raise ContractError("HTTP recording_kind is invalid")
        request_record = record.get("request")
        response_record = record.get("response")
        if not isinstance(request_record, dict) or not isinstance(response_record, dict):
            raise ContractError("HTTP recording request and response must be objects")
        if set(request_record) != {"method", "url", "accept"}:
            raise ContractError("HTTP recording request has unknown or missing fields")
        expected_response_fields = {
            "status_code",
            "final_url",
            "headers",
            "retrieved_at",
            "body_file",
            "byte_length",
            "sha256",
        }
        if set(response_record) != expected_response_fields:
            raise ContractError("HTTP recording response has unknown or missing fields")
        self._record = record

    @property
    def recording_kind(self) -> str:
        """Return the receipt's completeness claim; this is not source authentication."""
        return str(self._record["recording_kind"])

    def _body_path(self, relative_value: object) -> Path:
        if not isinstance(relative_value, str) or not relative_value:
            raise ContractError("HTTP recording body_file must be a relative path")
        relative = Path(relative_value)
        if relative.is_absolute() or ".." in relative.parts:
            raise ContractError("HTTP recording body_file escapes the fixture directory")
        root = self.recording_path.parent.resolve()
        candidate = root / relative
        current = root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ContractError("HTTP recording body_file must not traverse a symbolic link")
        resolved = candidate.resolve()
        if resolved == root or root not in resolved.parents:
            raise ContractError("HTTP recording body_file escapes the fixture directory")
        if not resolved.is_file() or resolved.lstat().st_nlink != 1:
            raise ContractError("HTTP recording body_file must be a regular unlinked file")
        return resolved

    def fetch(self, request: FetchRequest) -> TransportResponse:
        request_record = self._record["request"]
        assert isinstance(request_record, dict)
        if (
            request_record.get("method") != request.method
            or request_record.get("url") != request.url
            or request_record.get("accept") != request.accept
        ):
            raise ContractError("HTTP recording does not match the planned request")
        response = self._record["response"]
        assert isinstance(response, dict)
        path = self._body_path(response["body_file"])
        expected_length = response.get("byte_length")
        if (
            isinstance(expected_length, bool)
            or not isinstance(expected_length, int)
            or expected_length < 0
            or expected_length > request.max_bytes
            or path.stat().st_size != expected_length
        ):
            raise ContractError("HTTP recording body byte length does not match its manifest")
        try:
            body = path.read_bytes()
        except OSError as exc:
            raise ContractError(f"cannot read HTTP recording body: {exc}") from exc
        expected_sha256 = response.get("sha256")
        if len(body) != expected_length:
            raise ContractError("HTTP recording body byte length does not match its manifest")
        if not isinstance(expected_sha256, str) or sha256_bytes(body) != expected_sha256:
            raise ContractError("HTTP recording body SHA-256 does not match its manifest")
        headers = response.get("headers")
        if not isinstance(headers, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in headers.items()
        ):
            raise ContractError("HTTP recording response headers must be strings")
        normalized_header_names = [name.lower() for name in headers]
        if len(normalized_header_names) != len(set(normalized_header_names)):
            raise ContractError("HTTP recording contains duplicate case-insensitive headers")
        unknown_headers = sorted(set(normalized_header_names) - _RESPONSE_HEADERS)
        if unknown_headers:
            raise ContractError(
                "HTTP recording contains non-audited response headers: "
                + ", ".join(unknown_headers)
            )
        retrieved_at = response.get("retrieved_at")
        if not isinstance(retrieved_at, str):
            raise ContractError("HTTP recording retrieved_at must be a string")
        parse_timestamp(retrieved_at, field="retrieved_at")
        status_code = response.get("status_code")
        final_url = response.get("final_url")
        if isinstance(status_code, bool) or not isinstance(status_code, int):
            raise ContractError("HTTP recording status_code must be an integer")
        if not isinstance(final_url, str):
            raise ContractError("HTTP recording final_url must be a string")
        return TransportResponse(
            status_code=status_code,
            final_url=final_url,
            headers=_filtered_headers(headers),
            retrieved_at=retrieved_at,
            body=body,
        )
