import json
import os
from pathlib import Path

import pytest

from openmacrostate.api.v1.connector_types import FetchRequest
from openmacrostate.api.v1.errors import CaseValidationError, ContractError
from openmacrostate.cli import main
from openmacrostate.runtime.http import (
    RecordedHttpTransport,
    inspect_http_recording,
)
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


def test_inspect_http_recording_valid(tmp_path: Path) -> None:
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
                    "sha256": sha256_bytes(body.read_bytes()),
                },
            }
        )
    )

    result = inspect_http_recording(recording)

    assert result["schema_version"] == "1.0.0"
    assert result["recording_kind"] == "complete_response"


def make_recording(tmp_path: Path, **response_overrides: object) -> Path:
    fixture = tmp_path / "recording"
    fixture.mkdir()

    body = fixture / "body.json"
    body.write_bytes(b'{"hello":"world"}')

    response = {
        "status_code": 200,
        "final_url": "https://example.com/data",
        "headers": {"content-type": "application/json"},
        "retrieved_at": "2026-08-14T00:00:00Z",
        "body_file": "body.json",
        "byte_length": len(body.read_bytes()),
        "sha256": sha256_bytes(body.read_bytes()),
    }
    response.update(response_overrides)

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
                "response": response,
            }
        )
    )
    return recording


def test_inspect_rejects_wrong_schema_version(tmp_path: Path) -> None:
    recording = make_recording(tmp_path)
    data = json.loads(recording.read_text())
    data["schema_version"] = "9.9.9"
    recording.write_text(json.dumps(data))

    with pytest.raises(ContractError, match="schema_version"):
        inspect_http_recording(recording)


def test_inspect_rejects_invalid_status(tmp_path: Path) -> None:
    recording = make_recording(tmp_path, status_code=99)

    with pytest.raises(ContractError, match="status_code"):
        inspect_http_recording(recording)


def test_inspect_rejects_invalid_timestamp(tmp_path: Path) -> None:
    recording = make_recording(
        tmp_path,
        retrieved_at="not-a-timestamp",
    )

    with pytest.raises(ContractError, match="retrieved_at"):
        inspect_http_recording(recording)


def test_inspect_rejects_unknown_header(tmp_path: Path) -> None:
    recording = make_recording(
        tmp_path,
        headers={"x-secret-header": "bad"},
    )

    with pytest.raises(ContractError, match="non-audited"):
        inspect_http_recording(recording)


def test_inspect_rejects_malformed_request(tmp_path: Path) -> None:
    recording = make_recording(tmp_path)
    data = json.loads(recording.read_text())
    data["request"]["method"] = 123
    recording.write_text(json.dumps(data))

    with pytest.raises(ContractError, match="method"):
        inspect_http_recording(recording)


def test_inspect_rejects_missing_body(tmp_path: Path) -> None:
    recording = make_recording(tmp_path)

    body = recording.parent / "body.json"
    body.unlink()

    with pytest.raises(ContractError, match="cannot read HTTP recording body"):
        inspect_http_recording(recording)


def test_inspect_rejects_symlink_body(tmp_path: Path) -> None:
    recording = make_recording(tmp_path)

    body = recording.parent / "body.json"
    real_body = recording.parent / "real_body.json"
    body.rename(real_body)

    try:
        body.symlink_to(real_body)
    except OSError as exc:
        pytest.skip(f"symlinks unavailable on this platform: {exc}")

    with pytest.raises(ContractError, match="symbolic link"):
        inspect_http_recording(recording)


def test_inspect_rejects_hard_link_body(tmp_path: Path) -> None:
    recording = make_recording(tmp_path)

    body = recording.parent / "body.json"
    hard_link = recording.parent / "body-hard-link.json"

    os.link(body, hard_link)

    data = json.loads(recording.read_text())
    data["response"]["body_file"] = hard_link.name
    recording.write_text(json.dumps(data))

    with pytest.raises(ContractError, match="hard"):
        inspect_http_recording(recording)


def test_inspect_recording_cli_human_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recording = make_recording(tmp_path)

    assert main(["connector", "inspect-recording", str(recording)]) == 0

    captured = capsys.readouterr()

    assert "PASS HTTP recording" in captured.out
    assert "recording_kind: complete_response" in captured.out
    assert "source authentication: not established" in captured.out
    assert "historical eligibility: not established" in captured.out
    assert captured.err == ""


def test_inspect_recording_cli_json_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recording = make_recording(tmp_path)

    assert main(["connector", "inspect-recording", str(recording), "--json"]) == 0

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["valid"] is True
    assert output["recording_kind"] == "complete_response"
    assert output["recording_kind_claim"] == "self-reported completeness claim"
    assert output["source_authenticated"] is False
    assert output["historical_eligibility_established"] is False
    assert captured.err == ""


def test_inspect_recording_cli_invalid_recording(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recording = make_recording(tmp_path, status_code=99)

    assert main(["connector", "inspect-recording", str(recording)]) == 2

    captured = capsys.readouterr()

    assert captured.out == ""
    assert "ERROR:" in captured.err
    assert "status_code" in captured.err


def test_inspect_recording_cli_never_uses_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recording = make_recording(tmp_path)

    def fail_if_network_used(*args: object, **kwargs: object) -> None:
        raise AssertionError("inspect-recording attempted network access")

    monkeypatch.setattr(
        "urllib.request.build_opener",
        fail_if_network_used,
    )

    assert main(["connector", "inspect-recording", str(recording)]) == 0


def test_inspect_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    fixture = tmp_path / "recording"
    fixture.mkdir()

    recording = fixture / "recording.json"

    recording.write_text(
        """
        {
            "schema_version": "1.0.0",
            "recording_kind": "complete_response",
            "recording_kind": "test_only_excerpt",
            "request": {},
            "response": {}
        }
        """,
        encoding="utf-8",
    )

    with pytest.raises(
        CaseValidationError,
        match="duplicate JSON object key",
    ):
        inspect_http_recording(recording)


def test_inspect_rejects_wrong_sha256(tmp_path: Path) -> None:
    recording = make_recording(tmp_path)

    data = json.loads(recording.read_text())
    data["response"]["sha256"] = "0" * 64
    recording.write_text(json.dumps(data))

    with pytest.raises(ContractError, match="SHA-256"):
        inspect_http_recording(recording)


def test_inspect_rejects_wrong_byte_length(tmp_path: Path) -> None:
    recording = make_recording(tmp_path)

    data = json.loads(recording.read_text())
    data["response"]["byte_length"] += 1
    recording.write_text(json.dumps(data))

    with pytest.raises(ContractError, match="byte length"):
        inspect_http_recording(recording)


def test_inspect_rejects_body_path_escape(tmp_path: Path) -> None:
    recording = make_recording(tmp_path)

    data = json.loads(recording.read_text())
    data["response"]["body_file"] = "../body.json"
    recording.write_text(json.dumps(data))

    with pytest.raises(
        ContractError,
        match="escapes the fixture directory",
    ):
        inspect_http_recording(recording)


def test_inspect_rejects_recording_symlink(tmp_path: Path) -> None:
    recording = make_recording(tmp_path)

    target = recording.with_name("real-recording.json")
    recording.rename(target)

    try:
        recording.symlink_to(target)

        with pytest.raises(
            ContractError,
            match="symbolic link",
        ):
            inspect_http_recording(recording)
    except OSError:
        pytest.skip("symlinks are not supported")


def test_inspect_rejects_recording_hard_link(tmp_path: Path) -> None:
    recording = make_recording(tmp_path)

    hard_link = recording.with_name("recording-copy.json")
    os.link(recording, hard_link)

    with pytest.raises(
        ContractError,
        match="hard link",
    ):
        inspect_http_recording(hard_link)
