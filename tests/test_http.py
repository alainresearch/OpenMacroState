import json
from pathlib import Path

import pytest

from openmacrostate.api.v1.connector_types import FetchRequest
from openmacrostate.api.v1.errors import ContractError
from openmacrostate.runtime.http import RecordedHttpTransport
from openmacrostate.runtime.jsonio import sha256_bytes


def test_recorded_transport_rejects_wrong_sha256(tmp_path: Path) -> None:
    fixture = tmp_path / "recording"
    fixture.mkdir()
    
    body = fixture / "body.json"
    body.write_bytes(b'{"hello":"world"}')
    
    recording = fixture / "recording.json"
    recording.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "recording_kind": "complete_response",
                "request": {
                    "method": "GET",
                    "url": "https://example.com/data",
                    "accept": "application/json",
                },
                "response": {
                    "status_code": 200,
                    "final_url": "https://example.com/data",
                    "headers": {"content-type": "application/json"},
                    "retrieved_at": "2026-08-14T00:00:00Z",
                    "body_file": "body.json",
                    "byte_length": len(body.read_bytes()),
                    "sha256": "0" * 64,
                },
            }
        )
    )
    
    transport = RecordedHttpTransport(recording)
    request = FetchRequest(
        method="GET",
        url="https://example.com/data",
        accept="application/json",
        max_bytes=1024,
    )
    
    with pytest.raises(ContractError, match="SHA-256"):
        transport.fetch(request)


def test_recorded_transport_rejects_wrong_byte_length(tmp_path: Path) -> None:
    fixture = tmp_path / "recording"
    fixture.mkdir()
    
    body = fixture / "body.json"
    body.write_bytes(b'{"hello":"world"}')
    
    recording = fixture / "recording.json"
    recording.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "recording_kind": "complete_response",
                "request": {
                    "method": "GET",
                    "url": "https://example.com/data",
                    "accept": "application/json",
                },
                "response": {
                    "status_code": 200,
                    "final_url": "https://example.com/data",
                    "headers": {"content-type": "application/json"},
                    "retrieved_at": "2026-08-14T00:00:00Z",
                    "body_file": "body.json",
                    "byte_length": 999,
                    "sha256": sha256_bytes(body.read_bytes()),
                },
            }
        )
    )
    
    transport = RecordedHttpTransport(recording)
    request = FetchRequest(
        method="GET",
        url="https://example.com/data",
        accept="application/json",
        max_bytes=1024,
    )
    
    with pytest.raises(ContractError, match="byte length"):
        transport.fetch(request)


def test_recorded_transport_rejects_body_path_escape(tmp_path: Path) -> None:
    fixture = tmp_path / "recording"
    fixture.mkdir()
    
    recording = fixture / "recording.json"
    recording.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "recording_kind": "complete_response",
                "request": {
                    "method": "GET",
                    "url": "https://example.com/data",
                    "accept": "application/json",
                },
                "response": {
                    "status_code": 200,
                    "final_url": "https://example.com/data",
                    "headers": {},
                    "retrieved_at": "2026-08-14T00:00:00Z",
                    "body_file": "../body.json",
                    "byte_length": 0,
                    "sha256": "0" * 64,
                },
            }
        )
    )
    
    with pytest.raises(ContractError, match="escapes the fixture directory"):
        RecordedHttpTransport(recording).fetch(
            FetchRequest(
                method="GET",
                url="https://example.com/data",
                accept="application/json",
                max_bytes=1024,
            )
        )


def test_recorded_transport_rejects_unknown_headers(tmp_path: Path) -> None:
    fixture = tmp_path / "recording"
    fixture.mkdir()
    
    body = fixture / "body.json"
    body.write_bytes(b"")
    
    recording = fixture / "recording.json"
    recording.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "recording_kind": "complete_response",
                "request": {
                    "method": "GET",
                    "url": "https://example.com/data",
                    "accept": "application/json",
                },
                "response": {
                    "status_code": 200,
                    "final_url": "https://example.com/data",
                    "headers": {"x-secret-header": "bad"},
                    "retrieved_at": "2026-08-14T00:00:00Z",
                    "body_file": "body.json",
                    "byte_length": 0,
                    "sha256": sha256_bytes(b""),
                },
            }
        )
    )
    
    with pytest.raises(ContractError, match="non-audited response headers"):
        RecordedHttpTransport(recording).fetch(
            FetchRequest(
                method="GET",
                url="https://example.com/data",
                accept="application/json",
                max_bytes=1024,
            )
        )


def test_recorded_transport_rejects_request_mismatch(tmp_path: Path) -> None:
    # Use one of the existing fixture recordings.
    recording = (
        Path(__file__).resolve().parents[1]
        / "tests"
        / "fixtures"
        / "connectors"
        / "frbny_sofr"
        / "recording.json"
    )
    
    transport = RecordedHttpTransport(recording)
    request = FetchRequest(
        method="GET",
        url="https://example.com/wrong",
        accept="application/json",
        max_bytes=1024 * 1024,
    )
    
    with pytest.raises(ContractError, match="does not match the planned request"):
        transport.fetch(request)