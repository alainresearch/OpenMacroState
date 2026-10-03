"""Offline, escaped presentation of the experimental H.4.1 brief contract."""

from __future__ import annotations

import base64
import csv
import hashlib
import html
import io
import json
import re
from collections.abc import Mapping
from typing import Any

from openmacrostate.api.v1.errors import ContractError

_LABELS = {
    "total_assets": "Total assets",
    "total_liabilities": "Total liabilities",
    "total_capital": "Total capital",
    "securities_held_outright": "Securities held outright",
    "primary_credit": "Primary credit",
    "treasury_general_account": "Treasury General Account",
    "reserve_balances": "Reserve balances",
}
_INTEGER = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")
_SOURCE_URL = re.compile(r"https://www\.federalreserve\.gov/releases/h41/[0-9]{8}/h41\.htm\Z")
_CELL = re.compile(r"t[0-9]+r[0-9]+c[0-9]+\Z")
_CSV_CAPTURE_FIELDS = (
    "case_id",
    "observed_at",
    "source_url",
    "artifact_sha256",
    "ingested_at",
    "source_authentication",
    "recording_kind",
    "historical_version_authenticated",
    "audit_passed",
    "source_attribution",
    "source_terms_url",
    "redistribution_status",
)
_PREVIOUS_HELP = "oms brief h41 CURRENT_CASE --previous PREVIOUS_CASE --output BRIEF_DIR"
_LIMITATION = (
    "Checks establish consistency with the preserved bytes. They do not establish "
    "historical availability, authenticate a historical version, or explain economic causes."
)
_STYLE = """
:root{color-scheme:light;--paper:#f5f4ee;--ink:#203c33;--muted:#64736a;
--line:#d7ddd4;--warn:#785014;--danger:#922f29}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1100px;margin:auto;padding:40px 44px 30px}a{color:inherit;
text-underline-offset:3px}button,.download{font:inherit;border:1px solid var(--ink);
padding:9px 15px;border-radius:5px;background:transparent;color:var(--ink);
cursor:pointer;text-decoration:none}button{background:var(--ink);color:white}
button:focus-visible,a:focus-visible,summary:focus-visible,textarea:focus-visible{
outline:3px solid #c8a65d;outline-offset:4px}[hidden]{display:none!important}
.masthead{display:flex;justify-content:space-between;gap:20px;border-bottom:2px solid
var(--ink);padding-bottom:16px;font-size:11px;letter-spacing:.14em;text-transform:uppercase}
.brand{font-weight:750}.edition{color:var(--muted)}.eyebrow{font-size:11px;
letter-spacing:.13em;text-transform:uppercase;margin:34px 0 9px;color:var(--muted)}
h1{font:normal clamp(32px,4.7vw,53px)/1.08 Georgia,"Times New Roman",serif;
letter-spacing:-.035em;margin:0;max-width:810px}h2{font:normal 26px/1.2 Georgia,serif;
margin:0}h3{font-size:14px;margin:0 0 10px}.lede{color:var(--muted);margin:14px 0 23px}
.dates{display:flex;flex-wrap:wrap;gap:20px 50px;margin:0 0 26px}.dates dt,
.meta dt{color:var(--muted);font-size:11px;letter-spacing:.035em}.dates dd{margin:2px 0 0;
font-size:19px;font-variant-numeric:tabular-nums}.notice{padding:15px 19px;
border:1px solid #d9cdb5;background:#faf5e9;border-left:4px solid #a27c3a;
color:var(--warn);border-radius:3px;margin:18px 0}.notice strong{display:block;
font-size:14px}.notice p{margin:4px 0 0;font-size:13px}.notice.fail{border-color:#d9aba7;
border-left-color:var(--danger);background:#fff0ed;color:var(--danger)}
.section-head{display:flex;align-items:end;justify-content:space-between;gap:20px;
margin:30px 0 14px}.unit{font-size:12px;color:var(--muted);margin:0}.table-scroll{
overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th{text-align:left;font-size:11px;letter-spacing:.05em;text-transform:uppercase;
color:var(--muted);padding:10px 12px;border-top:1px solid var(--line);
border-bottom:1px solid var(--line)}td{padding:13px 12px 1px}.number{text-align:right;
white-space:nowrap}.data-row td:first-child{font-weight:600}.data-row .number{font-size:19px;
letter-spacing:-.02em}.data-row .previous{color:var(--muted);font-size:16px}
.delta{font-size:16px!important}
.provenance-row td{padding:0 12px 12px;border-bottom:1px solid var(--line)}
summary{cursor:pointer;color:var(--muted);font-size:11px;width:fit-content}
details[open]>summary{margin-bottom:12px}.meta{display:grid;grid-template-columns:
minmax(130px,1fr) minmax(0,3fr);gap:8px 18px;margin:0;font-size:12px;padding:16px;
background:#ecefe7;border-radius:3px}.meta dd{margin:0;overflow-wrap:anywhere}
.meta dt{font-size:12px}.trace-columns{display:grid;grid-template-columns:1fr;gap:14px}
.trace-columns.paired{grid-template-columns:1fr 1fr}.subtle{color:var(--muted);font-size:12px}
.comparison-note{font-size:13px;color:var(--muted);margin:13px 0 0}.missing-previous{
padding:17px 0;color:var(--muted);font-size:13px}.missing-previous p{margin:0 0 8px}
code{font:12px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere}
.toolbar{display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin:23px 0}
.copy-status{font-size:12px;color:var(--muted)}textarea{width:100%;min-height:180px;
background:#fffef9;border:1px solid var(--line);padding:12px;font:12px/1.5 monospace}
.audit{border-top:1px solid var(--line);padding-top:20px;margin-top:30px}
.audit-head{display:flex;gap:15px;align-items:center;flex-wrap:wrap}.badge{font-size:10px;
letter-spacing:.08em;font-weight:700;border:1px solid currentColor;padding:3px 8px;
border-radius:3px}.badge.fail{color:var(--danger)}.audit-list{list-style:none;padding:0;
font-size:12px}.audit-list li{padding:7px 0;border-bottom:1px solid var(--line)}
.check-status{font-weight:700;display:inline-block;min-width:42px}.failed-check{
color:var(--danger)}.provenance{margin-top:24px}.provenance summary{font-size:13px}
footer{border-top:2px solid var(--ink);margin-top:32px;padding-top:15px;
color:var(--muted);font-size:11px;display:flex;justify-content:space-between;gap:20px}
.attribution{font-size:11px;color:var(--muted);overflow-wrap:anywhere}
@media(max-width:650px){main{padding:22px 18px}.masthead{font-size:9px}.edition{
max-width:100px;text-align:right}.eyebrow{margin-top:26px}.dates{gap:16px 30px}
.dates dd{font-size:16px}.section-head{align-items:start;flex-direction:column;gap:7px}
th,td{padding-left:7px;padding-right:7px}th{font-size:9px}.data-row td:first-child{
font-size:12px;min-width:125px}.data-row .number{font-size:15px}.data-row .previous,
.data-row .delta{font-size:13px!important}.trace-columns.paired{grid-template-columns:1fr}
.meta{grid-template-columns:1fr;gap:3px;padding:12px}.meta dd{margin-bottom:8px}
.toolbar{align-items:stretch}button,.download{font-size:12px;padding:9px 11px}}
@media print{body{background:white;font-size:10pt}main{max-width:none;padding:0}
.toolbar,.missing-previous,#copy-fallback,footer .offline-note{display:none!important}
h1{font-size:30pt}.notice{background:white}.data-row .number{font-size:12pt}
.table-scroll{overflow:visible}.audit,.notice{break-inside:avoid}a{text-decoration:none}
details{break-inside:avoid}.meta{background:white}.eyebrow{margin-top:18px}
th,td{padding-top:7px}.provenance-row td{padding-bottom:7px}footer{margin-top:20px}}
"""
_SCRIPT = """
"use strict";
const copyButton = document.getElementById("copy-table");
const copyData = document.getElementById("copy-data");
const copyFallback = document.getElementById("copy-fallback");
const copyStatus = document.getElementById("copy-status");
copyButton.hidden = false;
copyButton.addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(copyData.value);
    copyFallback.hidden = true;
    copyStatus.textContent = "Table copied.";
  } catch {
    copyFallback.hidden = false;
    copyData.focus();
    copyData.select();
    copyStatus.textContent = "Select and copy the table below.";
  }
});
"""


def _text(value: object) -> str:
    if value is None:
        return "Not supplied"
    if isinstance(value, Mapping):
        return json.dumps(dict(value), ensure_ascii=False, sort_keys=True)
    return str(value)


def _escape(value: object) -> str:
    return html.escape(_text(value), quote=True)


def _integer(value: object) -> str:
    if not isinstance(value, str) or not _INTEGER.fullmatch(value):
        raise ContractError("brief amounts must be exact canonical integer strings")
    return value


def _number(value: object, *, signed: bool = False) -> str:
    if value is None:
        return "—"
    amount = int(_integer(value))
    return format(amount, "+,d" if signed and amount else ",d")


def _label(row: Mapping[str, Any]) -> str:
    return _LABELS.get(str(row["key"]), str(row["label"]))


def _source_link(url: object, cell: object = None) -> str:
    rendered = _escape(url)
    if isinstance(url, str) and _SOURCE_URL.fullmatch(url):
        target = url
        if isinstance(cell, str) and _CELL.fullmatch(cell):
            target += "#" + cell
        return f'<a href="{_escape(target)}" rel="noreferrer noopener">{rendered}</a>'
    return rendered


def _csv_text(value: object) -> str:
    text = "" if value is None else str(value)
    if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        text = "'" + text
    return text


def render_brief_csv(report: Mapping[str, Any]) -> str:
    """Export exact observations together with both captures' trust and licensing scope."""
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "label",
            "series_id",
            "unit",
            "current_value",
            "previous_value",
            "delta",
        ]
        + [f"{side}_{field}" for side in ("current", "previous") for field in _CSV_CAPTURE_FIELDS]
        + ["table", "row_locator", "current_observation_id", "previous_observation_id"]
    )
    provenance = []
    for side in ("current", "previous"):
        source = report[side]
        for field in _CSV_CAPTURE_FIELDS:
            if source is None:
                value = ""
            elif field == "audit_passed":
                value = "true" if source["audit"]["passed"] is True else "false"
            elif field == "historical_version_authenticated":
                value = "false"
            else:
                value = source.get(field)
            provenance.append(_csv_text(value))
    for row in report["rows"]:
        writer.writerow(
            [
                _csv_text(_label(row)),
                _csv_text(row["series_id"]),
                "USD_million",
                _integer(row["current_value"]),
                "" if row["previous_value"] is None else _integer(row["previous_value"]),
                "" if row["delta"] is None else _integer(row["delta"]),
            ]
            + provenance
            + [
                _csv_text(row["table"]),
                _csv_text(row["row_locator"]),
                _csv_text(row["current_observation_id"]),
                _csv_text(row["previous_observation_id"]),
            ]
        )
    return output.getvalue()


def _copy_table(report: Mapping[str, Any]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    title, explanation = _trust(report)
    writer.writerow(["H.4.1 brief", _csv_text(title)])
    writer.writerow(["Provenance limits", _csv_text(explanation)])
    writer.writerow(["Historical availability", "Not authenticated"])
    for side in ("current", "previous"):
        source = report[side]
        if source is not None:
            writer.writerow([side.title() + " observation", _csv_text(source["observed_at"])])
            writer.writerow([side.title() + " source", _csv_text(source["source_url"])])
    writer.writerow(["Measure", "Current", "Previous", "Change", "Unit"])
    for row in report["rows"]:
        writer.writerow(
            [_csv_text(_label(row))]
            + [
                "" if row[key] is None else _integer(row[key])
                for key in ("current_value", "previous_value", "delta")
            ]
            + ["USD_million"]
        )
    return output.getvalue()


def _trust(report: Mapping[str, Any]) -> tuple[str, str]:
    sources = [report["current"]]
    if report["previous"] is not None:
        sources.append(report["previous"])
    if any(source["recording_kind"] == "test_only_excerpt" for source in sources):
        return (
            "Test excerpt — not a complete source release",
            "This brief includes a test-only excerpt. Its values demonstrate the workflow; "
            "they are not a complete, authenticated release or a historical research result.",
        )
    if any(source["source_authentication"] != "core_observed_https" for source in sources):
        return (
            "Preserved recording — source not authenticated",
            "The source and receipt time of at least one recording are unauthenticated. "
            "A matching hash establishes consistency with those preserved bytes only.",
        )
    return (
        "Captured over HTTPS — historical version not authenticated",
        "Capture metadata reports core-observed HTTPS acquisition. "
        "This does not establish what was available at an earlier historical cutoff.",
    )


def _comparison_text(report: Mapping[str, Any]) -> str:
    comparison = report["comparison"]
    kind = comparison["kind"]
    if kind == "single_capture":
        return "One capture. No previous values or changes have been inferred."
    if kind == "new_period":
        interval = comparison["interval_days"]
        return (
            f"Change across {interval} days between observation dates. "
            "Current minus previous; no cause is inferred."
        )
    if kind == "same_period_values_changed":
        return (
            "Same observation date; values differ between captures. "
            "This alone does not authenticate a source revision."
        )
    if kind == "same_period_artifact_changed":
        return "Same observation date and values; the preserved source bytes differ."
    return "Same observation date, values, and preserved source bytes."


def _metadata_html(
    metadata: Mapping[str, Any], row: Mapping[str, Any] | None = None, *, previous: bool = False
) -> str:
    fields = [
        ("Case", "case_id"),
        ("Observation date", "observed_at"),
        ("Conservative availability bound", "released_at"),
        ("Captured version bound", "vintage_at"),
        ("Core ingestion time", "ingested_at"),
        ("Information cutoff", "information_cutoff"),
        ("Receipt time claim", "transport_retrieved_at_claim"),
        ("Source authentication", "source_authentication"),
        ("Capture mode", "capture_mode"),
        ("Completeness claim", "recording_kind"),
        ("Source", "source_id"),
        ("Artifact", "artifact_id"),
        ("Artifact SHA-256", "artifact_sha256"),
        ("Snapshot SHA-256", "snapshot_sha256"),
        ("Parser rules", "connector_ruleset_version"),
        ("Accounting boundary", "boundary_id"),
        ("Provenance scope", "provenance_verification_scope"),
        ("Source attribution", "source_attribution"),
        ("Source terms", "source_terms_url"),
        ("Redistribution", "redistribution_status"),
        ("License", "license"),
    ]
    entries = []
    cell = None
    if row is not None:
        prefix = "previous" if previous else "current"
        cell = row.get("previous_source_cell_id" if previous else "source_cell_id")
        for name, value in (
            ("Series", row["series_id"]),
            ("Observation", row[f"{prefix}_observation_id"]),
            ("Source table", row["table"]),
            ("Source row", row["row_locator"]),
            ("Source cell", cell),
        ):
            entries.append(f"<dt>{name}</dt><dd>{_escape(value)}</dd>")
    entries.append(
        f"<dt>Original source URL</dt><dd>{_source_link(metadata['source_url'], cell)}</dd>"
    )
    for name, key in fields:
        if key in metadata:
            entries.append(f"<dt>{name}</dt><dd>{_escape(metadata[key])}</dd>")
    entries.append("<dt>Historical availability</dt><dd>Not authenticated</dd>")
    return '<dl class="meta">' + "".join(entries) + "</dl>"


def _audit_html(report: Mapping[str, Any]) -> str:
    sections = []
    for label, metadata in (("Current", report["current"]), ("Previous", report["previous"])):
        if metadata is None:
            continue
        audit = metadata["audit"]
        checks = []
        for check in audit["checks"]:
            passed = check["passed"] is True
            css = "" if passed else ' class="failed-check"'
            status = "PASS" if passed else "FAIL"
            checks.append(
                f'<li{css}><span class="check-status">{status}</span> '
                f"{_escape(check['expression'])} "
                f'<span class="subtle">· residual {_escape(check["residual"])}; '
                f"tolerance {_escape(check['tolerance'])} USD million</span></li>"
            )
        sections.append(
            f'<h3>{label} capture</h3><ul class="audit-list">{"".join(checks)}</ul>'
            f'<p class="subtle">Audit SHA-256: <code>{_escape(audit["audit_sha256"])}</code></p>'
        )
    return "".join(sections)


def _hash_directive(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"


def render_brief_html(report: Mapping[str, Any]) -> str:
    """Render a self-contained brief; only explicit source-link clicks leave the file."""
    current, previous = report["current"], report["previous"]
    trust_title, trust_body = _trust(report)
    passed = report["passed"] is True
    status, status_class = ("PASS", "") if passed else ("FAIL", " fail")
    failure = (
        ""
        if passed
        else (
            '<aside class="notice fail" role="alert"><strong>FAIL — accounting checks</strong>'
            "<p>At least one capture failed its accounting checks. Review the failures below "
            "before using these values.</p></aside>"
        )
    )
    rows = []
    for row in report["rows"]:
        trace = "<section><h3>Current capture</h3>" + _metadata_html(current, row) + "</section>"
        if previous:
            trace += (
                "<section><h3>Previous capture</h3>"
                + _metadata_html(previous, row, previous=True)
                + "</section>"
            )
        paired = " paired" if previous else ""
        rows.append(
            f'<tr class="data-row"><td>{_escape(_label(row))}</td>'
            f'<td class="number">{_number(row["current_value"])}</td>'
            f'<td class="number previous">{_number(row["previous_value"])}</td>'
            f'<td class="number delta">{_number(row["delta"], signed=True)}</td></tr>'
            '<tr class="provenance-row"><td colspan="4"><details>'
            f"<summary>Trace source · {_escape(row['table'])} · "
            f"{_escape(row['row_locator'])}</summary>"
            f'<div class="trace-columns{paired}">{trace}</div></details></td></tr>'
        )
    previous_date = _escape(str(previous["observed_at"])[:10]) if previous else "Not selected"
    missing = (
        ""
        if previous
        else (
            '<div class="missing-previous"><p>Select a previous capture to compare these seven '
            "values. Use local case directories:</p>"
            f"<code>{_escape(_PREVIOUS_HELP)}</code></div>"
        )
    )
    csp = (
        "default-src 'none'; base-uri 'none'; object-src 'none'; connect-src 'none'; "
        "form-action 'none'; img-src 'none'; font-src 'none'; "
        f"style-src {_hash_directive(_STYLE)}; script-src {_hash_directive(_SCRIPT)}"
    )
    attribution = []
    for label, source in (("Current", current), ("Previous", previous)):
        if source is not None and source.get("source_attribution"):
            attribution.append(
                f'<p class="attribution">{label} source: '
                f"{_escape(source['source_attribution'])} "
                f"Source terms: {_escape(source.get('source_terms_url'))}. "
                "External source material retains its own terms; "
                "the software license does not replace them.</p>"
            )
    copy_text = _escape(_copy_table(report))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{_escape(csp)}">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>H.4.1 brief · {_escape(str(current["observed_at"])[:10])}</title>
<style>{_STYLE}</style></head><body><main>
<header><div class="masthead"><span class="brand">OpenMacroState</span>
<span class="edition">Research brief / H.4.1</span></div>
<p class="eyebrow">Federal Reserve Banks · Consolidated balance sheet</p>
<h1>Federal Reserve balance sheet</h1>
<p class="lede">Seven reported values, their changes, and the source behind each number.</p>
<dl class="dates"><div><dt>OBSERVATION DATE</dt>
<dd>{_escape(str(current["observed_at"])[:10])}</dd></div>
<div><dt>PREVIOUS OBSERVATION</dt><dd>{previous_date}</dd></div>
<div><dt>ACCOUNTING CHECKS</dt><dd><span class="badge{status_class}">{status}</span></dd></div></dl>
</header>
<aside class="notice"><strong>{_escape(trust_title)}</strong><p>{_escape(trust_body)}</p></aside>
{failure}
<section aria-labelledby="values-heading"><div class="section-head">
<h2 id="values-heading">Reported values</h2><p class="unit">USD million · exact integers</p></div>
<div class="table-scroll"><table aria-label="Seven H.4.1 observations">
<thead><tr><th scope="col">Measure</th><th scope="col" class="number">Current</th>
<th scope="col" class="number">Previous</th><th scope="col" class="number">Change</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<p class="comparison-note">{_escape(_comparison_text(report))}</p>{missing}
<div class="toolbar"><button id="copy-table" type="button" hidden>Copy table</button>
<a class="download" href="observations.csv" download>Download CSV</a>
<a class="download" href="brief.md" download>Download Markdown</a>
<span id="copy-status" class="copy-status" role="status" aria-live="polite"></span></div>
<section id="copy-fallback" hidden><label for="copy-data">Select and copy this table</label>
<textarea id="copy-data" readonly spellcheck="false">{copy_text}</textarea>
</section><noscript><p class="subtle">Downloads work without JavaScript.</p></noscript></section>
<section class="audit" aria-labelledby="audit-heading"><div class="audit-head">
<h2 id="audit-heading">Accounting checks</h2><span class="badge{status_class}">{status}</span></div>
<p class="subtle">Assets = liabilities + capital, plus bounds on selected components.
Passing these checks does not certify source authenticity.</p>{_audit_html(report)}</section>
<details class="provenance"><summary>Capture record and provenance limits</summary>
<p class="subtle">{_escape(_LIMITATION)}</p>{_metadata_html(current)}</details>
{"".join(attribution)}
<footer><span>OpenMacroState · Experimental H.4.1 research brief</span>
<span class="offline-note">Offline file · no automatic network requests</span></footer>
</main><script>{_SCRIPT}</script></body></html>
"""


def _markdown(value: object) -> str:
    text = html.escape(_text(value), quote=False).replace("\r", " ").replace("\n", " ")
    return re.sub(r"([\\`*_{\[\]}()|!#>])", r"\\\1", text)


def render_brief_markdown(report: Mapping[str, Any]) -> str:
    """Render portable notes with exact amounts and explicit provenance limits."""
    current, previous = report["current"], report["previous"]
    trust_title, trust_body = _trust(report)
    status = "PASS" if report["passed"] is True else "FAIL"
    lines = [
        "# Federal Reserve balance sheet",
        "",
        f"Observation: {_markdown(current['observed_at'])}",
        "",
        f"**Accounting checks: {status}.**",
        "",
        f"**{_markdown(trust_title)}.** {_markdown(trust_body)}",
        "",
        _LIMITATION,
        "",
        "External source material retains its own terms; "
        "the software license does not replace them.",
        "",
        "Unit: USD million (`USD_million`); exact integers.",
        "",
        "| Measure | Current | Previous | Change |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in report["rows"]:
        values = [
            "—" if row[key] is None else _integer(row[key])
            for key in ("current_value", "previous_value", "delta")
        ]
        lines.append(f"| {_markdown(_label(row))} | {' | '.join(values)} |")
    lines.extend(["", _markdown(_comparison_text(report)), ""])
    if previous is None:
        lines.extend(
            [
                "Select a previous capture using local case directories:",
                "",
                f"```sh\n{_PREVIOUS_HELP}\n```",
                "",
            ]
        )
    lines.extend(["## Accounting checks", ""])
    for label, source in (("Current", current), ("Previous", previous)):
        if source is None:
            continue
        lines.extend([f"### {label} capture", ""])
        for check in source["audit"]["checks"]:
            check_status = "PASS" if check["passed"] is True else "FAIL"
            lines.append(
                f"- {check_status}: {_markdown(check['expression'])}; "
                f"residual {_markdown(check['residual'])}, "
                f"tolerance {_markdown(check['tolerance'])} USD million."
            )
        lines.extend(["", f"Audit SHA-256: {_markdown(source['audit']['audit_sha256'])}", ""])
    lines.extend(["## Provenance", ""])
    for label, source in (("Current", current), ("Previous", previous)):
        if source is None:
            continue
        lines.extend([f"### {label} capture", ""])
        for key, value in source.items():
            if key != "audit":
                lines.append(f"- {_markdown(key)}: {_markdown(value)}")
        lines.append("")
    lines.extend(["### Observation locators", ""])
    for row in report["rows"]:
        lines.extend(
            [
                f"- **{_markdown(_label(row))}**: {_markdown(row['table'])}; "
                f"{_markdown(row['row_locator'])}; cell {_markdown(row.get('source_cell_id'))}; "
                f"observation {_markdown(row['current_observation_id'])}; "
                f"previous observation {_markdown(row['previous_observation_id'])}.",
            ]
        )
    return "\n".join(lines) + "\n"
