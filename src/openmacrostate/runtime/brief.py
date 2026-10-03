"""Experimental, read-only H.4.1 briefs over exact-replayed capture evidence."""

from __future__ import annotations

from decimal import Decimal, localcontext
from typing import Any

from openmacrostate.api.v1.errors import ContractError
from openmacrostate.api.v1.types import parse_timestamp
from openmacrostate.runtime.accounting import FED_H41_BALANCE_SHEET_RULE, audit_accounting
from openmacrostate.runtime.case import CaseEvaluation
from openmacrostate.runtime.jsonio import normalize_json_value

EXPERIMENTAL_FORMAT = "experimental/openmacrostate-h41-brief/1"
_ROWS = (
    ("total_assets", "Total assets", "Table 5"),
    ("total_liabilities", "Total liabilities", "Table 5"),
    ("total_capital", "Total capital", "Table 5"),
    ("securities_held_outright", "Securities held outright", "Table 1"),
    ("primary_credit", "Primary credit", "Table 1"),
    ("treasury_general_account", "Treasury General Account", "Table 1"),
    ("reserve_balances", "Reserve balances", "Table 1"),
)
_SERIES = frozenset(f"fed.h41.{key}" for key, _, _ in _ROWS)


def _validated_capture(
    evaluation: CaseEvaluation,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    evaluation.snapshot()  # Verify the frozen evaluation before inspecting its records.
    if evaluation.quarantined_observations:
        raise ContractError("H.4.1 brief requires a capture without quarantined observations")
    records = evaluation.accepted_observations
    if len(records) != len(_ROWS) or {record.get("series_id") for record in records} != _SERIES:
        raise ContractError("H.4.1 brief requires exactly the seven accepted H.4.1 series")
    observed_times = {
        parse_timestamp(str(record.get("observed_at")), field="brief observation.observed_at")
        for record in records
    }
    if len(observed_times) != 1:
        raise ContractError("H.4.1 brief requires one unique observed_at across its seven inputs")
    observed_at = next(iter(observed_times)).isoformat().replace("+00:00", "Z")
    audit = audit_accounting(
        evaluation,
        rule_id=FED_H41_BALANCE_SHEET_RULE,
        observed_at=observed_at,
    )
    # The audit has re-hashed and re-normalized the preserved HTML and required
    # exact equality with all seven accepted records, including their locators.
    artifact = next(
        record
        for record in evaluation.artifacts
        if record["artifact_id"] == audit["source_artifact_id"]
    )
    retrieval = artifact["extensions"]["retrieval"]
    first = audit["inputs"]["total_assets"]
    metadata = {
        "case_id": evaluation.case_id,
        "source_id": artifact["source_id"],
        "source_url": artifact["extensions"]["request"]["url"],
        "artifact_id": audit["source_artifact_id"],
        "artifact_sha256": audit["source_artifact_sha256"],
        "source_authentication": audit["source_authentication"],
        "capture_mode": retrieval["capture_mode"],
        "recording_kind": retrieval["recording_completeness_claim"],
        "observed_at": audit["observed_at"],
        "released_at": first["released_at"],
        "vintage_at": first["vintage_at"],
        "ingested_at": first["ingested_at"],
        "transport_retrieved_at_claim": retrieval["transport_retrieved_at_claim"],
        "information_cutoff": audit["information_cutoff"],
        "snapshot_sha256": audit["source_snapshot_content_sha256"],
        "connector_ruleset_version": audit["connector_ruleset_version"],
        "unit": audit["unit"],
        "boundary_id": audit["boundary_id"],
        "historical_evidence": False,
        "historical_version_authenticated": False,
        "provenance_verification": audit["provenance_verification"],
        "provenance_verification_scope": audit["provenance_verification_scope"],
        "license": normalize_json_value(artifact["license"]),
        "source_attribution": artifact["license"]["attribution"],
        "source_terms_url": artifact["license"]["terms_url"],
        "redistribution_status": artifact["license"]["redistribution"],
        "audit": {
            "passed": audit["passed"],
            "checks": audit["checks"],
            "residual": audit["derived"]["balance_sheet_residual"],
            "tolerance": audit["checks"][0]["tolerance"],
            "audit_sha256": audit["audit_sha256"],
        },
    }
    by_key = {str(record["series_id"]).removeprefix("fed.h41."): record for record in records}
    return metadata, audit["inputs"], by_key


def _comparison(current: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    if previous is None:
        return {
            "kind": "single_capture",
            "interval_days": None,
            "exactly_seven_days": None,
            "label": "Single capture; no comparison",
        }
    for field in ("source_id", "unit", "boundary_id", "connector_ruleset_version"):
        if current[field] != previous[field]:
            raise ContractError(f"H.4.1 brief captures must share the same {field}")
    current_time = parse_timestamp(current["observed_at"], field="brief current.observed_at")
    previous_time = parse_timestamp(previous["observed_at"], field="brief previous.observed_at")
    if previous_time > current_time:
        raise ContractError("previous H.4.1 observed_at must not follow current observed_at")
    if previous_time == current_time and parse_timestamp(
        previous["ingested_at"], field="brief previous.ingested_at"
    ) > parse_timestamp(current["ingested_at"], field="brief current.ingested_at"):
        raise ContractError("previous H.4.1 ingested_at must not follow current ingested_at")
    interval = current_time - previous_time
    return {
        "kind": "new_period" if interval.days else "identical",
        "interval_days": str(interval.days),
        "exactly_seven_days": interval.days == 7,
        "label": (
            f"New observation period; interval {interval.days} days"
            if interval.days
            else "No change in source bytes or selected values"
        ),
    }


def build_h41_brief(
    current: CaseEvaluation,
    previous: CaseEvaluation | None = None,
) -> dict[str, Any]:
    """Build a deterministic sidecar without reading a reveal or writing a capture.

    Both inputs must be complete, exact-replayed single-period H.4.1 captures.
    A failed accounting identity remains visible in a returned ``passed=False``
    report; invalid evidence raises instead. Comparisons never certify revisions.
    """
    current_meta, current_inputs, current_records = _validated_capture(current)
    previous_meta = None
    previous_inputs: dict[str, Any] = {}
    previous_records: dict[str, Any] = {}
    if previous is not None:
        previous_meta, previous_inputs, previous_records = _validated_capture(previous)
    comparison = _comparison(current_meta, previous_meta)
    rows = []
    for key, label, table in _ROWS:
        record = current_inputs[key]
        prior = previous_inputs.get(key)
        extensions = current_records[key]["extensions"]
        previous_value = None if prior is None else prior["value"]
        delta = None
        status = "single_capture"
        if prior is not None:
            with localcontext() as context:
                context.prec = 32  # Exact subtraction of supported 15-digit integer inputs.
                difference = Decimal(record["value"]) - Decimal(previous_value)
            delta = format(difference, "f")
            status = (
                "increased" if difference > 0 else "decreased" if difference < 0 else "unchanged"
            )
        rows.append(
            {
                "key": key,
                "label": label,
                "series_id": record["series_id"],
                "table": table,
                "row_locator": extensions["source_row_label"],
                "source_cell_id": extensions["source_cell_id"],
                "previous_source_cell_id": (
                    None if prior is None else previous_records[key]["extensions"]["source_cell_id"]
                ),
                "unit": record["unit"],
                "current_value": record["value"],
                "previous_value": previous_value,
                "delta": delta,
                "status": status,
                "current_observation_id": record["observation_id"],
                "previous_observation_id": None if prior is None else prior["observation_id"],
            }
        )
    if previous_meta is not None and comparison["kind"] == "identical":
        if any(row["status"] != "unchanged" for row in rows):
            comparison.update(
                kind="same_period_values_changed",
                label="Same observation period; selected values differ between captures",
            )
        elif current_meta["artifact_sha256"] != previous_meta["artifact_sha256"]:
            comparison.update(
                kind="same_period_artifact_changed",
                label="Selected values unchanged; source bytes differ between captures",
            )
    return {
        "format": EXPERIMENTAL_FORMAT,
        "passed": current_meta["audit"]["passed"]
        and (previous_meta is None or previous_meta["audit"]["passed"]),
        "historical_evidence": False,
        "historical_version_authenticated": False,
        "causal_interpretation": False,
        "current": current_meta,
        "previous": previous_meta,
        "comparison": comparison,
        "rows": rows,
    }


__all__ = ["EXPERIMENTAL_FORMAT", "build_h41_brief"]
