from __future__ import annotations

import calendar
import json
import socket
from datetime import date, timedelta
from pathlib import Path

import pytest

from openmacrostate.api.v1.errors import ContractError
from openmacrostate.connectors.fed_h41_release import FedH41ReleaseConnector
from openmacrostate.runtime.brief import EXPERIMENTAL_FORMAT, build_h41_brief
from openmacrostate.runtime.case import CaseEvaluation, evaluate_case
from openmacrostate.runtime.connectors import run_connector
from openmacrostate.runtime.http import RecordedHttpTransport
from openmacrostate.runtime.jsonio import canonical_json_bytes, sha256_bytes

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "connectors" / "fed_h41_release"
CORE_TIME = "2026-08-09T17:30:00Z"
LATER_TIME = "2026-08-09T17:31:00Z"


def _capture(
    output: Path,
    *,
    core_time: str = CORE_TIME,
    release_date: str = "2023-03-16",
    replacements: tuple[tuple[str, str], ...] = (),
) -> CaseEvaluation:
    """Recapture changed test bytes through the real recording/connector boundary."""
    release = date.fromisoformat(release_date)
    observed = release - timedelta(days=1)
    text = (FIXTURE / "response.html").read_text(encoding="utf-8")
    text = text.replace(
        "Thursday, March 16, 2023",
        f"{calendar.day_name[release.weekday()]}, "
        f"{calendar.month_name[release.month]} {release.day}, {release.year}",
    ).replace(
        "Mar 15, 2023", f"{calendar.month_abbr[observed.month]} {observed.day}, {observed.year}"
    )
    for old, new in replacements:
        assert old in text
        text = text.replace(old, new)
    body = text.encode("utf-8")
    directory = output.with_name(output.name + "-recording")
    directory.mkdir()
    (directory / "response.html").write_bytes(body)
    recording = json.loads((FIXTURE / "recording.json").read_text(encoding="utf-8"))
    url = f"https://www.federalreserve.gov/releases/h41/{release:%Y%m%d}/h41.htm"
    recording["request"]["url"] = url
    recording["response"].update(
        final_url=url,
        byte_length=len(body),
        sha256=sha256_bytes(body),
    )
    recording_path = directory / "recording.json"
    recording_path.write_text(json.dumps(recording) + "\n", encoding="utf-8")
    result = run_connector(
        FedH41ReleaseConnector(),
        {"start": release_date, "end": release_date},
        RecordedHttpTransport(recording_path),
        output,
        protected_paths=(directory,),
        clock=lambda: core_time,
    )
    return evaluate_case(result.case_dir)


def _rehash(case_dir: Path) -> None:
    path = case_dir / "checksums" / "sha256.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        data = (case_dir / entry["path"]).read_bytes()
        entry.update(bytes=len(data), sha256=sha256_bytes(data))
    path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")


def _row(report: dict, key: str) -> dict:
    return next(row for row in report["rows"] if row["key"] == key)


def test_h41_brief_is_read_only_offline_and_bound_to_verified_capture(
    tmp_path, monkeypatch
) -> None:
    current = _capture(tmp_path / "current")
    before = {path: path.read_bytes() for path in current.case_dir.rglob("*") if path.is_file()}

    def forbidden_socket(*args, **kwargs):
        raise AssertionError("brief attempted to open a network socket")

    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        if "reveals" in path.parts:
            raise AssertionError("brief attempted to read a reveal")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", forbidden_socket)
    monkeypatch.setattr(Path, "open", guarded_open)
    report = build_h41_brief(current)
    assert report == build_h41_brief(current)
    assert report["format"] == EXPERIMENTAL_FORMAT
    assert report["passed"] is True
    assert report["historical_evidence"] is False
    assert report["historical_version_authenticated"] is False
    assert report["causal_interpretation"] is False
    assert report["previous"] is None
    assert report["comparison"]["kind"] == "single_capture"
    assert report["comparison"]["interval_days"] is None
    meta = report["current"]
    assert meta["source_url"] == "https://www.federalreserve.gov/releases/h41/20230316/h41.htm"
    assert meta["observed_at"] == "2023-03-15T00:00:00Z"
    assert meta["ingested_at"] == meta["information_cutoff"] == CORE_TIME
    assert meta["snapshot_sha256"] == current.snapshot()["content_sha256"]
    assert meta["source_authentication"] == "unverified_recording"
    assert meta["capture_mode"] == "recorded"
    assert meta["recording_kind"] == "test_only_excerpt"
    assert meta["source_attribution"] == "Board of Governors of the Federal Reserve System"
    assert meta["source_terms_url"] == "https://www.federalreserve.gov/disclaimer.htm"
    assert meta["redistribution_status"] == "restricted"
    assert meta["artifact_id"] == "artifact:sha256:" + meta["artifact_sha256"]
    assert meta["audit"]["residual"] == "0"
    assert meta["audit"]["tolerance"] == "1"
    assert len(meta["audit"]["checks"]) == 3
    assert len(report["rows"]) == 7
    assert _row(report, "total_assets")["current_value"] == "8639300"
    assert _row(report, "primary_credit")["source_cell_id"] == "t1r16c5"
    assert _row(report, "total_capital")["row_locator"] == "Total capital"
    assert all(row["previous_value"] is None and row["delta"] is None for row in report["rows"])
    assert all(row["status"] == "single_capture" for row in report["rows"])
    canonical_json_bytes(report)
    assert before == {
        path: path.read_bytes() for path in current.case_dir.rglob("*") if path.is_file()
    }


@pytest.mark.parametrize(("release_date", "days"), [("2023-03-23", "7"), ("2023-03-30", "14")])
def test_new_period_compares_exact_values_and_reports_actual_interval(
    tmp_path: Path, release_date: str, days: str
) -> None:
    previous = _capture(tmp_path / "previous")
    current = _capture(
        tmp_path / "current",
        core_time=LATER_TIME,
        release_date=release_date,
        replacements=(("152,853", "152,855"), ("277,643", "277,640")),
    )
    report = build_h41_brief(current, previous)
    assert report["comparison"]["kind"] == "new_period"
    assert report["comparison"]["interval_days"] == days
    assert report["comparison"]["exactly_seven_days"] is (days == "7")
    assert _row(report, "primary_credit")["delta"] == "2"
    assert _row(report, "primary_credit")["status"] == "increased"
    assert _row(report, "treasury_general_account")["delta"] == "-3"
    assert _row(report, "treasury_general_account")["status"] == "decreased"
    assert _row(report, "total_assets")["delta"] == "0"
    assert (
        _row(report, "total_assets")["previous_observation_id"]
        != _row(report, "total_assets")["current_observation_id"]
    )
    assert "revision" not in report["comparison"]["label"].lower()


@pytest.mark.parametrize(
    ("replacements", "kind"),
    [
        ((("152,853", "152,852"),), "same_period_values_changed"),
        (
            (("</body>", "<!-- capture test annotation -->\n</body>"),),
            "same_period_artifact_changed",
        ),
        ((), "identical"),
    ],
)
def test_same_period_classifies_values_bytes_and_unchanged_recapture(
    tmp_path: Path, replacements: tuple[tuple[str, str], ...], kind: str
) -> None:
    previous = _capture(tmp_path / "previous")
    current = _capture(tmp_path / "current", core_time=LATER_TIME, replacements=replacements)
    report = build_h41_brief(current, previous)
    assert report["comparison"]["kind"] == kind
    assert report["comparison"]["interval_days"] == "0"
    assert report["comparison"]["exactly_seven_days"] is False
    assert report["current"]["case_id"] != report["previous"]["case_id"]
    assert report["current"]["ingested_at"] != report["previous"]["ingested_at"]
    if kind == "same_period_values_changed":
        assert _row(report, "primary_credit")["delta"] == "-1"
    else:
        assert all(row["delta"] == "0" for row in report["rows"])
    if kind == "identical":
        assert report["comparison"]["label"] == "No change in source bytes or selected values"
    assert "revision" not in report["comparison"]["label"].lower()


@pytest.mark.parametrize("failed_input", ["current", "previous"])
def test_accounting_failure_is_preserved_without_hiding_the_brief(tmp_path, failed_input) -> None:
    bad_replacements = (("8,639,300", "8,639,302"),)
    previous = _capture(
        tmp_path / "previous", replacements=bad_replacements if failed_input == "previous" else ()
    )
    current = _capture(
        tmp_path / "current",
        core_time=LATER_TIME,
        replacements=bad_replacements if failed_input == "current" else (),
    )
    report = build_h41_brief(current, previous)
    assert report["passed"] is False
    assert report[failed_input]["audit"]["passed"] is False
    assert report[failed_input]["audit"]["residual"] == "2"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("unit", "must use USD_million"),
        ("source", "unexpected source_id"),
        ("boundary", "unexpected accounting metadata"),
        ("missing", "exactly the seven"),
        ("duplicate", "exactly the seven"),
        ("multiple_periods", "one unique observed_at"),
        ("quarantined", "without quarantined"),
        ("value", "does not exactly match"),
    ],
)
def test_brief_rejects_invalid_capture_evidence_after_checksums_are_refreshed(
    tmp_path: Path, mutation: str, message: str
) -> None:
    original = _capture(tmp_path / "current")
    case_dir = original.case_dir
    path = case_dir / "inputs" / "observations.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if mutation == "unit":
        records[0]["unit"] = "USD"
    elif mutation == "source":
        for record in records:
            record["source_id"] = "unexpected.source"
        artifact_path = case_dir / "inputs" / "artifacts.jsonl"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        artifact["source_id"] = "unexpected.source"
        artifact_path.write_text(json.dumps(artifact) + "\n", encoding="utf-8")
    elif mutation == "boundary":
        records[0]["extensions"]["org.openmacrostate.accounting"]["boundary_id"] = "other.boundary"
    elif mutation == "missing":
        records.pop()
    elif mutation == "duplicate":
        records.append({**records[0], "observation_id": "obs:duplicate"})
    elif mutation == "multiple_periods":
        records[0]["observed_at"] = "2023-03-08T00:00:00Z"
    elif mutation == "quarantined":
        case_path = case_dir / "case.json"
        case = json.loads(case_path.read_text(encoding="utf-8"))
        case["information_cutoff"] = "2026-08-09T17:29:00Z"
        case_path.write_text(json.dumps(case) + "\n", encoding="utf-8")
    else:
        records[0]["value"] = "8639301"
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    _rehash(case_dir)
    altered = evaluate_case(case_dir)
    with pytest.raises(ContractError, match=message):
        build_h41_brief(altered)


def test_brief_rehashes_source_even_after_evaluation(tmp_path: Path) -> None:
    current = _capture(tmp_path / "current")
    path = current.case_dir / current.artifacts[0]["storage_uri"]
    body = path.read_bytes().replace(b"152,853", b"152,854")
    path.write_bytes(body)
    with pytest.raises(ContractError, match="SHA-256 does not match"):
        build_h41_brief(current)


def test_previous_capture_must_pass_the_same_strict_evidence_checks(tmp_path: Path) -> None:
    previous = _capture(tmp_path / "previous")
    current = _capture(tmp_path / "current", core_time=LATER_TIME)
    path = previous.case_dir / "inputs" / "observations.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    records[0]["unit"] = "USD"
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    _rehash(previous.case_dir)
    with pytest.raises(ContractError, match="must use USD_million"):
        build_h41_brief(current, evaluate_case(previous.case_dir))


@pytest.mark.parametrize("reverse", ["observation_period", "capture_time"])
def test_brief_rejects_reverse_previous(tmp_path: Path, reverse: str) -> None:
    current = _capture(tmp_path / "current")
    previous = _capture(
        tmp_path / "previous",
        core_time=LATER_TIME if reverse != "observation_period" else CORE_TIME,
        release_date="2023-03-23" if reverse == "observation_period" else "2023-03-16",
    )
    with pytest.raises(ContractError, match="must not follow current"):
        build_h41_brief(current, previous)


def test_new_period_allows_previous_observation_to_be_captured_later(tmp_path: Path) -> None:
    current = _capture(
        tmp_path / "current",
        release_date="2023-03-23",
        replacements=(("152,853", "152,855"),),
    )
    previous = _capture(tmp_path / "previous", core_time=LATER_TIME)
    report = build_h41_brief(current, previous)
    assert report["comparison"]["kind"] == "new_period"
    assert report["comparison"]["interval_days"] == "7"
    assert report["current"]["observed_at"] > report["previous"]["observed_at"]
    assert report["current"]["ingested_at"] < report["previous"]["ingested_at"]
    assert _row(report, "primary_credit")["delta"] == "2"
    assert report["current"]["audit"]["passed"] is True
    assert report["previous"]["audit"]["passed"] is True
    assert report["historical_evidence"] is False
    assert report["historical_version_authenticated"] is False
