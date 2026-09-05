"""Experimental, read-only accounting checks over accepted observations.

The report produced here is not part of the public v1 interchange schema.  It
does not create derived observations or modify a case bundle.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from openmacrostate.api.v1.connector_types import FrozenArtifact
from openmacrostate.api.v1.errors import ContractError
from openmacrostate.api.v1.types import parse_timestamp
from openmacrostate.connectors.fed_h41_release import FedH41ReleaseConnector
from openmacrostate.runtime.case import CaseEvaluation, _bundle_path
from openmacrostate.runtime.connectors import _observation_record
from openmacrostate.runtime.jsonio import canonical_json_bytes, sha256_bytes

EXPERIMENTAL_FORMAT = "experimental/openmacrostate-accounting-audit/1"
FED_H41_BALANCE_SHEET_RULE = "fed-h41-balance-sheet-v1"
_BOUNDARY_ID = "us.federal_reserve_banks.consolidated"
_CONNECTOR_ID = "fed-h41-release"
_CONNECTOR_VERSION = "0.2.0"
_SOURCE_ID = "federal.reserve.board.h41.dated_release"
_UNIT = "USD_million"
_TOLERANCE = Decimal("1")
_MAX_ARTIFACT_BYTES = 2 * 1024 * 1024
_AMOUNT = re.compile(r"^(?:0|[1-9][0-9]{0,14})$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RETRIEVAL_FIELDS = {
    "capture_mode",
    "recording_completeness_claim",
    "final_url",
    "http_status",
    "response_headers",
    "hash_authority",
    "transport_retrieved_at_claim",
    "transport_time_core_observed",
    "source_authentication",
}

_INPUTS = (
    (
        "total_assets",
        "fed.h41.total_assets",
        {"statement_id": "fed.h41.table5", "side": "asset", "role": "total"},
    ),
    (
        "total_liabilities",
        "fed.h41.total_liabilities",
        {"statement_id": "fed.h41.table5", "side": "liability", "role": "total"},
    ),
    (
        "total_capital",
        "fed.h41.total_capital",
        {"statement_id": "fed.h41.table5", "side": "capital", "role": "total"},
    ),
    (
        "securities_held_outright",
        "fed.h41.securities_held_outright",
        {"statement_id": "fed.h41.table1", "side": "asset", "role": "component"},
    ),
    (
        "primary_credit",
        "fed.h41.primary_credit",
        {"statement_id": "fed.h41.table1", "side": "asset", "role": "component"},
    ),
    (
        "treasury_general_account",
        "fed.h41.treasury_general_account",
        {"statement_id": "fed.h41.table1", "side": "liability", "role": "component"},
    ),
    (
        "reserve_balances",
        "fed.h41.reserve_balances",
        {"statement_id": "fed.h41.table1", "side": "liability", "role": "component"},
    ),
)


def _canonical_timestamp(value: object, *, field: str) -> tuple[datetime, str]:
    if not isinstance(value, str):
        raise ContractError(f"{field} must be a non-empty RFC3339 string")
    parsed = parse_timestamp(value, field=field)
    return parsed, parsed.isoformat().replace("+00:00", "Z")


def _amount(record: Mapping[str, Any], *, series_id: str) -> Decimal:
    value = record.get("value")
    if not isinstance(value, str) or _AMOUNT.fullmatch(value) is None:
        raise ContractError(
            f"accounting input {series_id} must be a canonical non-negative integer string "
            "with at most 15 digits"
        )
    return Decimal(value)


def _render_amount(value: Decimal) -> str:
    return format(value, "f")


def _accounting_metadata(record: Mapping[str, Any], *, series_id: str) -> Mapping[str, Any]:
    extensions = record.get("extensions")
    if not isinstance(extensions, Mapping):
        raise ContractError(f"accounting input {series_id} lacks observation extensions")
    accounting = extensions.get("org.openmacrostate.accounting")
    if not isinstance(accounting, Mapping):
        raise ContractError(f"accounting input {series_id} lacks accounting metadata")
    return accounting


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{field} must be an object")
    return value


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{field} must be a non-empty string")
    return value


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{field} must be an integer")
    return value


def _boolean(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{field} must be boolean")
    return value


def _read_preserved_artifact(
    evaluation: CaseEvaluation,
    artifact: Mapping[str, Any],
) -> bytes:
    storage_uri = _text(artifact.get("storage_uri"), field="accounting artifact.storage_uri")
    artifact_path = _bundle_path(
        evaluation.case_dir,
        storage_uri,
        field="accounting artifact.storage_uri",
    )
    try:
        if artifact_path.is_symlink() or not artifact_path.is_file():
            raise ContractError("accounting artifact must be a regular preserved file")
        with artifact_path.open("rb") as handle:
            body = handle.read(_MAX_ARTIFACT_BYTES + 1)
    except ContractError:
        raise
    except OSError as exc:
        raise ContractError(f"cannot read preserved accounting artifact: {exc}") from exc
    if len(body) > _MAX_ARTIFACT_BYTES:
        raise ContractError("accounting artifact exceeds the fixed 2 MiB parser limit")
    declared_length = _integer(artifact.get("byte_length"), field="accounting artifact.byte_length")
    if declared_length != len(body):
        raise ContractError("accounting artifact byte length does not match preserved bytes")
    declared_sha256 = _text(artifact.get("sha256"), field="accounting artifact.sha256")
    if _SHA256.fullmatch(declared_sha256) is None or sha256_bytes(body) != declared_sha256:
        raise ContractError("accounting artifact SHA-256 does not match preserved bytes")
    return body


def _replay_exact_artifact(
    evaluation: CaseEvaluation,
    artifact: Mapping[str, Any],
    selected: Mapping[str, Mapping[str, Any]],
) -> dict[str, str | bool]:
    case_extensions = _mapping(
        evaluation.case.get("extensions"), field="accounting case.extensions"
    )
    if (
        case_extensions.get("connector_id") != _CONNECTOR_ID
        or case_extensions.get("connector_version") != _CONNECTOR_VERSION
    ):
        raise ContractError("accounting case must be a fed-h41-release v0.2.0 capture")
    if case_extensions.get("historical_evidence") is not False:
        raise ContractError("accounting replay does not authenticate historical evidence")

    artifact_extensions = _mapping(
        artifact.get("extensions"), field="accounting artifact.extensions"
    )
    if (
        artifact_extensions.get("connector_id") != _CONNECTOR_ID
        or artifact_extensions.get("connector_version") != _CONNECTOR_VERSION
    ):
        raise ContractError("accounting artifact must be a fed-h41-release v0.2.0 artifact")
    if artifact_extensions.get("historical_version_authenticated") is not False:
        raise ContractError("accounting replay does not authenticate a historical artifact")
    if artifact.get("source_id") != _SOURCE_ID:
        raise ContractError("accounting source artifact has an unexpected source_id")
    if artifact.get("media_type") != "text/html":
        raise ContractError("accounting source artifact must use text/html")
    if artifact.get("source_published_at") is not None:
        raise ContractError("accounting source artifact must not claim a publication timestamp")

    artifact_sha256 = _text(artifact.get("sha256"), field="accounting source artifact.sha256")
    artifact_id = _text(artifact.get("artifact_id"), field="accounting source artifact.artifact_id")
    if artifact_id != f"artifact:sha256:{artifact_sha256}":
        raise ContractError("accounting artifact_id must be derived from its SHA-256")

    request = _mapping(artifact_extensions.get("request"), field="accounting artifact request")
    if set(request) != {"method", "url", "accept"}:
        raise ContractError("accounting artifact request metadata is not exact")
    if request.get("method") != "GET" or request.get("accept") != "text/html":
        raise ContractError("accounting artifact request must be exact GET text/html")
    request_url = _text(request.get("url"), field="accounting artifact request.url")

    retrieval = _mapping(
        artifact_extensions.get("retrieval"), field="accounting artifact retrieval"
    )
    if set(retrieval) != _RETRIEVAL_FIELDS:
        raise ContractError("accounting artifact retrieval metadata is not exact")
    final_url = _text(retrieval.get("final_url"), field="accounting retrieval.final_url")
    if final_url != request_url:
        raise ContractError("accounting artifact final_url must equal its dated request URL")
    if _integer(retrieval.get("http_status"), field="accounting retrieval.http_status") != 200:
        raise ContractError("accounting artifact HTTP status must be 200")
    response_headers = _mapping(
        retrieval.get("response_headers"), field="accounting retrieval.response_headers"
    )
    if any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in response_headers.items()
    ):
        raise ContractError("accounting retrieval response headers must be strings")
    content_type = response_headers.get("content-type")
    if (
        not isinstance(content_type, str)
        or content_type.split(";", 1)[0].strip().lower() != "text/html"
    ):
        raise ContractError("accounting retrieval content-type must be text/html")
    capture_mode = _text(retrieval.get("capture_mode"), field="accounting retrieval.capture_mode")
    recording_kind = _text(
        retrieval.get("recording_completeness_claim"),
        field="accounting retrieval.recording_completeness_claim",
    )
    source_authentication = _text(
        retrieval.get("source_authentication"),
        field="accounting retrieval.source_authentication",
    )
    transport_time_core_observed = _boolean(
        retrieval.get("transport_time_core_observed"),
        field="accounting retrieval.transport_time_core_observed",
    )
    if capture_mode == "recorded":
        if (
            recording_kind not in {"complete_response", "test_only_excerpt"}
            or source_authentication != "unverified_recording"
            or transport_time_core_observed
        ):
            raise ContractError("accounting recorded retrieval metadata is inconsistent")
    elif capture_mode == "live":
        if (
            recording_kind != "complete_response"
            or source_authentication != "core_observed_https"
            or not transport_time_core_observed
        ):
            raise ContractError("accounting live retrieval metadata is inconsistent")
    else:
        raise ContractError("accounting retrieval capture_mode must be live or recorded")
    if (
        case_extensions.get("capture_mode") != capture_mode
        or case_extensions.get("recording_completeness_claim") != recording_kind
        or case_extensions.get("source_authentication") != source_authentication
    ):
        raise ContractError("accounting case and artifact retrieval metadata disagree")
    if artifact_extensions.get("test_only_excerpt") is not (recording_kind == "test_only_excerpt"):
        raise ContractError("accounting artifact excerpt metadata is inconsistent")
    if retrieval.get("hash_authority") != "openmacrostate-core":
        raise ContractError("accounting artifact hash authority must be openmacrostate-core")
    transport_retrieved_at_claim = _text(
        retrieval.get("transport_retrieved_at_claim"),
        field="accounting retrieval.transport_retrieved_at_claim",
    )
    parse_timestamp(
        transport_retrieved_at_claim,
        field="accounting retrieval.transport_retrieved_at_claim",
    )

    body = _read_preserved_artifact(evaluation, artifact)
    retrieved_at = _text(
        artifact.get("retrieved_at"), field="accounting source artifact.retrieved_at"
    )
    parse_timestamp(retrieved_at, field="accounting source artifact.retrieved_at")
    connector = FedH41ReleaseConnector()
    frozen = FrozenArtifact(
        source_id=_SOURCE_ID,
        request_url=request_url,
        final_url=final_url,
        status_code=200,
        media_type="text/html",
        response_headers=MappingProxyType(dict(response_headers)),
        retrieved_at=retrieved_at,
        transport_retrieved_at_claim=transport_retrieved_at_claim,
        body=body,
        sha256=artifact_sha256,
        byte_length=len(body),
        capture_mode=capture_mode,
        recording_kind=recording_kind,
        source_authentication=source_authentication,
        transport_time_core_observed=transport_time_core_observed,
    )
    drafts = tuple(connector.normalize(frozen))
    expected_records = tuple(
        _observation_record(
            draft,
            source_id=_SOURCE_ID,
            artifact_id=artifact_id,
            retrieved_at=retrieved_at,
        )
        for draft in drafts
    )
    expected_by_series = {str(record["series_id"]): record for record in expected_records}
    required_series = {series_id for _, series_id, _ in _INPUTS}
    if len(expected_records) != len(_INPUTS) or set(expected_by_series) != required_series:
        raise ContractError("current H.4.1 replay did not reconstruct exactly seven inputs")
    for input_name, series_id, _ in _INPUTS:
        if canonical_json_bytes(selected[input_name]) != canonical_json_bytes(
            expected_by_series[series_id]
        ):
            raise ContractError(
                f"accounting input {series_id} does not exactly match the preserved artifact replay"
            )
    return {
        "provenance_verification": "replayed_exact_artifact",
        "connector_ruleset_version": connector.ruleset_version,
        "source_artifact_id": artifact_id,
        "source_artifact_sha256": artifact_sha256,
        "source_authentication": source_authentication,
        "provenance_verification_scope": (
            "exact_preserved_artifact_re_normalization_not_acquisition_authentication"
        ),
        "historical_version_authenticated": False,
    }


def _input_record(
    record: Mapping[str, Any],
    *,
    value: Decimal,
    canonical_times: Mapping[str, str],
) -> dict[str, str]:
    return {
        "series_id": str(record["series_id"]),
        "observation_id": str(record["observation_id"]),
        "source_id": str(record["source_id"]),
        "artifact_id": str(record["artifact_id"]),
        "value": _render_amount(value),
        "unit": str(record["unit"]),
        "quality": str(record["quality"]),
        "observed_at": canonical_times["observed_at"],
        "released_at": canonical_times["released_at"],
        "vintage_at": canonical_times["vintage_at"],
        "ingested_at": canonical_times["ingested_at"],
    }


def audit_accounting(
    evaluation: CaseEvaluation,
    *,
    rule_id: str,
    observed_at: str,
) -> dict[str, Any]:
    """Evaluate one fixed accounting rule against eligible case evidence only."""

    if rule_id != FED_H41_BALANCE_SHEET_RULE:
        raise ContractError(f"unsupported accounting rule: {rule_id}")
    requested_time, canonical_observed_at = _canonical_timestamp(
        observed_at, field="accounting observed_at"
    )

    selected: dict[str, Mapping[str, Any]] = {}
    amounts: dict[str, Decimal] = {}
    input_times: dict[str, dict[str, str]] = {}
    for input_name, series_id, expected_metadata in _INPUTS:
        matches: list[Mapping[str, Any]] = []
        for record in evaluation.accepted_observations:
            if record.get("series_id") != series_id:
                continue
            record_time, _ = _canonical_timestamp(
                record.get("observed_at"), field=f"accounting input {series_id}.observed_at"
            )
            if record_time == requested_time:
                matches.append(record)
        if len(matches) != 1:
            raise ContractError(
                f"accounting rule {rule_id} requires exactly one accepted {series_id} "
                f"observation at {canonical_observed_at}; found {len(matches)}"
            )
        record = matches[0]
        if record.get("source_id") != _SOURCE_ID:
            raise ContractError(f"accounting input {series_id} has an unexpected source_id")
        if record.get("unit") != _UNIT:
            raise ContractError(f"accounting input {series_id} must use {_UNIT}")
        if record.get("quality") != "reported":
            raise ContractError(f"accounting input {series_id} must have reported quality")
        accounting = _accounting_metadata(record, series_id=series_id)
        expected = {
            "boundary_id": _BOUNDARY_ID,
            **expected_metadata,
            "stock_flow": "stock",
        }
        if dict(accounting) != expected:
            raise ContractError(f"accounting input {series_id} has unexpected accounting metadata")
        selected[input_name] = record
        amounts[input_name] = _amount(record, series_id=series_id)
        input_times[input_name] = {
            field: _canonical_timestamp(
                record.get(field), field=f"accounting input {series_id}.{field}"
            )[1]
            for field in ("observed_at", "released_at", "vintage_at", "ingested_at")
        }

    artifact_ids = {str(record.get("artifact_id")) for record in selected.values()}
    if len(artifact_ids) != 1:
        raise ContractError("accounting inputs must come from exactly one source artifact")
    artifact_id = next(iter(artifact_ids))
    matching_artifacts = [
        artifact for artifact in evaluation.artifacts if artifact.get("artifact_id") == artifact_id
    ]
    if len(matching_artifacts) != 1:
        raise ContractError("accounting inputs require exactly one matching source artifact")
    if matching_artifacts[0].get("source_id") != _SOURCE_ID:
        raise ContractError("accounting source artifact has an unexpected source_id")
    for field in ("observed_at", "released_at", "vintage_at", "ingested_at"):
        timestamps = {times[field] for times in input_times.values()}
        if len(timestamps) != 1:
            raise ContractError(f"accounting inputs must share one exact canonical {field}")
    provenance = _replay_exact_artifact(evaluation, matching_artifacts[0], selected)

    liabilities_plus_capital = amounts["total_liabilities"] + amounts["total_capital"]
    balance_sheet_residual = amounts["total_assets"] - liabilities_plus_capital
    selected_asset_components = amounts["securities_held_outright"] + amounts["primary_credit"]
    unselected_assets = amounts["total_assets"] - selected_asset_components
    selected_liability_components = (
        amounts["reserve_balances"] + amounts["treasury_general_account"]
    )
    unselected_liabilities = amounts["total_liabilities"] - selected_liability_components

    checks = [
        {
            "check_id": "assets_equal_liabilities_plus_capital",
            "expression": "total_assets = total_liabilities + total_capital",
            "residual": _render_amount(balance_sheet_residual),
            "tolerance": _render_amount(_TOLERANCE),
            "comparison": "absolute_residual_lte_tolerance",
            "passed": abs(balance_sheet_residual) <= _TOLERANCE,
        },
        {
            "check_id": "selected_asset_components_within_total_assets",
            "expression": ("securities_held_outright + primary_credit <= total_assets + tolerance"),
            "residual": _render_amount(unselected_assets),
            "tolerance": _render_amount(_TOLERANCE),
            "comparison": "residual_gte_negative_tolerance",
            "passed": unselected_assets >= -_TOLERANCE,
        },
        {
            "check_id": "selected_liability_components_within_total_liabilities",
            "expression": (
                "reserve_balances + treasury_general_account <= total_liabilities + tolerance"
            ),
            "residual": _render_amount(unselected_liabilities),
            "tolerance": _render_amount(_TOLERANCE),
            "comparison": "residual_gte_negative_tolerance",
            "passed": unselected_liabilities >= -_TOLERANCE,
        },
    ]
    source_snapshot = evaluation.snapshot()
    source_snapshot_content_sha256 = source_snapshot.get("content_sha256")
    if not isinstance(source_snapshot_content_sha256, str):
        raise ContractError("case snapshot lacks content_sha256")

    report: dict[str, Any] = {
        "format": EXPERIMENTAL_FORMAT,
        "rule_id": rule_id,
        "boundary_id": _BOUNDARY_ID,
        "case_id": evaluation.case_id,
        "observed_at": canonical_observed_at,
        "information_cutoff": evaluation.information_cutoff,
        "unit": _UNIT,
        "inputs": {
            input_name: _input_record(
                selected[input_name],
                value=amounts[input_name],
                canonical_times=input_times[input_name],
            )
            for input_name, _, _ in _INPUTS
        },
        "derived": {
            "liabilities_plus_capital": _render_amount(liabilities_plus_capital),
            "balance_sheet_residual": _render_amount(balance_sheet_residual),
            "selected_asset_components": _render_amount(selected_asset_components),
            "unselected_assets": _render_amount(unselected_assets),
            "selected_liability_components": _render_amount(selected_liability_components),
            "unselected_liabilities": _render_amount(unselected_liabilities),
        },
        "checks": checks,
        "passed": all(check["passed"] for check in checks),
        "source_snapshot_content_sha256": source_snapshot_content_sha256,
        **provenance,
    }
    report["audit_sha256"] = sha256_bytes(canonical_json_bytes(report))
    return report


__all__ = [
    "EXPERIMENTAL_FORMAT",
    "FED_H41_BALANCE_SHEET_RULE",
    "audit_accounting",
]
