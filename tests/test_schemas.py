from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from openmacrostate.runtime.case import evaluate_case

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "2023-banks"
REVEAL = ROOT / "reveals" / "2023-banks"
SCHEMAS = ROOT / "schemas" / "v1"


def _records(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _validate(instance: dict[str, object], schema_name: str) -> None:
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    assert not errors, "\n".join(error.message for error in errors)


def test_bundled_case_matches_public_wire_schemas() -> None:
    _validate(json.loads((CASE / "case.json").read_text(encoding="utf-8")), "case.schema.json")
    for record in _records(CASE / "inputs" / "artifacts.jsonl"):
        _validate(record, "artifact.schema.json")
    for record in _records(CASE / "inputs" / "observations.jsonl"):
        _validate(record, "observation.schema.json")
    for record in _records(CASE / "inputs" / "claims.jsonl"):
        _validate(record, "claim.schema.json")
    for record in _records(CASE / "inputs" / "predictions.jsonl"):
        _validate(record, "prediction.schema.json")
    reveal = json.loads((REVEAL / "reveal.json").read_text(encoding="utf-8"))
    _validate(reveal, "reveal.schema.json")
    for record in _records(REVEAL / "artifacts.jsonl"):
        _validate(record, "artifact.schema.json")
    for record in _records(REVEAL / "outcomes.jsonl"):
        _validate(record, "outcome.schema.json")
    _validate(evaluate_case(CASE).snapshot(), "snapshot.schema.json")
