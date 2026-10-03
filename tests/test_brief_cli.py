from __future__ import annotations

import csv
import json
import socket
from hashlib import sha256
from pathlib import Path

import pytest

from openmacrostate.cli import main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "connectors" / "fed_h41_release"


def _capture(case: Path, *extra: str, recording: Path | None = None) -> int:
    return main(
        [
            "connector",
            "capture",
            "fed-h41-release",
            "--start",
            "2023-03-16",
            "--end",
            "2023-03-16",
            "--recording",
            str(recording or FIXTURE / "recording.json"),
            "--output",
            str(case),
            *extra,
        ]
    )


def _files(directory: Path) -> dict[str, str]:
    return {
        str(path.relative_to(directory)): sha256(path.read_bytes()).hexdigest()
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_capture_and_brief_are_offline_and_keep_inputs_frozen(tmp_path, monkeypatch, capsys):
    def no_network(*args, **kwargs):
        raise AssertionError("brief attempted to open a network socket")

    monkeypatch.setattr(socket, "socket", no_network)
    case = tmp_path / "capture"
    first = tmp_path / "first-brief"
    fixture_before = _files(FIXTURE)
    assert _capture(case, "--brief-output", str(first)) == 0
    assert "OPEN " in capsys.readouterr().out
    expected = {"index.html", "observations.csv", "brief.md", "brief.json"}
    assert {path.name for path in first.iterdir()} == expected
    report = json.loads((first / "brief.json").read_text())
    assert report["comparison"]["kind"] == "single_capture"
    assert report["passed"] is True
    assert len(report["rows"]) == 7
    with (first / "observations.csv").open(encoding="utf-8-sig", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 7
    before = _files(case)
    second = tmp_path / "second-brief"
    assert main(["brief", "h41", str(case), "--output", str(second)]) == 0
    assert _files(case) == before
    assert _files(FIXTURE) == fixture_before
    assert _files(first) == _files(second)


def test_compare_captures_and_refuse_overwrite(tmp_path, capsys):
    previous = tmp_path / "previous"
    current = tmp_path / "current"
    assert _capture(previous) == 0
    assert _capture(current) == 0
    output = tmp_path / "comparison"
    command = ["brief", "h41", str(current), "--previous", str(previous), "--output", str(output)]
    assert main(command) == 0
    report = json.loads((output / "brief.json").read_text())
    assert report["comparison"]["kind"] == "identical"
    assert all(row["delta"] == "0" for row in report["rows"])
    before = _files(output)
    assert main(command) == 2
    assert "already exists" in capsys.readouterr().err
    assert _files(output) == before


def test_brief_rejects_tampered_capture_without_creating_output(tmp_path, capsys):
    case = tmp_path / "capture"
    assert _capture(case) == 0
    observations = case / "inputs" / "observations.jsonl"
    observations.write_text(observations.read_text() + "\n")
    output = tmp_path / "brief"
    assert main(["brief", "h41", str(case), "--output", str(output)]) == 2
    assert "ERROR:" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("inside_previous", [False, True])
def test_brief_cannot_write_inside_either_input(tmp_path, inside_previous):
    previous = tmp_path / "previous"
    current = tmp_path / "current"
    assert _capture(previous) == 0
    assert _capture(current) == 0
    output = (previous if inside_previous else current) / "brief"
    before = (_files(previous), _files(current))
    assert (
        main(["brief", "h41", str(current), "--previous", str(previous), "--output", str(output)])
        == 2
    )
    assert not output.exists()
    assert (_files(previous), _files(current)) == before


def test_brief_refuses_symbolic_link_output(tmp_path):
    case = tmp_path / "capture"
    assert _capture(case) == 0
    link = tmp_path / "brief"
    target = tmp_path / "target"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links are unavailable")
    assert main(["brief", "h41", str(case), "--output", str(link)]) == 2
    assert link.is_symlink()
    assert not target.exists()


def test_capture_preflights_brief_destination(tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    case = tmp_path / "capture"
    assert _capture(case, "--brief-output", str(output)) == 2
    assert not case.exists()


def test_brief_flag_rejects_other_connectors_before_network(tmp_path, monkeypatch, capsys):
    def no_network(*args, **kwargs):
        raise AssertionError("unsupported brief opened a socket")

    monkeypatch.setattr(socket, "socket", no_network)
    assert (
        main(
            [
                "connector",
                "capture",
                "frbny-sofr",
                "--start",
                "2023-03-22",
                "--end",
                "2023-03-22",
                "--online",
                "--output",
                str(tmp_path / "capture"),
                "--brief-output",
                str(tmp_path / "brief"),
            ]
        )
        == 2
    )
    assert "only for fed-h41-release" in capsys.readouterr().err
    assert not (tmp_path / "capture").exists()


def test_failed_accounting_is_exported_with_failure_exit_status(tmp_path, capsys):
    recording_dir = tmp_path / "recording"
    recording_dir.mkdir()
    body = (FIXTURE / "response.html").read_bytes().replace(b"8,639,300", b"8,639,400")
    (recording_dir / "response.html").write_bytes(body)
    recording = json.loads((FIXTURE / "recording.json").read_text())
    recording["response"]["byte_length"] = len(body)
    recording["response"]["sha256"] = sha256(body).hexdigest()
    path = recording_dir / "recording.json"
    path.write_text(json.dumps(recording))
    brief = tmp_path / "brief"
    assert _capture(tmp_path / "capture", "--brief-output", str(brief), recording=path) == 2
    report = json.loads((brief / "brief.json").read_text())
    assert report["passed"] is False
    assert report["current"]["audit"]["residual"] == "100"
    assert "FAIL H.4.1 brief" in capsys.readouterr().out
