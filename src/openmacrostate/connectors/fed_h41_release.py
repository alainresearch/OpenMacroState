"""Federal Reserve Board dated H.4.1 release connector."""

from __future__ import annotations

import calendar
import re
from collections.abc import Iterable, Mapping
from datetime import date
from html.parser import HTMLParser
from types import MappingProxyType
from typing import Any
from zoneinfo import ZoneInfo

from openmacrostate.api.v1.connector_types import (
    CaptureBundleMetadata,
    FetchRequest,
    FrozenArtifact,
    ObservationDraft,
)
from openmacrostate.api.v1.errors import ContractError
from openmacrostate.api.v1.types import parse_timestamp

_BASE_URL = "https://www.federalreserve.gov/releases/h41"
_FIRST_RULESET_DATE = date(2021, 8, 12)
_NEW_YORK = ZoneInfo("America/New_York")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_REQUEST_URL = re.compile(r"^https://www\.federalreserve\.gov/releases/h41/([0-9]{8})/h41\.htm$")
_RELEVANT_CELL = re.compile(r"^(t1|t2|t7|t8)(?:h[1-9][0-9]*c[1-9][0-9]*|r[1-9][0-9]*c[1-9][0-9]*)$")
_ROW_LABEL = re.compile(r"^(t1|t2|t7|t8)r([1-9][0-9]*)c1$")
_MILLIONS = re.compile(r"^(?:0|[1-9][0-9]{0,2}(?:,[0-9]{3})*)$")
_RELEASE_PREFIX = "Release Date: "
_TABLE_PREFIXES = ("t1", "t2", "t7", "t8")
_TABLE_HEADINGS = {
    "t1": "1. Factors Affecting Reserve Balances of Depository Institutions",
    "t2": "1. Factors Affecting Reserve Balances of Depository Institutions (continued)",
    "t7": "5. Consolidated Statement of Condition of All Federal Reserve Banks",
    "t8": "5. Consolidated Statement of Condition of All Federal Reserve Banks (continued)",
}
_HIDDEN_CLASSES = frozenset(
    {"d-none", "display-none", "hidden", "is-hidden", "sr-only", "visually-hidden"}
)
_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
)


class _H41HtmlParser(HTMLParser):
    """Collect ruleset-3 cells while preserving their table and row lineage."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cells: dict[str, str] = {}
        self.cell_headers: dict[str, tuple[str, ...]] = {}
        self.cell_rows: dict[str, int] = {}
        self.cell_tables: dict[str, int] = {}
        self.table_contexts: dict[int, tuple[tuple[str, str, bool, bool], ...]] = {}
        self.table_has_plain_div_parent: dict[int, bool] = {}
        self.visible_chunks: list[str] = []
        self._active_cell: tuple[str, str, list[str]] | None = None
        self._completed_children: dict[int, list[tuple[str, str, bool, bool]]] = {}
        self._element_text: dict[int, list[str]] = {}
        self._semantic_attributes: dict[int, tuple[bool, bool]] = {}
        self._seen_cells: set[str] = set()
        self._element_stack: list[tuple[str, int, int, bool, bool, bool]] = []
        self._plain_divs: set[int] = set()
        self._hidden_depth = 0
        self._ignored_depth = 0
        self._next_element = 0
        self._next_row = 0
        self._next_table = 0
        self._row_stack: list[tuple[int, int]] = []
        self._table_stack: list[int] = []

    @staticmethod
    def _attributes(attrs: list[tuple[str, str | None]]) -> dict[str, str | None]:
        result: dict[str, str | None] = {}
        for key, value in attrs:
            if key in result:
                raise ContractError(f"H.4.1 HTML contains duplicate {key!r} attributes")
            result[key] = value
        return result

    @staticmethod
    def _first_attributes(attrs: list[tuple[str, str | None]]) -> dict[str, str | None]:
        result: dict[str, str | None] = {}
        for key, value in attrs:
            result.setdefault(key, value)
        return result

    @staticmethod
    def _starts_hidden(tag: str, attrs: Mapping[str, str | None]) -> bool:
        if tag in {"details", "dialog"} and "open" not in attrs:
            return True
        if "hidden" in attrs or "inert" in attrs:
            return True
        aria_hidden = attrs.get("aria-hidden")
        if isinstance(aria_hidden, str) and aria_hidden.strip().lower() == "true":
            return True
        classes = attrs.get("class")
        if isinstance(classes, str) and _HIDDEN_CLASSES.intersection(classes.lower().split()):
            return True
        style = attrs.get("style")
        if isinstance(style, str):
            compact = re.sub(r"\s+", "", style.lower())
            if any(
                declaration in compact
                for declaration in ("display:none", "visibility:hidden", "opacity:0")
            ):
                return True
        return False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        first_attributes = self._first_attributes(attrs)
        own_hidden = self._starts_hidden(tag, first_attributes)
        own_ignored = tag in {"noscript", "script", "style", "template"}
        parent_id = self._element_stack[-1][1] if self._element_stack else 0
        self._next_element += 1
        element_id = self._next_element
        hidden = self._hidden_depth > 0 or own_hidden
        ignored = self._ignored_depth > 0 or own_ignored
        if tag not in _VOID_TAGS:
            self._element_stack.append(
                (tag, element_id, parent_id, own_hidden, own_ignored, not hidden and not ignored)
            )
            self._element_text[element_id] = []
            self._semantic_attributes[element_id] = (
                "id" in first_attributes,
                "class" in first_attributes,
            )
            self._hidden_depth += int(own_hidden)
            self._ignored_depth += int(own_ignored)
            if tag == "div" and not attrs:
                self._plain_divs.add(element_id)
        elif not hidden and not ignored:
            self._completed_children.setdefault(parent_id, []).append(
                (
                    tag,
                    "",
                    "id" in first_attributes,
                    "class" in first_attributes,
                )
            )
        if ignored:
            return
        if tag == "table":
            self._next_table += 1
            table_id = self._next_table
            self._table_stack.append(table_id)
            self.table_contexts[table_id] = tuple(self._completed_children.get(parent_id, ())[-2:])
            self.table_has_plain_div_parent[table_id] = parent_id in self._plain_divs
        elif tag == "tr" and self._table_stack:
            self._next_row += 1
            self._row_stack.append((self._table_stack[-1], self._next_row))

        identifiers = [value for key, value in attrs if key == "id"]
        relevant_identifiers = [
            value
            for value in identifiers
            if isinstance(value, str) and _RELEVANT_CELL.fullmatch(value) is not None
        ]
        if len(identifiers) > 1 and relevant_identifiers:
            raise ContractError("H.4.1 relevant elements must not contain duplicate id attributes")
        if len(identifiers) != 1:
            return
        identifier = identifiers[0]
        if not isinstance(identifier, str) or _RELEVANT_CELL.fullmatch(identifier) is None:
            return
        if hidden:
            raise ContractError("H.4.1 relevant table cells must not be hidden")
        attributes = self._attributes(attrs)
        if tag not in {"td", "th"}:
            raise ContractError("H.4.1 relevant cell IDs must belong to td or th elements")
        if len(self._table_stack) != 1 or not self._row_stack:
            raise ContractError("H.4.1 relevant cells must belong to one explicit table row")
        table_id = self._table_stack[-1]
        row_table_id, row_id = self._row_stack[-1]
        if row_table_id != table_id:
            raise ContractError("H.4.1 relevant cell table and row ancestry disagree")
        if self._active_cell is not None:
            raise ContractError("H.4.1 HTML contains nested relevant table cells")
        if identifier in self._seen_cells:
            raise ContractError(f"H.4.1 HTML contains duplicate cell ID: {identifier}")
        self._seen_cells.add(identifier)
        header = attributes.get("header")
        if header is not None and not isinstance(header, str):
            raise ContractError("H.4.1 cell header attribute must be text")
        self.cell_headers[identifier] = tuple(header.split()) if header else ()
        self.cell_rows[identifier] = row_id
        self.cell_tables[identifier] = table_id
        self._active_cell = (tag, identifier, [])

    def handle_endtag(self, tag: str) -> None:
        ignored = self._ignored_depth > 0
        if not ignored and self._active_cell is not None:
            cell_tag, identifier, chunks = self._active_cell
            if tag == cell_tag:
                self.cells[identifier] = " ".join(chunks)
                self._active_cell = None
        if not ignored and tag == "tr" and self._row_stack:
            self._row_stack.pop()
        elif not ignored and tag == "table" and self._table_stack:
            table_id = self._table_stack.pop()
            if self._row_stack and self._row_stack[-1][0] == table_id:
                raise ContractError("H.4.1 table ended before its row")

        match_index = next(
            (
                position
                for position in range(len(self._element_stack) - 1, -1, -1)
                if self._element_stack[position][0] == tag
            ),
            None,
        )
        if match_index is None:
            return
        closing = self._element_stack[match_index:]
        for (
            element_tag,
            element_id,
            parent_id,
            own_hidden,
            own_ignored,
            visible,
        ) in reversed(closing):
            text = " ".join(self._element_text.pop(element_id, ()))
            attributes_have_id, attributes_have_class = self._semantic_attributes.pop(
                element_id, (False, False)
            )
            if visible and text:
                self._completed_children.setdefault(parent_id, []).append(
                    (element_tag, text, attributes_have_id, attributes_have_class)
                )
            self._hidden_depth -= int(own_hidden)
            self._ignored_depth -= int(own_ignored)
        del self._element_stack[match_index:]

    def handle_data(self, data: str) -> None:
        if self._ignored_depth or self._hidden_depth:
            return
        normalized = " ".join(data.replace("\xa0", " ").split())
        if not normalized:
            return
        self.visible_chunks.append(normalized)
        parent_id = self._element_stack[-1][1] if self._element_stack else 0
        self._completed_children.setdefault(parent_id, []).append(
            ("#text", normalized, False, False)
        )
        for _, element_id, _, _, _, visible in self._element_stack:
            if visible:
                self._element_text[element_id].append(normalized)
        if self._active_cell is not None:
            self._active_cell[2].append(normalized)

    def finish(self) -> None:
        self.close()
        if self._active_cell is not None:
            raise ContractError("H.4.1 HTML ended inside a relevant table cell")
        if self._ignored_depth:
            raise ContractError("H.4.1 HTML ended inside script or style content")
        if self._hidden_depth:
            raise ContractError("H.4.1 HTML ended inside hidden content")
        if self._row_stack or self._table_stack:
            raise ContractError("H.4.1 HTML ended inside a table or row")


def _calendar_date(value: object, *, field: str) -> date:
    if not isinstance(value, str) or _DATE.fullmatch(value) is None:
        raise ContractError(f"{field} must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError(f"{field} is not a real calendar date") from exc


def _request_url(release_date: date) -> str:
    return f"{_BASE_URL}/{release_date:%Y%m%d}/h41.htm"


def _planned_release_date(url: str) -> date:
    match = _REQUEST_URL.fullmatch(url)
    if match is None:
        raise ContractError("H.4.1 artifact request URL does not match the fixed dated endpoint")
    value = match.group(1)
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:]))
    except ValueError as exc:
        raise ContractError("H.4.1 request URL contains an invalid release date") from exc


def _parse_long_date(value: str, *, field: str) -> date:
    match = re.fullmatch(
        r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), "
        r"(January|February|March|April|May|June|July|August|September|October|November|December) "
        r"([1-9]|[12][0-9]|3[01]), ([0-9]{4})",
        value,
    )
    if match is None:
        raise ContractError(f"{field} has an invalid source date")
    weekday_name, month_name, day_text, year_text = match.groups()
    month = list(calendar.month_name).index(month_name)
    try:
        result = date(int(year_text), month, int(day_text))
    except ValueError as exc:
        raise ContractError(f"{field} is not a real calendar date") from exc
    if calendar.day_name[result.weekday()] != weekday_name:
        raise ContractError(f"{field} weekday does not match its calendar date")
    return result


def _parse_month_date(value: str, *, field: str) -> date:
    match = re.fullmatch(
        r"(January|February|March|April|May|June|July|August|September|October|November|December) "
        r"(0[1-9]|[12][0-9]|3[01]), ([0-9]{4})",
        value,
    )
    if match is None:
        raise ContractError(f"{field} has an invalid source date")
    month_name, day_text, year_text = match.groups()
    month = list(calendar.month_name).index(month_name)
    try:
        return date(int(year_text), month, int(day_text))
    except ValueError as exc:
        raise ContractError(f"{field} is not a real calendar date") from exc


def _release_date(chunks: list[str]) -> date:
    candidates: list[date] = []
    for position, chunk in enumerate(chunks):
        if chunk.startswith(_RELEASE_PREFIX) and chunk != _RELEASE_PREFIX.strip():
            declared = chunk[len(_RELEASE_PREFIX) :]
            if re.match(
                r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), ",
                declared,
            ):
                candidates.append(_parse_long_date(declared, field="H.4.1 Release Date"))
            else:
                candidates.append(_parse_month_date(declared, field="H.4.1 Release Date"))
        if chunk == _RELEASE_PREFIX.strip() and position + 1 < len(chunks):
            candidates.append(_parse_month_date(chunks[position + 1], field="H.4.1 Release Date"))
    if len(candidates) != 1:
        raise ContractError("H.4.1 HTML must contain exactly one Release Date statement")
    return candidates[0]


def _parse_wednesday_header(value: str, *, field: str) -> date:
    match = re.fullmatch(
        r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) "
        r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
        r"([1-9]|[12][0-9]|3[01]), ([0-9]{4})",
        value,
    )
    if match is None:
        raise ContractError(f"{field} has an invalid H.4.1 column date")
    weekday_name, month_name, day_text, year_text = match.groups()
    month = list(calendar.month_abbr).index(month_name)
    try:
        result = date(int(year_text), month, int(day_text))
    except ValueError as exc:
        raise ContractError(f"{field} is not a real calendar date") from exc
    if weekday_name != "Wednesday" or result.weekday() != calendar.WEDNESDAY:
        raise ContractError(f"{field} must identify the Wednesday stock column")
    return result


def _millions_value(value: str, *, field: str) -> tuple[str, int]:
    if _MILLIONS.fullmatch(value) is None:
        raise ContractError(f"{field} must be a non-negative ASCII integer in millions")
    normalized = value.replace(",", "")
    if len(normalized) > 15:
        raise ContractError(f"{field} exceeds the supported 15-digit magnitude")
    try:
        return normalized, int(normalized)
    except ValueError as exc:
        raise ContractError(f"{field} is not a supported integer in millions") from exc


class FedH41ReleaseConnector:
    """Capture one dated H.4.1 HTML release under conservative time semantics."""

    __slots__ = ()
    ruleset_version = "fed-h41-release-normalization/3"
    bundle_metadata = CaptureBundleMetadata(
        title="Federal Reserve Board dated H.4.1 official-source capture",
        fixture_kind="licensed_public",
        source_notice=(
            "Source: Board of Governors of the Federal Reserve System, H.4.1 Factors "
            "Affecting Reserve Balances and Condition Statement of F.R. Banks. The "
            "Board's website disclaimer states that, unless otherwise indicated, "
            "information on its website is in the public domain and may be copied and "
            "distributed when the Board is cited as the source. This source decision "
            "covers only Board-authored table and text content in the captured response; "
            "it excludes Federal Reserve seals, logos, trademarks, and third-party "
            "material. OpenMacroState is not affiliated with or endorsed by the Board. "
            "A dated URL may be corrected later and does not authenticate when the exact "
            "bytes first became public."
        ),
    )
    spec: Mapping[str, Any] = MappingProxyType(
        {
            "schema_version": "1.0.0",
            "plugin_id": "fed-h41-release",
            "plugin_version": "0.2.0",
            "api_version": "1",
            "source_ids": ("federal.reserve.board.h41.dated_release",),
            "allowed_hosts": ("www.federalreserve.gov",),
            "required_secret_names": (),
            "license": {
                "license_id": "Federal-Reserve-Board-Public-Domain-Website-Information",
                "terms_url": "https://www.federalreserve.gov/disclaimer.htm",
                "redistribution": "restricted",
                "commercial_use": "allowed",
                "attribution": "Board of Governors of the Federal Reserve System",
                "reviewed_at": "2026-08-09T17:00:00Z",
            },
        }
    )

    _SERIES = (
        ("fed.h41.total_assets", "t7", "Total assets", 3),
        ("fed.h41.total_liabilities", "t8", "Total liabilities", 3),
        ("fed.h41.total_capital", "t8", "Total capital", 3),
        ("fed.h41.securities_held_outright", "t1", "Securities held outright 1", 5),
        ("fed.h41.primary_credit", "t1", "Primary credit", 5),
        ("fed.h41.treasury_general_account", "t2", "U.S. Treasury, General Account", 5),
        ("fed.h41.reserve_balances", "t2", "Reserve balances with Federal Reserve Banks", 5),
    )
    _ACCOUNTING = MappingProxyType(
        {
            "fed.h41.total_assets": ("fed.h41.table5", "asset", "total"),
            "fed.h41.total_liabilities": ("fed.h41.table5", "liability", "total"),
            "fed.h41.total_capital": ("fed.h41.table5", "capital", "total"),
            "fed.h41.securities_held_outright": ("fed.h41.table1", "asset", "component"),
            "fed.h41.primary_credit": ("fed.h41.table1", "asset", "component"),
            "fed.h41.treasury_general_account": (
                "fed.h41.table1",
                "liability",
                "component",
            ),
            "fed.h41.reserve_balances": ("fed.h41.table1", "liability", "component"),
        }
    )

    def plan(self, request: Mapping[str, Any]) -> tuple[FetchRequest, ...]:
        if set(request) != {"start", "end"}:
            raise ContractError("fed-h41-release request requires only start and end")
        start = _calendar_date(request.get("start"), field="start")
        end = _calendar_date(request.get("end"), field="end")
        if start != end:
            raise ContractError(
                "fed-h41-release requires start and end to be the same release date"
            )
        if start < _FIRST_RULESET_DATE:
            raise ContractError("fed-h41-release ruleset 3 supports dates on or after 2021-08-12")
        return (
            FetchRequest(
                method="GET",
                url=_request_url(start),
                accept="text/html",
                max_bytes=2 * 1024 * 1024,
            ),
        )

    def normalize(self, artifact: FrozenArtifact) -> Iterable[ObservationDraft]:
        requested_release = _planned_release_date(artifact.request_url)
        retrieval_date = (
            parse_timestamp(artifact.retrieved_at, field="core_retrieved_at")
            .astimezone(_NEW_YORK)
            .date()
        )
        if requested_release > retrieval_date:
            raise ContractError(
                "H.4.1 release date must not follow the core retrieval date in America/New_York"
            )
        try:
            html = artifact.body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContractError("H.4.1 HTML must be strict UTF-8") from exc
        parser = _H41HtmlParser()
        parser.feed(html)
        parser.finish()

        if "H.4.1" not in parser.visible_chunks:
            raise ContractError("H.4.1 HTML must identify the H.4.1 statistical release")
        declared_release = _release_date(parser.visible_chunks)
        if declared_release != requested_release:
            raise ContractError("H.4.1 path date does not match the page Release Date")

        prefix_tables: dict[str, int] = {}
        for prefix in _TABLE_PREFIXES:
            table_ids = {
                parser.cell_tables[identifier]
                for identifier in parser.cells
                if identifier.startswith(prefix)
            }
            if len(table_ids) != 1:
                raise ContractError(f"H.4.1 {prefix} cells must belong to exactly one table")
            table_id = next(iter(table_ids))
            prefix_tables[prefix] = table_id
            if not parser.table_has_plain_div_parent.get(table_id, False):
                raise ContractError(
                    f"H.4.1 {prefix} table must have one immediate plain div parent "
                    "without attributes"
                )
            context = parser.table_contexts.get(table_id, ())
            if len(context) != 2:
                raise ContractError(
                    f"H.4.1 {prefix} table must immediately follow its heading and unit paragraphs"
                )
            (
                (heading_tag, heading, heading_has_id, heading_has_class),
                (unit_tag, unit, unit_has_id, unit_has_class),
            ) = context
            if (
                heading_tag != "p"
                or unit_tag != "p"
                or heading_has_id
                or unit_has_id
                or heading_has_class
                or unit_has_class
            ):
                raise ContractError(
                    f"H.4.1 {prefix} table must immediately follow plain heading and unit "
                    "paragraph siblings without id or class attributes"
                )
            if unit != "Millions of dollars":
                raise ContractError(
                    f"H.4.1 {prefix} table unit must be exactly Millions of dollars"
                )
            if heading != _TABLE_HEADINGS[prefix]:
                raise ContractError(f"H.4.1 {prefix} table lacks its exact semantic heading")
        if len(set(prefix_tables.values())) != len(_TABLE_PREFIXES):
            raise ContractError("H.4.1 selected prefixes must belong to distinct source tables")
        observed_dates = {
            prefix: _parse_wednesday_header(
                parser.cells.get(f"{prefix}h1c3", ""), field=f"{prefix}h1c3"
            )
            for prefix in _TABLE_PREFIXES
        }
        for prefix in _TABLE_PREFIXES:
            if parser.cell_tables.get(f"{prefix}h1c3") != prefix_tables[prefix]:
                raise ContractError(f"H.4.1 {prefix} Wednesday header is outside its source table")
            if parser.cell_tables.get(f"{prefix}h1c1") != prefix_tables[prefix]:
                raise ContractError(f"H.4.1 {prefix} row header is outside its source table")
            if parser.cell_rows.get(f"{prefix}h1c1") != parser.cell_rows.get(f"{prefix}h1c3"):
                raise ContractError(
                    f"H.4.1 {prefix} row and Wednesday headers must share one source row"
                )
            if parser.cell_tables.get(f"{prefix}r1c1") != prefix_tables[prefix]:
                raise ContractError(f"H.4.1 {prefix} row-group header is missing from its table")
            if parser.cell_headers.get(f"{prefix}r1c1") != (f"{prefix}h1c1",):
                raise ContractError(
                    f"H.4.1 {prefix} row-group header is not bound to the row header"
                )
        if len(set(observed_dates.values())) != 1:
            raise ContractError("H.4.1 selected table headers must share one Wednesday date")
        observed_date = next(iter(observed_dates.values()))
        if observed_date >= declared_release or (declared_release - observed_date).days > 7:
            raise ContractError(
                "H.4.1 Wednesday observation date must precede the release by at most seven days"
            )
        if observed_date >= retrieval_date:
            raise ContractError(
                "H.4.1 Wednesday observation date must be earlier than the core retrieval "
                "date in America/New_York"
            )

        values: dict[str, tuple[str, int, str]] = {}
        for series_id, prefix, label, value_column in self._SERIES:
            matches: list[tuple[str, str]] = []
            for identifier, text in parser.cells.items():
                match = _ROW_LABEL.fullmatch(identifier)
                if match is None or match.group(1) != prefix or text != label:
                    continue
                row = match.group(2)
                value_id = f"{prefix}r{row}c{value_column}"
                matches.append((identifier, value_id))
            if len(matches) != 1:
                raise ContractError(
                    f"H.4.1 {prefix} table must contain exactly one row labeled {label!r}"
                )
            label_id, value_id = matches[0]
            if parser.cell_tables.get(label_id) != prefix_tables[prefix]:
                raise ContractError(f"H.4.1 {label_id} is outside its expected source table")
            if parser.cell_tables.get(value_id) != prefix_tables[prefix]:
                raise ContractError(f"H.4.1 {value_id} is outside its expected source table")
            if parser.cell_rows.get(label_id) != parser.cell_rows.get(value_id):
                raise ContractError(f"H.4.1 {label_id} and {value_id} must share one source row")
            if parser.cell_headers.get(label_id) != (f"{prefix}h1c1",):
                raise ContractError(f"H.4.1 {label_id} is not bound to the expected row header")
            if parser.cell_headers.get(value_id) != (f"{prefix}r1c1", f"{prefix}h1c3"):
                raise ContractError(f"H.4.1 {value_id} is not bound to the Wednesday stock column")
            value, integer = _millions_value(
                parser.cells.get(value_id, ""), field=f"H.4.1 {value_id}"
            )
            values[series_id] = (value, integer, value_id)

        total_assets = values["fed.h41.total_assets"][1]
        if total_assets <= 0:
            raise ContractError("H.4.1 total assets must be positive")
        for series_id, (_, integer, _) in values.items():
            if series_id != "fed.h41.total_assets" and integer > total_assets:
                raise ContractError(f"H.4.1 {series_id} must not exceed total assets")

        common = {
            "value_date": observed_date.isoformat(),
            "source_declared_release_date": declared_release.isoformat(),
            "source_declared_release_date_is_availability_proof": False,
            "source_schedule_basis": "generally_Thursday_around_4_30_pm_not_used_as_released_at",
            "source_last_modified_is_availability_proof": False,
            "temporal_precision": "date",
            "calendar_timezone": "America/New_York",
            "observed_at_convention": "canonical_utc_date_anchor_not_instant",
            "release_time_basis": "conservative_retrieval_time",
            "vintage_time_basis": "conservative_retrieval_time",
            "historical_version_authenticated": False,
            "parser_id": self.ruleset_version,
            "transformation": "selected_Wednesday_stock_column_and_removed_grouping_commas",
        }
        return tuple(
            ObservationDraft(
                series_id=series_id,
                observed_at=f"{observed_date.isoformat()}T00:00:00Z",
                released_at=artifact.retrieved_at,
                value=values[series_id][0],
                unit="USD_million",
                extensions={
                    **common,
                    "source_table_prefix": prefix,
                    "source_row_label": label,
                    "source_cell_id": values[series_id][2],
                    "org.openmacrostate.accounting": {
                        "boundary_id": "us.federal_reserve_banks.consolidated",
                        "statement_id": self._ACCOUNTING[series_id][0],
                        "side": self._ACCOUNTING[series_id][1],
                        "role": self._ACCOUNTING[series_id][2],
                        "stock_flow": "stock",
                    },
                },
            )
            for series_id, prefix, label, _ in self._SERIES
        )
