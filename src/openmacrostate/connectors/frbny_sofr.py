"""Federal Reserve Bank of New York SOFR connector."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any
from zoneinfo import ZoneInfo

from openmacrostate.api.v1.connector_types import FetchRequest, FrozenArtifact, ObservationDraft
from openmacrostate.api.v1.errors import ContractError
from openmacrostate.api.v1.types import parse_timestamp

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FIRST_SOFR_DATE = date(2018, 4, 2)
_NEW_YORK = ZoneInfo("America/New_York")
_ROW_FIELDS = {
    "effectiveDate",
    "type",
    "percentRate",
    "percentPercentile1",
    "percentPercentile25",
    "percentPercentile75",
    "percentPercentile99",
    "volumeInBillions",
    "revisionIndicator",
    "footnoteId",
}
_SERIES = (
    ("percentRate", "frbny.sofr.rate", "percent"),
    ("volumeInBillions", "frbny.sofr.volume", "USD_billion"),
    ("percentPercentile1", "frbny.sofr.p01", "percent"),
    ("percentPercentile25", "frbny.sofr.p25", "percent"),
    ("percentPercentile75", "frbny.sofr.p75", "percent"),
    ("percentPercentile99", "frbny.sofr.p99", "percent"),
)


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number is forbidden: {value}")


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _date(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or _DATE.fullmatch(value) is None:
        raise ContractError(f"{field} must use YYYY-MM-DD")
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise ContractError(f"{field} is not a real calendar date") from exc


def _date_observed_at(value: str) -> str:
    return f"{value}T00:00:00Z"


def _decimal_number(value: object, *, field: str) -> tuple[str, Decimal]:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ContractError(f"{field} must be a JSON number, not a string")
    return str(value), value


class FrbnySofrConnector:
    """Capture a bounded, explicitly dated SOFR response from the Markets API."""

    __slots__ = ()
    ruleset_version = "frbny-sofr-normalization/3"

    spec: Mapping[str, Any] = MappingProxyType(
        {
            "schema_version": "1.0.0",
            "plugin_id": "frbny-sofr",
            "plugin_version": "0.1.0",
            "api_version": "1",
            "source_ids": ("frbny.markets.sofr",),
            "allowed_hosts": ("markets.newyorkfed.org",),
            "required_secret_names": (),
            "license": {
                "license_id": "FRBNY-Terms-of-Use-2023-06-09",
                "terms_url": "https://www.newyorkfed.org/privacy/termsofuse.html",
                "redistribution": "restricted",
                "commercial_use": "allowed",
                "attribution": "Federal Reserve Bank of New York",
                "reviewed_at": "2026-08-09T00:00:00Z",
            },
        }
    )

    def plan(self, request: Mapping[str, Any]) -> tuple[FetchRequest, ...]:
        if set(request) != {"start", "end"}:
            raise ContractError("frbny-sofr request requires only start and end")
        start = request.get("start")
        end = request.get("end")
        start_date = _date(start, field="start")
        end_date = _date(end, field="end")
        if start_date > end_date:
            raise ContractError("start must not follow end")
        if (end_date - start_date).days > 366:
            raise ContractError("SOFR capture range must not exceed 367 calendar days")
        return (
            FetchRequest(
                method="GET",
                url=(
                    "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
                    f"?startDate={start}&endDate={end}"
                ),
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
                parse_int=Decimal,
                parse_constant=_reject_constant,
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            raise ContractError(f"cannot decode strict FRBNY SOFR JSON: {exc}") from exc
        if not isinstance(document, dict) or set(document) != {"refRates"}:
            raise ContractError("FRBNY SOFR response must contain only refRates")
        rows = document.get("refRates")
        if not isinstance(rows, list):
            raise ContractError("FRBNY SOFR refRates must be an array")
        if not rows:
            raise ContractError("FRBNY SOFR response contains no rows")

        planned = self._planned_range(artifact.request_url)
        retrieval_date = (
            parse_timestamp(artifact.retrieved_at, field="core_retrieved_at")
            .astimezone(_NEW_YORK)
            .date()
        )
        seen_dates: set[str] = set()
        validated_rows: list[
            tuple[str, Mapping[str, Any], Mapping[str, tuple[str, Decimal]], str | None]
        ] = []
        for position, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ContractError(f"FRBNY SOFR row {position} must be an object")
            unknown = sorted(set(row) - _ROW_FIELDS)
            if unknown:
                raise ContractError(f"FRBNY SOFR row has unknown fields: {', '.join(unknown)}")
            missing = sorted({"effectiveDate", "type", "percentRate"} - set(row))
            if missing:
                raise ContractError(f"FRBNY SOFR row is missing fields: {', '.join(missing)}")
            effective_date = row["effectiveDate"]
            effective = _date(effective_date, field="effectiveDate")
            assert isinstance(effective_date, str)
            if not planned[0] <= effective <= planned[1]:
                raise ContractError("FRBNY SOFR row falls outside the requested date range")
            if effective.date() < _FIRST_SOFR_DATE:
                raise ContractError("FRBNY SOFR effectiveDate predates the first valid SOFR date")
            if effective.date() >= retrieval_date:
                raise ContractError(
                    "FRBNY SOFR effectiveDate must be strictly earlier than the "
                    "core retrieval date in America/New_York"
                )
            if effective_date in seen_dates:
                raise ContractError(f"duplicate FRBNY SOFR effectiveDate: {effective_date}")
            seen_dates.add(effective_date)
            if row["type"] != "SOFR":
                raise ContractError("FRBNY secured-rates row is not type SOFR")
            revision = row.get("revisionIndicator")
            if revision is not None and not isinstance(revision, str):
                raise ContractError("revisionIndicator must be a string when present")
            footnote = row.get("footnoteId")
            footnote_text = None
            if footnote is not None:
                footnote_text, _ = _decimal_number(footnote, field="footnoteId")
            numeric: dict[str, tuple[str, Decimal]] = {}
            for field, _, _ in _SERIES:
                if field in row and row[field] is not None:
                    numeric[field] = _decimal_number(row[field], field=field)
            if "percentRate" not in numeric:
                raise ContractError("FRBNY SOFR percentRate is required")
            if "volumeInBillions" in numeric and numeric["volumeInBillions"][1] < 0:
                raise ContractError("FRBNY SOFR volumeInBillions must be non-negative")
            self._validate_percentile_order(numeric)
            validated_rows.append((effective_date, row, numeric, footnote_text))

        drafts: list[ObservationDraft] = []
        for effective_date, row, numeric, footnote_text in sorted(
            validated_rows, key=lambda item: item[0]
        ):
            revision = row.get("revisionIndicator")
            common = {
                "value_date": effective_date,
                "temporal_precision": "date",
                "calendar_timezone": "America/New_York",
                "observed_at_convention": "canonical_utc_date_anchor_not_instant",
                "release_time_basis": "conservative_retrieval_time",
                "vintage_time_basis": "conservative_retrieval_time",
                "revision_indicator": revision,
                "footnote_id": footnote_text,
                "parser_id": self.ruleset_version,
                "transformation": "normalized_from_exact_response",
                "effective_date_eligibility": (
                    "on_or_after_2018-04-02_and_strictly_before_core_retrieval_new_york_date"
                ),
            }
            for field, series_id, unit in _SERIES:
                if field not in numeric:
                    continue
                value = numeric[field][0]
                drafts.append(
                    ObservationDraft(
                        series_id=series_id,
                        observed_at=_date_observed_at(effective_date),
                        released_at=artifact.retrieved_at,
                        value=value,
                        unit=unit,
                        extensions={**common, "source_field": field},
                    )
                )
        return tuple(drafts)

    @staticmethod
    def _validate_percentile_order(values: Mapping[str, tuple[str, Decimal]]) -> None:
        rate = values["percentRate"][1]
        p01 = values.get("percentPercentile1")
        p25 = values.get("percentPercentile25")
        p75 = values.get("percentPercentile75")
        p99 = values.get("percentPercentile99")
        comparisons = (
            (p01, p25, "p01 <= p25"),
            (p01, ("", rate), "p01 <= rate"),
            (p25, ("", rate), "p25 <= rate"),
            (("", rate), p75, "rate <= p75"),
            (("", rate), p99, "rate <= p99"),
            (p75, p99, "p75 <= p99"),
        )
        for lower, upper, rule in comparisons:
            if lower is not None and upper is not None and lower[1] > upper[1]:
                raise ContractError(f"FRBNY SOFR percentile ordering violates {rule}")

    @staticmethod
    def _planned_range(url: str) -> tuple[datetime, datetime]:
        match = re.fullmatch(
            r"https://markets\.newyorkfed\.org/api/rates/secured/sofr/search\.json"
            r"\?startDate=(\d{4}-\d{2}-\d{2})&endDate=(\d{4}-\d{2}-\d{2})",
            url,
        )
        if match is None:
            raise ContractError("FRBNY artifact URL does not match the fixed endpoint")
        return _date(match.group(1), field="startDate"), _date(match.group(2), field="endDate")
