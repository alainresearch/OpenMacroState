from __future__ import annotations

import json
import socket
from pathlib import Path

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


def test_connector_list_command(capsys) -> None:
    assert main(["connector", "list"]) == 0
    stdout = capsys.readouterr().out
    assert "Built-in review trust is not a third-party sandbox." in stdout
    assert "frbny-sofr v0.1.0" in stdout
    assert "Source name: Federal Reserve Bank of New York" in stdout
    assert "Allowed host: markets.newyorkfed.org" in stdout
    assert "Capture modes: online, recording" in stdout
    assert "Redistribution status: restricted" in stdout
    assert "Documentation link: https://www.newyorkfed.org/privacy/termsofuse.html" in stdout


def test_connector_list_json_command(capsys) -> None:
    assert main(["connector", "list", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["trust_notice"] == "Built-in review trust is not a third-party sandbox."
    connectors = data["connectors"]
    assert len(connectors) >= 1
    frbny = next(c for c in connectors if c["connector_id"] == "frbny-sofr")
    assert frbny["version"] == "0.1.0"
    assert frbny["source_name"] == "Federal Reserve Bank of New York"
    assert frbny["allowed_hosts"] == ["markets.newyorkfed.org"]
    assert frbny["capture_modes"] == ["online", "recording"]
    assert frbny["redistribution_status"] == "restricted"
    assert frbny["documentation_link"] == "https://www.newyorkfed.org/privacy/termsofuse.html"
