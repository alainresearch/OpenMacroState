from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
from copy import deepcopy
from html.parser import HTMLParser
from typing import Any

import pytest

from openmacrostate.api.v1.errors import ContractError
from openmacrostate.runtime.brief_render import (
    render_brief_csv,
    render_brief_html,
    render_brief_markdown,
)


@pytest.fixture
def report() -> dict[str, Any]:
    current = {
        "case_id": "h41-current",
        "source_id": "federal.reserve.board.h41.dated_release",
        "source_url": "https://www.federalreserve.gov/releases/h41/20230316/h41.htm",
        "artifact_id": "artifact:sha256:" + "a" * 64,
        "artifact_sha256": "a" * 64,
        "source_authentication": "unverified_recording",
        "capture_mode": "recorded",
        "recording_kind": "test_only_excerpt",
        "observed_at": "2023-03-15T00:00:00Z",
        "released_at": "2023-03-16T20:30:00Z",
        "vintage_at": "2023-03-16T20:30:00Z",
        "ingested_at": "2026-08-09T17:30:00Z",
        "information_cutoff": "2026-08-09T17:30:00Z",
        "snapshot_sha256": "b" * 64,
        "connector_ruleset_version": "fed-h41-release-normalization/3",
        "unit": "USD_million",
        "boundary_id": "us.federal_reserve_banks.consolidated",
        "historical_evidence": False,
        "historical_version_authenticated": False,
        "source_attribution": "Board of Governors of the Federal Reserve System",
        "source_terms_url": "https://www.federalreserve.gov/foia/about_foia.htm",
        "redistribution_status": "unknown",
        "audit": {
            "passed": True,
            "residual": "0",
            "tolerance": "1",
            "audit_sha256": "c" * 64,
            "checks": [
                {
                    "check_id": "assets_equal_liabilities_plus_capital",
                    "expression": "total_assets = total_liabilities + total_capital",
                    "residual": "0",
                    "tolerance": "1",
                    "comparison": "absolute_residual_lte_tolerance",
                    "passed": True,
                }
            ],
        },
    }
    measures = [
        ("total_assets", "8639300"),
        ("total_liabilities", "8596799"),
        ("total_capital", "42501"),
        ("securities_held_outright", "7939954"),
        ("primary_credit", "152913"),
        ("treasury_general_account", "278392"),
        ("reserve_balances", "3443459"),
    ]
    rows = [
        {
            "key": key,
            "label": key,
            "series_id": "fed.h41." + key,
            "table": "Table 5" if index < 3 else "Table 1",
            "row_locator": key.replace("_", " "),
            "source_cell_id": f"t7r{index + 1}c3",
            "previous_source_cell_id": None,
            "unit": "USD_million",
            "current_value": value,
            "previous_value": None,
            "delta": None,
            "status": "single_capture",
            "current_observation_id": "obs:" + key,
            "previous_observation_id": None,
        }
        for index, (key, value) in enumerate(measures)
    ]
    return {
        "format": "experimental/openmacrostate-h41-brief/1",
        "passed": True,
        "current": current,
        "previous": None,
        "comparison": {
            "kind": "single_capture",
            "interval_days": None,
            "exactly_seven_days": None,
            "label": "Single capture",
        },
        "rows": rows,
    }


def _add_previous(report: dict[str, Any]) -> None:
    previous = deepcopy(report["current"])
    previous["observed_at"] = "2023-03-08T00:00:00Z"
    previous["case_id"] = "h41-previous"
    report["previous"] = previous
    report["comparison"] = {
        "kind": "new_period",
        "interval_days": "7",
        "exactly_seven_days": True,
        "label": "New period",
    }
    for row in report["rows"]:
        row.update(
            previous_value=str(int(row["current_value"]) + 123),
            delta="-123",
            status="decreased",
            previous_observation_id="old:" + row["key"],
            previous_source_cell_id=row["source_cell_id"],
        )


class _Tags(HTMLParser):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.feed(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))


def test_csv_exports_exact_integers_and_negative_changes(report: dict[str, Any]) -> None:
    _add_previous(report)
    report["rows"][0].update(
        current_value="999999999999999", previous_value="999999999999998", delta="1"
    )
    rows = list(csv.DictReader(io.StringIO(render_brief_csv(report))))
    assert len(rows) == 7
    assert rows[0]["current_value"] == "999999999999999"
    assert rows[0]["previous_value"] == "999999999999998"
    assert rows[0]["delta"] == "1"
    assert rows[1]["delta"] == "-123"
    assert {row["unit"] for row in rows} == {"USD_million"}
    assert all(row["previous_observed_at"] == "2023-03-08T00:00:00Z" for row in rows)
    for row in rows:
        for side in ("current", "previous"):
            assert row[f"{side}_recording_kind"] == "test_only_excerpt"
            assert row[f"{side}_source_authentication"] == "unverified_recording"
            assert row[f"{side}_historical_version_authenticated"] == "false"
            assert row[f"{side}_audit_passed"] == "true"
            assert row[f"{side}_artifact_sha256"] == "a" * 64
            assert row[f"{side}_source_attribution"].startswith("Board of Governors")
            assert row[f"{side}_source_terms_url"].startswith("https://www.federalreserve.gov/")
    assert "999,999,999,999,999" in render_brief_html(report)
    assert "999999999999999" in render_brief_markdown(report)


@pytest.mark.parametrize("payload", ["=1+1", "+SUM(A1:A2)", "-2+3", "@SUM(A1)", " \t=1+1"])
def test_csv_protects_text_formulas_without_changing_numbers(
    report: dict[str, Any], payload: str
) -> None:
    _add_previous(report)
    report["rows"][0]["series_id"] = payload
    report["rows"][0]["row_locator"] = payload
    report["current"]["source_url"] = payload
    row = next(csv.DictReader(io.StringIO(render_brief_csv(report))))
    assert row["series_id"] == "'" + payload
    assert row["row_locator"] == "'" + payload
    assert row["current_source_url"] == "'" + payload
    assert row["delta"] == "-123"


@pytest.mark.parametrize("value", [1.0, "1.0", "1e6", "=1+1", "+3", "01"])
def test_renderers_reject_non_integer_amounts(report: dict[str, Any], value: object) -> None:
    report["rows"][0]["current_value"] = value
    for renderer in (render_brief_csv, render_brief_html, render_brief_markdown):
        with pytest.raises(ContractError, match="canonical integer"):
            renderer(report)


def test_single_capture_does_not_invent_changes(report: dict[str, Any]) -> None:
    rendered = render_brief_html(report)
    assert "No previous values or changes have been inferred" in rendered
    assert "oms brief h41 CURRENT_CASE --previous PREVIOUS_CASE --output BRIEF_DIR" in rendered
    assert rendered.count('class="data-row"') == 7
    assert rendered.count('class="number delta">—') == 7
    assert "Test excerpt — not a complete source release" in rendered
    assert "Historical availability</dt><dd>Not authenticated" in rendered
    for row in csv.DictReader(io.StringIO(render_brief_csv(report))):
        assert row["previous_value"] == ""
        assert row["delta"] == ""
    markdown = render_brief_markdown(report)
    assert "test-only excerpt" in markdown
    assert "historical availability" in markdown
    assert "--previous PREVIOUS_CASE" in markdown


def test_failed_previous_audit_is_prominent(report: dict[str, Any]) -> None:
    _add_previous(report)
    report["passed"] = False
    report["previous"]["audit"]["passed"] = False
    report["previous"]["audit"]["checks"][0].update(passed=False, residual="5")
    rendered = render_brief_html(report)
    assert 'class="notice fail" role="alert"' in rendered
    assert "FAIL — accounting checks" in rendered
    assert 'class="failed-check"' in rendered
    assert "residual 5" in rendered
    assert "**Accounting checks: FAIL.**" in render_brief_markdown(report)
    row = next(csv.DictReader(io.StringIO(render_brief_csv(report))))
    assert row["current_audit_passed"] == "true"
    assert row["previous_audit_passed"] == "false"


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "http://www.federalreserve.gov/releases/h41/20230316/h41.htm",
        "https://www.federalreserve.gov.evil.test/releases/h41/20230316/h41.htm",
        "https://www.federalreserve.gov@evil.test/releases/h41/20230316/h41.htm",
        'https://www.federalreserve.gov/releases/h41/20230316/h41.htm" onclick="alert(1)',
        "https://www.federalreserve.gov/releases/h41/20230316/h41.htm?external=evil",
    ],
)
def test_unsafe_source_urls_are_never_links(report: dict[str, Any], url: str) -> None:
    report["current"]["source_url"] = url
    tags = _Tags(render_brief_html(report)).tags
    assert [attrs["href"] for tag, attrs in tags if tag == "a"] == ["observations.csv", "brief.md"]


def test_html_escapes_variable_content_and_links_only_exact_source(report: dict[str, Any]) -> None:
    attack = '</textarea><script>alert(1)</script><img src=x onerror="alert(1)">'
    report["current"]["case_id"] = attack
    report["current"]["license"] = {"name": attack}
    report["rows"][0]["row_locator"] = attack
    report["rows"][0]["current_observation_id"] = attack
    report["rows"][0]["source_cell_id"] = 'bad" onclick="alert(1)'
    rendered = render_brief_html(report)
    tags = _Tags(rendered).tags
    assert sum(tag == "script" for tag, _ in tags) == 1
    assert not any(tag in {"img", "iframe", "link"} for tag, _ in tags)
    assert not any(key.startswith("on") for _, attrs in tags for key in attrs)
    assert "&lt;/textarea&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    links = [attrs["href"] for tag, attrs in tags if tag == "a"]
    assert report["current"]["source_url"] in links
    assert report["current"]["source_url"] + "#t7r2c3" in links
    assert "<img" not in render_brief_markdown(report)


def test_csp_only_allows_constant_hashed_script_and_style(report: dict[str, Any]) -> None:
    rendered = render_brief_html(report)
    csp = next(
        attrs["content"]
        for tag, attrs in _Tags(rendered).tags
        if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy"
    )
    assert csp is not None
    assert "default-src 'none'" in csp
    assert "connect-src 'none'" in csp
    assert "unsafe-inline" not in csp
    for tag in ("script", "style"):
        content = re.search(f"<{tag}>(.*?)</{tag}>", rendered, re.DOTALL)
        assert content is not None
        digest = base64.b64encode(hashlib.sha256(content[1].encode()).digest()).decode()
        assert f"{tag}-src 'sha256-{digest}'" in csp
    assert "@media print" in rendered
    assert "@media(max-width:650px)" in rendered


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("same_period_values_changed", "does not authenticate a source revision"),
        ("same_period_artifact_changed", "preserved source bytes differ"),
        ("identical", "Same observation date, values, and preserved source bytes"),
    ],
)
def test_same_period_comparison_wording(report: dict[str, Any], kind: str, expected: str) -> None:
    _add_previous(report)
    report["previous"]["observed_at"] = report["current"]["observed_at"]
    report["comparison"].update(kind=kind, interval_days="0", exactly_seven_days=False)
    assert expected in render_brief_html(report)
    assert expected in render_brief_markdown(report)


@pytest.mark.parametrize("mode", ["success", "denied", "unavailable"])
def test_copy_table_has_selectable_fallback_behavior(report: dict[str, Any], mode: str) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("optional JavaScript behavior check requires Node.js")
    rendered = render_brief_html(report)
    script = re.search(r"<script>(.*?)</script>", rendered, re.DOTALL)
    assert script is not None
    harness = r"""
const vm = require("node:vm");
let listener;
let copied;
const nodes = {
  "copy-table": {hidden: true, addEventListener: (name, fn) => {listener = fn;}},
  "copy-data": {value: "label\tvalue\nAssets\t8639300", focus() {this.focused = true;},
                select() {this.selected = true;}},
  "copy-fallback": {hidden: true}, "copy-status": {textContent: ""}
};
const navigator = MODE === "unavailable" ? {} : {clipboard: {writeText: async text => {
  if (MODE === "denied") throw Error("clipboard denied");
  copied = text;
}}};
vm.runInNewContext(SCRIPT, {document: {getElementById: id => nodes[id]}, navigator});
(async () => {
  await listener();
  console.log(JSON.stringify({visibleButton: !nodes["copy-table"].hidden,
    fallback: !nodes["copy-fallback"].hidden, selected: !!nodes["copy-data"].selected,
    focused: !!nodes["copy-data"].focused, copied,
    status: nodes["copy-status"].textContent}));
})();
"""
    result = subprocess.run(
        [
            node,
            "-e",
            "const MODE = "
            + json.dumps(mode)
            + "; const SCRIPT = "
            + json.dumps(script[1])
            + ";\n"
            + harness,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    state = json.loads(result.stdout)
    assert state["visibleButton"] is True
    if mode == "success":
        assert state["fallback"] is False
        assert state["copied"] == "label\tvalue\nAssets\t8639300"
        assert state["status"] == "Table copied."
    else:
        assert state["fallback"] is True
        assert state["selected"] is True
        assert state["focused"] is True
        assert state["status"] == "Select and copy the table below."
