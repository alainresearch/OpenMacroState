from __future__ import annotations

import json
import shutil
import socket
from hashlib import sha256
from pathlib import Path

import pytest

from openmacrostate.cli import main

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "2023-banks"
REVEAL = ROOT / "reveals" / "2023-banks"
EVALUATION_AT = "2023-03-13T22:00:00Z"


def _demo_args(output: Path, *extra: str) -> list[str]:
    return [
        "demo",
        str(CASE),
        "--reveal",
        str(REVEAL),
        "--evaluation-at",
        EVALUATION_AT,
        "--output",
        str(output),
        *extra,
    ]


def test_validate_command(capsys) -> None:
    assert main(["validate", str(CASE), "--json"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["accepted_observations"] == 4
    assert summary["quarantined_observations"] == 1
    assert summary["accepted_claims"] == 2
    assert summary["rejected_claims"] == 1


def test_validate_can_write_sealed_snapshot(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.json"
    assert main(["validate", str(CASE), "--snapshot", str(snapshot)]) == 0
    record = json.loads(snapshot.read_text(encoding="utf-8"))
    assert len(record["content_sha256"]) == 64
    assert record["extensions"]["content_hash_scope"] == "extensions.eligible_content"
    assert record["extensions"]["eligible_content"]["research_integrity"]["manifest_sha256"]
    assert main(["validate", str(CASE), "--snapshot", str(snapshot)]) == 2


def test_bundled_example_command(tmp_path: Path) -> None:
    output = tmp_path / "example"
    assert main(["example", "2023-banks", "--output", str(output)]) == 0
    assert (output / "report.md").is_file()


def test_bundled_example_does_not_open_a_network_socket(tmp_path: Path, monkeypatch) -> None:
    def forbidden_socket(*args, **kwargs):
        raise AssertionError("offline example attempted to open a network socket")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    output = tmp_path / "offline-example"
    assert main(["example", "2023-banks", "--output", str(output)]) == 0


def test_demo_writes_auditable_outputs(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    assert main(_demo_args(output)) == 0

    expected = {
        ".openmacrostate-output.json",
        "artifact_manifest.json",
        "claims.jsonl",
        "observations.jsonl",
        "predictions.jsonl",
        "quarantine.jsonl",
        "rejected_claims.jsonl",
        "report.md",
        "scores.json",
        "snapshot.json",
    }
    assert {path.name for path in output.iterdir()} == expected
    report = (output / "report.md").read_text(encoding="utf-8")
    assert "SYNTHETIC SOFTWARE FIXTURE" in report
    assert "NOT HISTORICAL EVIDENCE" in report
    claims = (output / "claims.jsonl").read_text(encoding="utf-8")
    assert "claim_synth_leaky_must_reject" not in claims

    assert main(_demo_args(output)) == 2
    assert main(_demo_args(output, "--force")) == 0


@pytest.mark.parametrize("audit_case", ["fixture", "all_accepted", "rejected_prediction_only"])
def test_demo_report_describes_actual_audit(tmp_path: Path, audit_case: str) -> None:
    case_dir = tmp_path / "case"
    shutil.copytree(CASE, case_dir)
    if audit_case != "fixture":
        for filename, id_field, excluded_id in (
            ("observations.jsonl", "observation_id", "obs_synth_post_cutoff_trap"),
            ("claims.jsonl", "claim_id", "claim_synth_leaky_must_reject"),
        ):
            path = case_dir / "inputs" / filename
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            path.write_text(
                "".join(
                    json.dumps(record) + "\n"
                    for record in records
                    if record[id_field] != excluded_id
                ),
                encoding="utf-8",
            )
    if audit_case == "rejected_prediction_only":
        path = case_dir / "inputs" / "predictions.jsonl"
        prediction = json.loads(path.read_text(encoding="utf-8"))
        prediction["made_at"] = "2023-03-10T00:00:00Z"
        path.write_text(json.dumps(prediction) + "\n", encoding="utf-8")
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    manifest_path = case_dir / case["extensions"]["checksums_file"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        data = (case_dir / entry["path"]).read_bytes()
        entry["bytes"] = len(data)
        entry["sha256"] = sha256(data).hexdigest()
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    output = tmp_path / "demo"
    args = _demo_args(output)
    args[1] = str(case_dir)
    assert main(args) == 0
    report = (output / "report.md").read_text(encoding="utf-8")
    snapshot = json.loads((output / "snapshot.json").read_text(encoding="utf-8"))
    counts = snapshot["extensions"]["eligible_content"]["exclusion_counts"]
    interpretation = report.split("## Interpretation\n", 1)[1]
    assert "deliberately late observation" not in interpretation
    assert "rejected transitively" not in interpretation
    assert (
        "Only accepted observations, claims, and predictions appear in the analysis snapshot."
        in report
    )
    assert "### Rejected predictions\n\n" in report
    if audit_case == "fixture":
        assert counts == {"observations": 1, "claims": 1, "predictions": 0}
        quarantine = json.loads((output / "quarantine.jsonl").read_text(encoding="utf-8"))
        assert all(reason in report for reason in quarantine["quarantine"]["reasons"])
        assert "claim_synth_leaky_must_reject` — ineligible_evidence_at_claim_cutoff" in report
        assert (
            "The excluded records and their validator reasons are listed above." in interpretation
        )
    elif audit_case == "all_accepted":
        assert counts == {"observations": 0, "claims": 0, "predictions": 0}
        assert "### Quarantined observations\n\n- None" in report
        assert "### Rejected claims\n\n- None" in report
        assert "### Rejected predictions\n\n- None" in report
        assert (
            "This run quarantined no observations and rejected no claims or predictions."
            in interpretation
        )
    else:
        assert counts == {"observations": 0, "claims": 0, "predictions": 1}
        assert "pred_naive_synth_bank_stress` — prediction_made_after_information_cutoff" in report
        assert "- No accepted predictions" in report
        assert (
            "The excluded records and their validator reasons are listed above." in interpretation
        )


def test_demo_rejects_arbitrary_non_empty_output(tmp_path: Path, capsys) -> None:
    output = tmp_path / "not-ours"
    output.mkdir()
    (output / "important.txt").write_text("keep me", encoding="utf-8")

    assert main(_demo_args(output, "--force")) == 2
    assert "refusing to replace" in capsys.readouterr().err
    assert (output / "important.txt").read_text(encoding="utf-8") == "keep me"


def test_demo_rejects_output_inside_case(capsys) -> None:
    assert main(_demo_args(CASE / "build")) == 2
    assert "ancestor or descendant" in capsys.readouterr().err


def test_demo_rejects_output_ancestor_of_inputs(capsys) -> None:
    assert main(_demo_args(ROOT)) == 2
    assert "ancestor or descendant" in capsys.readouterr().err


def test_force_does_not_follow_output_symlinks(tmp_path: Path, capsys) -> None:
    output = tmp_path / "demo"
    assert main(_demo_args(output)) == 0
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me", encoding="utf-8")
    report = output / "report.md"
    report.unlink()
    report.symlink_to(victim)

    assert main(_demo_args(output, "--force")) == 2
    assert "non-regular output" in capsys.readouterr().err
    assert victim.read_text(encoding="utf-8") == "keep me"


def test_connector_capture_help_uses_connector_specific_source_date(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["connector", "capture", "--help"])

    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    normalized = " ".join(output.split())
    assert "inclusive source date" in normalized
    assert "semantics are connector-specific" in normalized
    assert "inclusive value date" not in normalized


def test_connector_list_is_offline_deterministic(tmp_path: Path, monkeypatch, capsys) -> None:
    def forbidden_socket(*args, **kwargs):
        raise AssertionError("connector list attempted to open a network socket")

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    monkeypatch.chdir(tmp_path)

    assert main(["connector", "list"]) == 0
    first = capsys.readouterr().out
    assert main(["connector", "list"]) == 0
    second = capsys.readouterr().out

    assert first == second
    assert "Built-in review trust is not a third-party sandbox." in first
    assert "fed-h41-release v0.2.0" in first
    assert "frbny-sofr v0.1.0" in first
    assert "treasury-debt-to-penny v0.1.0" in first
    assert "Source name: Board of Governors of the Federal Reserve System" in first
    assert "Source name: Federal Reserve Bank of New York" in first
    assert "Source name: U.S. Department of the Treasury, Bureau of the Fiscal Service" in first
    assert not tuple(tmp_path.iterdir())


def test_connector_list_json_command(capsys) -> None:
    assert main(["connector", "list", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["trust_notice"] == "Built-in review trust is not a third-party sandbox."
    assert [item["connector_id"] for item in data["connectors"]] == [
        "fed-h41-release",
        "frbny-sofr",
        "treasury-debt-to-penny",
    ]
    h41 = data["connectors"][0]
    assert h41 == {
        "allowed_hosts": ["www.federalreserve.gov"],
        "capture_modes": ["online", "recording"],
        "connector_id": "fed-h41-release",
        "documentation_link": "https://www.federalreserve.gov/disclaimer.htm",
        "redistribution_status": "restricted",
        "source_name": "Board of Governors of the Federal Reserve System",
        "version": "0.2.0",
    }
    treasury = data["connectors"][2]
    assert treasury == {
        "allowed_hosts": ["api.fiscaldata.treasury.gov"],
        "capture_modes": ["online", "recording"],
        "connector_id": "treasury-debt-to-penny",
        "documentation_link": "https://fiscaldata.treasury.gov/api-documentation/",
        "redistribution_status": "allowed",
        "source_name": ("U.S. Department of the Treasury, Bureau of the Fiscal Service"),
        "version": "0.1.0",
    }
