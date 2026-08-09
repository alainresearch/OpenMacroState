"""U.S. Treasury Fiscal Data Debt to the Penny connector."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal
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

_BASE_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny"
)
_FIELDS = "record_date,tot_pub_debt_out_amt,src_line_nbr"
_ENCODED_FIELDS = "record_date%2Ctot_pub_debt_out_amt%2Csrc_line_nbr"
_PAGE_SIZE = 367
_FIRST_RECORD_DATE = date(1993, 4, 1)
_NEW_YORK = ZoneInfo("America/New_York")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_CURRENCY = re.compile(r"^(?:0|[1-9][0-9]*)\.[0-9]{2}$")
_REQUEST_URL = re.compile(
    re.escape(f"{_BASE_URL}?fields={_ENCODED_FIELDS}&filter=record_date%3Agte%3A")
    + r"([0-9]{4}-[0-9]{2}-[0-9]{2})"
    + re.escape("%2Crecord_date%3Alte%3A")
    + r"([0-9]{4}-[0-9]{2}-[0-9]{2})"
    + re.escape(f"&sort=record_date&format=json&page%5Bnumber%5D=1&page%5Bsize%5D={_PAGE_SIZE}")
)
_ROW_FIELDS = {"record_date", "tot_pub_debt_out_amt", "src_line_nbr"}
_LABELS = {
    "record_date": "Record Date",
    "tot_pub_debt_out_amt": "Total Public Debt Outstanding",
    "src_line_nbr": "Source Line Number",
}
_DATA_TYPES = {
    "record_date": "DATE",
    "tot_pub_debt_out_amt": "CURRENCY",
    "src_line_nbr": "INTEGER",
}
_DATA_FORMATS = {
    "record_date": "YYYY-MM-DD",
    "tot_pub_debt_out_amt": "$10.20",
    "src_line_nbr": "10",
}
_SERIES_ID = "treasury.debt.total_public_outstanding"


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _calendar_date(value: object, *, field: str) -> date:
    if not isinstance(value, str) or _DATE.fullmatch(value) is None:
        raise ContractError(f"{field} must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError(f"{field} is not a real calendar date") from exc


def _nonnegative_integer(value: object, *, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ContractError(f"{field} must be a non-negative JSON integer")
    return value


def _positive_currency(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _CURRENCY.fullmatch(value) is None:
        raise ContractError(f"{field} must be a positive fixed-two-decimal string")
    parsed = Decimal(value)
    if not parsed.is_finite() or parsed <= 0:
        raise ContractError(f"{field} must be a positive fixed-two-decimal string")
    return value


def _request_url(start: str, end: str) -> str:
    return (
        f"{_BASE_URL}?fields={_ENCODED_FIELDS}"
        f"&filter=record_date%3Agte%3A{start}%2Crecord_date%3Alte%3A{end}"
        f"&sort=record_date&format=json"
        f"&page%5Bnumber%5D=1&page%5Bsize%5D={_PAGE_SIZE}"
    )


class TreasuryDebtToPennyConnector:
    """Capture one bounded page of total public debt outstanding."""

    __slots__ = ()
    ruleset_version = "treasury-debt-to-penny-normalization/1"
    bundle_metadata = CaptureBundleMetadata(
        title="U.S. Treasury Debt to the Penny official-source capture",
        fixture_kind="licensed_public",
        source_notice=(
            "Source: U.S. Department of the Treasury, Bureau of the Fiscal Service, "
            "Fiscal Data, Debt to the Penny. Treasury Fiscal Data's Open Data Policy "
            "states that its data is offered free, without restriction, and may be "
            "copied, adapted, redistributed, or otherwise used for non-commercial or "
            "commercial purposes. This source decision applies only to the "
            "Treasury-generated data records captured from this endpoint; it does not "
            "grant rights in trademarks or third-party material. Source attribution is "
            "retained for provenance and does not imply Treasury endorsement."
        ),
    )
    spec: Mapping[str, Any] = MappingProxyType(
        {
            "schema_version": "1.0.0",
            "plugin_id": "treasury-debt-to-penny",
            "plugin_version": "0.1.0",
            "api_version": "1",
            "source_ids": ("us.treasury.fiscaldata.debt_to_penny",),
            "allowed_hosts": ("api.fiscaldata.treasury.gov",),
            "required_secret_names": (),
            "license": {
                "license_id": "US-Treasury-Fiscal-Data-Open-Data",
                "terms_url": "https://fiscaldata.treasury.gov/api-documentation/",
                "redistribution": "allowed",
                "commercial_use": "allowed",
                "attribution": ("U.S. Department of the Treasury, Bureau of the Fiscal Service"),
                "reviewed_at": "2026-08-09T16:00:00Z",
            },
        }
    )

    def plan(self, request: Mapping[str, Any]) -> tuple[FetchRequest, ...]:
        if set(request) != {"start", "end"}:
            raise ContractError("treasury-debt-to-penny request requires only start and end")
        start = request.get("start")
        end = request.get("end")
        start_date = _calendar_date(start, field="start")
        end_date = _calendar_date(end, field="end")
        if start_date < _FIRST_RECORD_DATE:
            raise ContractError("Debt to the Penny start must be on or after 1993-04-01")
        if start_date > end_date:
            raise ContractError("start must not follow end")
        if (end_date - start_date).days > 366:
            raise ContractError("Debt to the Penny capture range must not exceed 367 calendar days")
        assert isinstance(start, str) and isinstance(end, str)
        return (
            FetchRequest(
                method="GET",
                url=_request_url(start, end),
                accept="application/json",
                max_bytes=4 * 1024 * 1024,
            ),
        )

    def normalize(self, artifact: FrozenArtifact) -> Iterable[ObservationDraft]:
        try:
            document = json.loads(
                artifact.body.decode("utf-8"),
                object_pairs_hook=_object_without_duplicate_keys,
                parse_float=Decimal,
                parse_int=int,
                parse_constant=_reject_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ContractError(f"cannot decode strict Treasury Fiscal Data JSON: {exc}") from exc
        if not isinstance(document, dict) or set(document) != {"data", "meta", "links"}:
            raise ContractError("Treasury response must contain only data, meta, and links")
        rows = document["data"]
        meta = document["meta"]
        links = document["links"]
        if not isinstance(rows, list):
            raise ContractError("Treasury response data must be an array")
        if not rows:
            raise ContractError("Treasury Debt to the Penny response contains no rows")
        self._validate_page(rows, meta, links)

        planned_start, planned_end = self._planned_range(artifact.request_url)
        retrieval_date = (
            parse_timestamp(artifact.retrieved_at, field="core_retrieved_at")
            .astimezone(_NEW_YORK)
            .date()
        )
        if planned_end >= retrieval_date:
            raise ContractError(
                "Treasury requested end date must be strictly earlier than the "
                "core retrieval date in America/New_York"
            )
        previous_date: date | None = None
        validated: list[tuple[str, str, str]] = []
        for position, row in enumerate(rows):
            if not isinstance(row, dict) or set(row) != _ROW_FIELDS:
                raise ContractError(f"Treasury row {position} must contain exactly {_FIELDS}")
            if any(not isinstance(value, str) for value in row.values()):
                raise ContractError("Treasury row fields must all be JSON strings")
            record_date_text = row["record_date"]
            record_date = _calendar_date(record_date_text, field="record_date")
            if not planned_start <= record_date <= planned_end:
                raise ContractError("Treasury row falls outside the requested date range")
            if record_date >= retrieval_date:
                raise ContractError(
                    "Treasury record_date must be strictly earlier than the "
                    "core retrieval date in America/New_York"
                )
            if previous_date is not None and record_date <= previous_date:
                raise ContractError(
                    "Treasury rows must be strictly ascending with unique record_date values"
                )
            previous_date = record_date
            if row["src_line_nbr"] != "1":
                raise ContractError("Treasury src_line_nbr must be the documented string '1'")
            total = _positive_currency(row["tot_pub_debt_out_amt"], field="tot_pub_debt_out_amt")
            validated.append((record_date_text, total, row["src_line_nbr"]))

        return tuple(
            ObservationDraft(
                series_id=_SERIES_ID,
                observed_at=f"{record_date_text}T00:00:00Z",
                released_at=artifact.retrieved_at,
                value=total,
                unit="USD",
                extensions={
                    "record_date": record_date_text,
                    "temporal_precision": "date",
                    "calendar_timezone": "America/New_York",
                    "observed_at_convention": "canonical_utc_date_anchor_not_instant",
                    "release_time_basis": "conservative_retrieval_time",
                    "vintage_time_basis": "conservative_retrieval_time",
                    "source_line_number": source_line,
                    "source_field": "tot_pub_debt_out_amt",
                    "record_date_semantics": (
                        "source_dictionary_calls_record_date_the_publication_date_while_"
                        "dataset_intro_describes_end_of-business-day_publication_of_"
                        "previous-business-day_data"
                    ),
                    "record_date_is_release_timestamp": False,
                    "release_calendar_basis": ("estimated_schedule_not_used_as_row_released_at"),
                    "revision_metadata": "not_exposed_by_source_endpoint",
                    "parser_id": self.ruleset_version,
                    "transformation": "normalized_from_exact_response",
                },
            )
            for record_date_text, total, source_line in validated
        )

    @staticmethod
    def _validate_page(rows: list[object], meta: object, links: object) -> None:
        if not isinstance(meta, dict) or set(meta) != {
            "count",
            "labels",
            "dataTypes",
            "dataFormats",
            "total-count",
            "total-pages",
        }:
            raise ContractError("Treasury meta has unknown or missing fields")
        if meta["labels"] != _LABELS:
            raise ContractError("Treasury meta labels do not match the fixed field selection")
        if meta["dataTypes"] != _DATA_TYPES:
            raise ContractError("Treasury meta dataTypes do not match the fixed field selection")
        if meta["dataFormats"] != _DATA_FORMATS:
            raise ContractError("Treasury meta dataFormats do not match the fixed field selection")
        count = _nonnegative_integer(meta["count"], field="meta.count")
        total_count = _nonnegative_integer(meta["total-count"], field="meta.total-count")
        total_pages = _nonnegative_integer(meta["total-pages"], field="meta.total-pages")
        if count != len(rows) or total_count != len(rows):
            raise ContractError(
                "Treasury pagination count and total-count must equal the returned row count"
            )
        if total_pages != 1 or len(rows) > _PAGE_SIZE:
            raise ContractError("Treasury capture requires exactly one complete bounded page")
        if not isinstance(links, dict) or set(links) != {
            "self",
            "first",
            "prev",
            "next",
            "last",
        }:
            raise ContractError("Treasury links has unknown or missing fields")
        expected_page = f"&page%5Bnumber%5D=1&page%5Bsize%5D={_PAGE_SIZE}"
        if (
            links["self"] != expected_page
            or links["first"] != expected_page
            or links["last"] != expected_page
            or links["prev"] is not None
            or links["next"] is not None
        ):
            raise ContractError(
                "Treasury pagination links must prove a single page with no next or previous"
            )

    @staticmethod
    def _planned_range(request_url: str) -> tuple[date, date]:
        match = _REQUEST_URL.fullmatch(request_url)
        if match is None:
            raise ContractError("Treasury artifact URL does not match the fixed endpoint")
        return (
            _calendar_date(match.group(1), field="request.start"),
            _calendar_date(match.group(2), field="request.end"),
        )


__all__ = ["TreasuryDebtToPennyConnector"]
