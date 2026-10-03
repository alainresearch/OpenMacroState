import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH = Path("schemas/v1/http-recording.schema.json")


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    return Draft202012Validator(
        _load_schema(),
        format_checker=FormatChecker(),
    )


def _recording(body_file: str) -> dict:
    return {
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
            "headers": {
                "content-type": "application/json",
            },
            "retrieved_at": "2026-09-06T12:00:00Z",
            "body_file": body_file,
            "byte_length": 0,
            "sha256": "0" * 64,
        },
    }


def test_body_file_schema_rejects_unsafe_paths() -> None:
    validator = _validator()

    for body_file in [
        "/body.json",
        "../body.json",
        "a/../body.json",
        "body\x00.json",
    ]:
        errors = list(validator.iter_errors(_recording(body_file)))
        assert errors, body_file


def test_body_file_schema_accepts_nested_relative_path() -> None:
    validator = _validator()

    errors = list(validator.iter_errors(_recording("responses/body.json")))

    assert not errors
