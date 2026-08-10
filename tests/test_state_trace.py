from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

import pytest

import openmacrostate.runtime.state_trace as state_trace_module
from openmacrostate.api.v1.errors import ContractError
from openmacrostate.cli import main
from openmacrostate.connectors.fed_h41_release import FedH41ReleaseConnector
from openmacrostate.runtime.accounting import FED_H41_BALANCE_SHEET_RULE
from openmacrostate.runtime.case import CaseEvaluation, evaluate_case
from openmacrostate.runtime.connectors import run_connector
from openmacrostate.runtime.http import RecordedHttpTransport
from openmacrostate.runtime.jsonio import canonical_json_bytes, normalize_json_value, sha256_bytes
from openmacrostate.runtime.state_trace import EXPERIMENTAL_FORMAT, trace_accounting_state

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "connectors" / "fed_h41_release"
RECORDING = FIXTURE / "recording.json"
CORE_TIME = "2026-08-09T17:30:00Z"
OBSERVED_AT = "2023-03-15T00:00:00Z"

REPORTED_NODE_IDS = (
    "reported:total_assets",
    "reported:total_liabilities",
    "reported:total_capital",
    "reported:securities_held_outright",
    "reported:primary_credit",
    "reported:treasury_general_account",
    "reported:reserve_balances",
)
DERIVED_NODE_IDS = (
    "derived:liabilities_plus_capital",
    "derived:balance_sheet_residual",
    "derived:selected_asset_components",
    "derived:unselected_assets",
    "derived:selected_liability_components",
    "derived:unselected_liabilities",
)
ALL_NODE_IDS = (*REPORTED_NODE_IDS, *DERIVED_NODE_IDS)
ALL_EDGE_TRIPLES = (
    (
        "reported:total_liabilities",
        "derived:liabilities_plus_capital",
        "addend_1",
    ),
    ("reported:total_capital", "derived:liabilities_plus_capital", "addend_2"),
    ("reported:total_assets", "derived:balance_sheet_residual", "minuend"),
    (
        "derived:liabilities_plus_capital",
        "derived:balance_sheet_residual",
        "subtrahend",
    ),
    (
        "reported:securities_held_outright",
        "derived:selected_asset_components",
        "addend_1",
    ),
    ("reported:primary_credit", "derived:selected_asset_components", "addend_2"),
    ("reported:total_assets", "derived:unselected_assets", "minuend"),
    (
        "derived:selected_asset_components",
        "derived:unselected_assets",
        "subtrahend",
    ),
    (
        "reported:reserve_balances",
        "derived:selected_liability_components",
        "addend_1",
    ),
    (
        "reported:treasury_general_account",
        "derived:selected_liability_components",
        "addend_2",
    ),
    ("reported:total_liabilities", "derived:unselected_liabilities", "minuend"),
    (
        "derived:selected_liability_components",
        "derived:unselected_liabilities",
        "subtrahend",
    ),
)


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


class _EvaluationStub:
    def __init__(self, source: CaseEvaluation, records: list[dict[str, Any]]) -> None:
        self.case_id = source.case_id
        self.information_cutoff = source.information_cutoff
        self.case = source.case
        self.case_dir = source.case_dir
        self.accepted_observations = tuple(records)
        self.quarantined_observations = ()
        self.artifacts = tuple(normalize_json_value(source.artifacts))
        self._content_sha256 = source.snapshot()["content_sha256"]

    def snapshot(self) -> dict[str, str]:
        return {"content_sha256": self._content_sha256}


def _trace(evaluation: Any, target: str = "all") -> dict[str, Any]:
    return trace_accounting_state(
        evaluation,
        FED_H41_BALANCE_SHEET_RULE,
        OBSERVED_AT,
        target,
    )


def _nodes_by_id(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["node_id"]: node for node in report["nodes"]}


def test_all_trace_has_exact_fact_nodes_edges_order_and_hash(tmp_path: Path) -> None:
    evaluation = _capture(tmp_path / "capture")

    report = _trace(evaluation)

    assert report["format"] == EXPERIMENTAL_FORMAT
    assert report["rule_id"] == FED_H41_BALANCE_SHEET_RULE
    assert report["target"] == "all"
    assert report["entity_id"] == "us.federal_reserve_banks"
    assert report["boundary_id"] == "us.federal_reserve_banks.consolidated"
    assert report["unit"] == "USD_million"
    assert report["materialization_mode"] == "retrospective_reconstruction"
    assert report["historical_evidence"] is False
    assert report["rights_propagation"] == "inherits_source_artifact_terms"
    assert report["passed"] is True
    assert report["causal_interpretation"] is False
    assert report["explicitly_excluded_epistemic_kinds"] == [
        "inference",
        "prediction",
        "scenario",
    ]
    assert [node["node_id"] for node in report["nodes"]] == list(ALL_NODE_IDS)
    assert [
        (edge["from_node_id"], edge["to_node_id"], edge["input_role"]) for edge in report["edges"]
    ] == list(ALL_EDGE_TRIPLES)
    assert {edge["edge_kind"] for edge in report["edges"]} == {"derivation_dependency"}
    assert all(edge["causal_interpretation"] is False for edge in report["edges"])

    nodes = _nodes_by_id(report)
    assert [nodes[node_id]["value_origin"] for node_id in REPORTED_NODE_IDS] == ["reported"] * 7
    assert [nodes[node_id]["value_origin"] for node_id in DERIVED_NODE_IDS] == ["derived"] * 6
    assert {node["epistemic_kind"] for node in report["nodes"]} == {"fact"}
    assert {
        node_id.removeprefix("derived:"): nodes[node_id]["value"] for node_id in DERIVED_NODE_IDS
    } == {
        "liabilities_plus_capital": "8639300",
        "balance_sheet_residual": "0",
        "selected_asset_components": "8092867",
        "unselected_assets": "546433",
        "selected_liability_components": "3721851",
        "unselected_liabilities": "4874948",
    }
    for node_id in REPORTED_NODE_IDS:
        node = nodes[node_id]
        assert {
            "observation_id",
            "source_id",
            "artifact_id",
            "observed_at",
            "released_at",
            "vintage_at",
            "ingested_at",
            "revision_of",
        } <= set(node)
        assert node["revision_of"] is None
    for node_id in DERIVED_NODE_IDS:
        node = nodes[node_id]
        assert node["operation"] in {"add", "subtract"}
        assert node["input_node_ids"]
        assert node["knowledge_time_envelope"] == {
            "released_at": CORE_TIME,
            "vintage_at": CORE_TIME,
            "ingested_at": CORE_TIME,
        }

    for field in (
        "audit_sha256",
        "source_snapshot_content_sha256",
        "source_artifact_id",
        "source_artifact_sha256",
        "provenance_verification",
        "connector_ruleset_version",
        "source_authentication",
        "provenance_verification_scope",
        "historical_version_authenticated",
    ):
        assert field in report
    expected_trace_sha256 = report.pop("trace_sha256")
    assert expected_trace_sha256 == sha256_bytes(canonical_json_bytes(report))


@pytest.mark.parametrize(
    ("target", "expected_node_ids", "expected_edge_count"),
    [
        (
            "liabilities_plus_capital",
            (
                "reported:total_liabilities",
                "reported:total_capital",
                "derived:liabilities_plus_capital",
            ),
            2,
        ),
        (
            "balance_sheet_residual",
            (
                "reported:total_assets",
                "reported:total_liabilities",
                "reported:total_capital",
                "derived:liabilities_plus_capital",
                "derived:balance_sheet_residual",
            ),
            4,
        ),
        (
            "selected_asset_components",
            (
                "reported:securities_held_outright",
                "reported:primary_credit",
                "derived:selected_asset_components",
            ),
            2,
        ),
        (
            "unselected_assets",
            (
                "reported:total_assets",
                "reported:securities_held_outright",
                "reported:primary_credit",
                "derived:selected_asset_components",
                "derived:unselected_assets",
            ),
            4,
        ),
        (
            "selected_liability_components",
            (
                "reported:treasury_general_account",
                "reported:reserve_balances",
                "derived:selected_liability_components",
            ),
            2,
        ),
        (
            "unselected_liabilities",
            (
                "reported:total_liabilities",
                "reported:treasury_general_account",
                "reported:reserve_balances",
                "derived:selected_liability_components",
                "derived:unselected_liabilities",
            ),
            4,
        ),
    ],
)
def test_target_returns_only_target_and_upstream_closure_in_fixed_order(
    tmp_path: Path,
    target: str,
    expected_node_ids: tuple[str, ...],
    expected_edge_count: int,
) -> None:
    report = _trace(_capture(tmp_path / "capture"), target)

    assert report["target"] == target
    assert [node["node_id"] for node in report["nodes"]] == list(expected_node_ids)
    assert len(report["edges"]) == expected_edge_count
    included = set(expected_node_ids)
    assert all(
        edge["from_node_id"] in included and edge["to_node_id"] in included
        for edge in report["edges"]
    )
    assert report["nodes"][-1]["node_id"] == f"derived:{target}"


def test_trace_is_timezone_equivalent_and_calls_accounting_audit_once(
    tmp_path: Path, monkeypatch
) -> None:
    evaluation = _capture(tmp_path / "capture")
    real_audit = state_trace_module.audit_accounting
    calls = 0

    def counted_audit(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_audit(*args, **kwargs)

    monkeypatch.setattr(state_trace_module, "audit_accounting", counted_audit)
    first = trace_accounting_state(
        evaluation,
        FED_H41_BALANCE_SHEET_RULE,
        OBSERVED_AT,
        "all",
    )
    assert calls == 1

    monkeypatch.setattr(state_trace_module, "audit_accounting", real_audit)
    second = trace_accounting_state(
        evaluation,
        FED_H41_BALANCE_SHEET_RULE,
        "2023-03-14T19:00:00-05:00",
        "all",
    )
    assert first == second


def test_trace_is_explicitly_non_causal_without_geographic_id_mixing(tmp_path: Path) -> None:
    report = _trace(_capture(tmp_path / "capture"))

    assert report["causal_interpretation"] is False
    assert all(edge["causal_interpretation"] is False for edge in report["edges"])
    assert all(
        node["entity_id"] == "us.federal_reserve_banks"
        and node["boundary_id"] == "us.federal_reserve_banks.consolidated"
        for node in report["nodes"]
    )
    serialized = canonical_json_bytes(report).decode("utf-8").lower()
    assert "fips" not in serialized
    assert "inference" not in {node["epistemic_kind"] for node in report["nodes"]}
    assert "prediction" not in {node["epistemic_kind"] for node in report["nodes"]}
    assert "scenario" not in {node["epistemic_kind"] for node in report["nodes"]}


def test_trace_rejects_unknown_target_before_audit(tmp_path: Path, monkeypatch) -> None:
    evaluation = _capture(tmp_path / "capture")

    def forbidden_audit(*args, **kwargs):
        raise AssertionError("invalid target should be rejected before accounting replay")

    monkeypatch.setattr(state_trace_module, "audit_accounting", forbidden_audit)
    with pytest.raises(ContractError, match="unsupported accounting state trace target"):
        _trace(evaluation, "total_assets")


def test_trace_fails_closed_when_preserved_artifact_is_modified(tmp_path: Path) -> None:
    evaluation = _capture(tmp_path / "capture")
    raw_path = evaluation.case_dir / str(evaluation.artifacts[0]["storage_uri"])
    body = raw_path.read_bytes()
    assert body.count(b"42,501") == 1
    raw_path.write_bytes(body.replace(b"42,501", b"42,502"))

    with pytest.raises(ContractError, match="SHA-256 does not match"):
        _trace(evaluation)


def test_trace_fails_closed_when_observation_time_is_modified(tmp_path: Path) -> None:
    evaluation = _capture(tmp_path / "capture")
    records = _records(evaluation)
    total_capital = next(
        record for record in records if record["series_id"] == "fed.h41.total_capital"
    )
    total_capital["released_at"] = "2026-08-09T17:30:01Z"

    with pytest.raises(ContractError, match="canonical released_at"):
        _trace(_EvaluationStub(evaluation, records))


def test_failed_accounting_check_still_returns_a_hashed_trace(tmp_path: Path) -> None:
    evaluation = _capture_with_replacements(
        tmp_path / "capture",
        tmp_path / "recording",
        ((">42,501</td>", ">42,503</td>"),),
    )

    report = _trace(evaluation)

    assert report["passed"] is False
    assert [node["node_id"] for node in report["nodes"]] == list(ALL_NODE_IDS)
    assert _nodes_by_id(report)["derived:balance_sheet_residual"]["value"] == "-2"
    trace_sha256 = report.pop("trace_sha256")
    assert trace_sha256 == sha256_bytes(canonical_json_bytes(report))


def test_state_trace_cli_is_offline_and_deterministic(tmp_path: Path, monkeypatch, capsys) -> None:
    evaluation = _capture(tmp_path / "capture")
    case_before = {
        path.relative_to(evaluation.case_dir): path.read_bytes()
        for path in evaluation.case_dir.rglob("*")
        if path.is_file()
    }

    def forbidden_socket(*args, **kwargs):
        raise AssertionError("state trace attempted to open a network socket")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    args = [
        "trace",
        "state",
        str(evaluation.case_dir),
        "--rule",
        FED_H41_BALANCE_SHEET_RULE,
        "--observed-at",
        OBSERVED_AT,
        "--target",
        "balance_sheet_residual",
        "--json",
    ]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert main(args) == 0
    second = capsys.readouterr().out
    assert first == second
    report = json.loads(first)
    assert report["target"] == "balance_sheet_residual"
    assert report["nodes"][-1]["value"] == "0"
    assert {
        path.relative_to(evaluation.case_dir): path.read_bytes()
        for path in evaluation.case_dir.rglob("*")
        if path.is_file()
    } == case_before


def test_state_trace_cli_human_summary_and_failed_audit_exit_two(tmp_path: Path, capsys) -> None:
    evaluation = _capture(tmp_path / "capture")
    base = [
        "trace",
        "state",
        str(evaluation.case_dir),
        "--rule",
        FED_H41_BALANCE_SHEET_RULE,
        "--observed-at",
        OBSERVED_AT,
        "--target",
        "balance_sheet_residual",
    ]
    assert main(base) == 0
    output = capsys.readouterr().out
    assert "PASS state-trace" in output
    assert "value=0 USD_million" in output
    assert "causal=false" in output

    failed = _capture_with_replacements(
        tmp_path / "failed-capture",
        tmp_path / "failed-recording",
        ((">42,501</td>", ">42,503</td>"),),
    )
    failed_args = [*base]
    failed_args[2] = str(failed.case_dir)
    failed_args.append("--json")
    assert main(failed_args) == 2
    assert json.loads(capsys.readouterr().out)["passed"] is False
