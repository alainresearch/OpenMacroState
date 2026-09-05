from __future__ import annotations

import json
import socket
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from openmacrostate.api.v1.errors import ContractError
from openmacrostate.cli import main
from openmacrostate.connectors.fed_h41_release import FedH41ReleaseConnector
from openmacrostate.runtime.accounting import (
    EXPERIMENTAL_FORMAT,
    FED_H41_BALANCE_SHEET_RULE,
    audit_accounting,
)
from openmacrostate.runtime.case import CaseEvaluation, evaluate_case
from openmacrostate.runtime.connectors import run_connector
from openmacrostate.runtime.http import RecordedHttpTransport
from openmacrostate.runtime.jsonio import canonical_json_bytes, normalize_json_value, sha256_bytes

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "connectors" / "fed_h41_release"
RECORDING = FIXTURE / "recording.json"
CORE_TIME = "2026-08-09T17:30:00Z"
OBSERVED_AT = "2023-03-15T00:00:00Z"


def _capture(output: Path) -> CaseEvaluation:
    capture = run_connector(
        FedH41ReleaseConnector(),
        {"start": "2023-03-16", "end": "2023-03-16"},
        RecordedHttpTransport(RECORDING),
        output,
        protected_paths=(FIXTURE,),
        clock=lambda: CORE_TIME,
    )
    return evaluate_case(capture.case_dir)


def _capture_with_replacements(
    output: Path,
    recording_dir: Path,
    replacements: tuple[tuple[str, str], ...],
) -> CaseEvaluation:
    text = (FIXTURE / "response.html").read_text(encoding="utf-8")
    for old, new in replacements:
        assert text.count(old) == 1
        text = text.replace(old, new)
    body = text.encode("utf-8")
    recording_dir.mkdir()
    (recording_dir / "response.html").write_bytes(body)
    recording = json.loads(RECORDING.read_text(encoding="utf-8"))
    recording["response"]["body_file"] = "response.html"
    recording["response"]["byte_length"] = len(body)
    recording["response"]["sha256"] = sha256_bytes(body)
    recording_path = recording_dir / "recording.json"
    recording_path.write_text(
        json.dumps(recording, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    capture = run_connector(
        FedH41ReleaseConnector(),
        {"start": "2023-03-16", "end": "2023-03-16"},
        RecordedHttpTransport(recording_path),
        output,
        protected_paths=(recording_dir,),
        clock=lambda: CORE_TIME,
    )
    return evaluate_case(capture.case_dir)


def _records(evaluation: CaseEvaluation) -> list[dict[str, Any]]:
    records = normalize_json_value(evaluation.accepted_observations)
    assert isinstance(records, list)
    return records


def _record(records: list[dict[str, Any]], series_id: str) -> dict[str, Any]:
    return next(record for record in records if record["series_id"] == series_id)


class _EvaluationStub:
    def __init__(
        self,
        source: CaseEvaluation,
        records: list[dict[str, Any]],
        *,
        quarantined: tuple[dict[str, Any], ...] = (),
    ) -> None:
        self.case_id = source.case_id
        self.information_cutoff = source.information_cutoff
        self.case = source.case
        self.case_dir = source.case_dir
        self.accepted_observations = tuple(records)
        self.quarantined_observations = quarantined
        self.artifacts = tuple(normalize_json_value(source.artifacts))
        self._content_sha256 = source.snapshot()["content_sha256"]

    def snapshot(self) -> dict[str, str]:
        return {"content_sha256": self._content_sha256}


def _audit(evaluation: Any) -> dict[str, Any]:
    return audit_accounting(
        evaluation,
        rule_id=FED_H41_BALANCE_SHEET_RULE,
        observed_at=OBSERVED_AT,
    )


def test_h41_accounting_audit_is_deterministic_and_hash_bound(tmp_path: Path) -> None:
    evaluation = _capture(tmp_path / "capture")

    first = _audit(evaluation)
    second = audit_accounting(
        evaluation,
        rule_id=FED_H41_BALANCE_SHEET_RULE,
        observed_at="2023-03-14T19:00:00-05:00",
    )

    assert first == second
    assert first["format"] == EXPERIMENTAL_FORMAT
    assert first["rule_id"] == FED_H41_BALANCE_SHEET_RULE
    assert first["boundary_id"] == "us.federal_reserve_banks.consolidated"
    assert first["observed_at"] == OBSERVED_AT
    assert first["unit"] == "USD_million"
    assert first["passed"] is True
    assert first["provenance_verification"] == "replayed_exact_artifact"
    assert first["connector_ruleset_version"] == "fed-h41-release-normalization/3"
    assert first["source_artifact_sha256"] == first["source_artifact_id"].removeprefix(
        "artifact:sha256:"
    )
    assert first["historical_version_authenticated"] is False
    assert first["provenance_verification_scope"] == (
        "exact_preserved_artifact_re_normalization_not_acquisition_authentication"
    )
    assert first["derived"] == {
        "liabilities_plus_capital": "8639300",
        "balance_sheet_residual": "0",
        "selected_asset_components": "8092867",
        "unselected_assets": "546433",
        "selected_liability_components": "3721851",
        "unselected_liabilities": "4874948",
    }
    assert [check["passed"] for check in first["checks"]] == [True, True, True]
    assert first["source_snapshot_content_sha256"] == evaluation.snapshot()["content_sha256"]
    expected_hash = first.pop("audit_sha256")
    assert expected_hash == sha256_bytes(canonical_json_bytes(first))


def test_accounting_audit_reads_accepted_observations_only(tmp_path: Path) -> None:
    evaluation = _capture(tmp_path / "capture")
    poisoned = deepcopy(_records(evaluation)[0])
    poisoned["value"] = "not-a-number"
    stub = _EvaluationStub(evaluation, _records(evaluation), quarantined=(poisoned,))

    assert _audit(stub)["passed"] is True


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda records: _record(records, "fed.h41.total_capital").update(
                source_id="unexpected.source"
            ),
            "unexpected source_id",
        ),
        (
            lambda records: _record(records, "fed.h41.total_capital").update(unit="USD"),
            "must use USD_million",
        ),
        (
            lambda records: _record(records, "fed.h41.total_capital").update(quality="derived"),
            "reported quality",
        ),
        (
            lambda records: _record(records, "fed.h41.total_capital").update(
                artifact_id="artifact:sha256:" + "0" * 64
            ),
            "exactly one source artifact",
        ),
        (
            lambda records: _record(records, "fed.h41.total_capital")["extensions"][
                "org.openmacrostate.accounting"
            ].update(role="component"),
            "unexpected accounting metadata",
        ),
        (
            lambda records: _record(records, "fed.h41.total_capital").update(value="NaN"),
            "canonical non-negative integer",
        ),
        (
            lambda records: _record(records, "fed.h41.total_capital").update(
                observed_at="2023-03-15T00:00:01Z"
            ),
            "found 0",
        ),
        (
            lambda records: _record(records, "fed.h41.total_capital").update(
                released_at="2026-08-09T17:30:01Z"
            ),
            "canonical released_at",
        ),
        (
            lambda records: _record(records, "fed.h41.total_capital").update(
                vintage_at="2026-08-09T17:30:01Z"
            ),
            "canonical vintage_at",
        ),
        (
            lambda records: _record(records, "fed.h41.total_capital").update(
                ingested_at="2026-08-09T17:30:01Z"
            ),
            "canonical ingested_at",
        ),
    ],
)
def test_accounting_audit_rejects_provenance_and_contract_drift(
    tmp_path: Path, mutation, message: str
) -> None:
    evaluation = _capture(tmp_path / "capture")
    records = _records(evaluation)
    mutation(records)

    with pytest.raises(ContractError, match=message):
        _audit(_EvaluationStub(evaluation, records))


def test_accounting_audit_requires_one_exact_time_match_per_series(tmp_path: Path) -> None:
    evaluation = _capture(tmp_path / "capture")
    missing = [
        record for record in _records(evaluation) if record["series_id"] != "fed.h41.total_capital"
    ]
    with pytest.raises(ContractError, match="found 0"):
        _audit(_EvaluationStub(evaluation, missing))

    duplicate = _records(evaluation)
    duplicate.append(deepcopy(_record(duplicate, "fed.h41.total_capital")))
    duplicate[-1]["observation_id"] = "observation:duplicate:total-capital"
    with pytest.raises(ContractError, match="found 2"):
        _audit(_EvaluationStub(evaluation, duplicate))


def test_accounting_audit_verifies_the_matching_artifact_source(tmp_path: Path) -> None:
    evaluation = _capture(tmp_path / "capture")
    stub = _EvaluationStub(evaluation, _records(evaluation))
    artifacts = normalize_json_value(stub.artifacts)
    artifacts[0]["source_id"] = "unexpected.source"
    stub.artifacts = tuple(artifacts)

    with pytest.raises(ContractError, match="source artifact has an unexpected source_id"):
        _audit(stub)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("media_type", "application/json", "must use text/html"),
        ("artifact_id", "artifact:sha256:" + "0" * 64, "derived from its SHA-256"),
    ],
)
def test_accounting_replay_rejects_artifact_identity_drift(
    tmp_path: Path, field: str, value: str, message: str
) -> None:
    evaluation = _capture(tmp_path / "capture")
    records = _records(evaluation)
    stub = _EvaluationStub(evaluation, records)
    if field == "artifact_id":
        for record in records:
            record["artifact_id"] = value
        stub.artifacts[0]["artifact_id"] = value
    else:
        stub.artifacts[0][field] = value

    with pytest.raises(ContractError, match=message):
        _audit(stub)


def test_accounting_replay_rejects_non_dated_request_metadata(tmp_path: Path) -> None:
    evaluation = _capture(tmp_path / "capture")
    stub = _EvaluationStub(evaluation, _records(evaluation))
    request = stub.artifacts[0]["extensions"]["request"]
    retrieval = stub.artifacts[0]["extensions"]["retrieval"]
    request["url"] = "https://www.federalreserve.gov/releases/h41/current/h41.htm"
    retrieval["final_url"] = request["url"]

    with pytest.raises(ContractError, match="fixed dated endpoint"):
        _audit(stub)


def test_accounting_replay_rechecks_preserved_bytes_at_audit_time(tmp_path: Path) -> None:
    evaluation = _capture(tmp_path / "capture")
    raw_path = evaluation.case_dir / str(evaluation.artifacts[0]["storage_uri"])
    body = raw_path.read_bytes()
    assert body.count(b"42,501") == 1
    raw_path.write_bytes(body.replace(b"42,501", b"42,502"))

    with pytest.raises(ContractError, match="SHA-256 does not match"):
        _audit(evaluation)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda record: record.update(value="42503"),
            "preserved artifact replay",
        ),
        (
            lambda record: record.update(observation_id="observation:spoof:total-capital"),
            "preserved artifact replay",
        ),
        (
            lambda record: record["extensions"].update(parser_id="spoofed-parser"),
            "preserved artifact replay",
        ),
        (
            lambda record: record["extensions"].update(source_cell_id="t8r999c3"),
            "preserved artifact replay",
        ),
    ],
)
def test_accounting_replay_rejects_plaintext_and_lineage_spoofing(
    tmp_path: Path, mutation, message: str
) -> None:
    evaluation = _capture(tmp_path / "capture")
    records = _records(evaluation)
    mutation(_record(records, "fed.h41.total_capital"))

    with pytest.raises(ContractError, match=message):
        _audit(_EvaluationStub(evaluation, records))


def test_accounting_replay_rejects_uniform_source_clock_drift(tmp_path: Path) -> None:
    evaluation = _capture(tmp_path / "capture")
    records = _records(evaluation)
    for record in records:
        record["released_at"] = "2026-08-09T17:00:00Z"
        record["vintage_at"] = "2026-08-09T17:10:00Z"
        record["ingested_at"] = "2026-08-09T17:20:00Z"

    with pytest.raises(ContractError, match="preserved artifact replay"):
        _audit(_EvaluationStub(evaluation, records))


def test_tolerance_is_fixed_at_one_usd_million(tmp_path: Path) -> None:
    within = _capture_with_replacements(
        tmp_path / "within-capture",
        tmp_path / "within-recording",
        ((">42,501</td>", ">42,502</td>"),),
    )
    within_report = _audit(within)
    assert within_report["checks"][0]["residual"] == "-1"
    assert within_report["checks"][0]["passed"] is True
    assert within_report["passed"] is True

    outside = _capture_with_replacements(
        tmp_path / "outside-capture",
        tmp_path / "outside-recording",
        ((">42,501</td>", ">42,503</td>"),),
    )
    outside_report = _audit(outside)
    assert outside_report["checks"][0]["residual"] == "-2"
    assert outside_report["checks"][0]["passed"] is False
    assert outside_report["passed"] is False


def test_partial_coverage_checks_fail_independently(tmp_path: Path) -> None:
    evaluation = _capture_with_replacements(
        tmp_path / "capture",
        tmp_path / "recording",
        (
            (">7,940,014</td>", ">8,486,449</td>"),
            (">3,444,208</td>", ">8,319,158</td>"),
        ),
    )

    report = _audit(evaluation)

    assert [check["passed"] for check in report["checks"]] == [True, False, False]
    assert report["derived"]["unselected_assets"] == "-2"
    assert report["derived"]["unselected_liabilities"] == "-2"
    assert report["passed"] is False


def test_accounting_cli_is_offline_and_returns_two_for_failed_check(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    evaluation = _capture(tmp_path / "capture")

    def forbidden_socket(*args, **kwargs):
        raise AssertionError("accounting audit attempted to open a network socket")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    args = [
        "audit",
        "accounting",
        str(evaluation.case_dir),
        "--rule",
        FED_H41_BALANCE_SHEET_RULE,
        "--observed-at",
        OBSERVED_AT,
        "--json",
    ]
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True

    failed = _capture_with_replacements(
        tmp_path / "failed-capture",
        tmp_path / "failed-recording",
        ((">42,501</td>", ">42,503</td>"),),
    )
    failed_args = [*args]
    failed_args[2] = str(failed.case_dir)
    assert main(failed_args) == 2
    assert json.loads(capsys.readouterr().out)["passed"] is False


def test_accounting_cli_human_summary_and_bad_rule(tmp_path: Path, capsys) -> None:
    evaluation = _capture(tmp_path / "capture")
    base = [
        "audit",
        "accounting",
        str(evaluation.case_dir),
        "--observed-at",
        OBSERVED_AT,
    ]

    assert main([*base, "--rule", FED_H41_BALANCE_SHEET_RULE]) == 0
    output = capsys.readouterr().out
    assert "PASS fed-h41-balance-sheet-v1" in output
    assert "residual=0 USD_million" in output
    assert "checks=3/3" in output

    assert main([*base, "--rule", "not-a-rule"]) == 2
    assert "unsupported accounting rule" in capsys.readouterr().err
