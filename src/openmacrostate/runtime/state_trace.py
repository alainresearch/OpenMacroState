"""Experimental, read-only state traces over verified accounting facts.

The trace is a deterministic projection of one accounting audit.  Its edges
describe derivation dependencies only; they do not encode causal claims or
persist derived observations in a case bundle.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from openmacrostate.api.v1.errors import ContractError
from openmacrostate.api.v1.types import parse_timestamp
from openmacrostate.runtime.accounting import (
    EXPERIMENTAL_FORMAT as ACCOUNTING_EXPERIMENTAL_FORMAT,
)
from openmacrostate.runtime.accounting import (
    FED_H41_BALANCE_SHEET_RULE,
    audit_accounting,
)
from openmacrostate.runtime.case import CaseEvaluation
from openmacrostate.runtime.jsonio import canonical_json_bytes, sha256_bytes

EXPERIMENTAL_FORMAT = "experimental/openmacrostate-state-trace/1"

_ENTITY_ID = "us.federal_reserve_banks"
_BOUNDARY_ID = "us.federal_reserve_banks.consolidated"
_UNIT = "USD_million"
_EXCLUDED_EPISTEMIC_KINDS = ("inference", "prediction", "scenario")
_KNOWLEDGE_TIME_FIELDS = ("released_at", "vintage_at", "ingested_at")

_REPORTED_INPUTS = (
    "total_assets",
    "total_liabilities",
    "total_capital",
    "securities_held_outright",
    "primary_credit",
    "treasury_general_account",
    "reserve_balances",
)


def _reported_node_id(input_name: str) -> str:
    return f"reported:{input_name}"


def _derived_node_id(derived_name: str) -> str:
    return f"derived:{derived_name}"


@dataclass(frozen=True, slots=True)
class _DerivedSpec:
    name: str
    operation: str
    expression: str
    inputs: tuple[tuple[str, str], ...]


_DERIVED_SPECS = (
    _DerivedSpec(
        name="liabilities_plus_capital",
        operation="add",
        expression="total_liabilities + total_capital",
        inputs=(
            (_reported_node_id("total_liabilities"), "addend_1"),
            (_reported_node_id("total_capital"), "addend_2"),
        ),
    ),
    _DerivedSpec(
        name="balance_sheet_residual",
        operation="subtract",
        expression="total_assets - liabilities_plus_capital",
        inputs=(
            (_reported_node_id("total_assets"), "minuend"),
            (_derived_node_id("liabilities_plus_capital"), "subtrahend"),
        ),
    ),
    _DerivedSpec(
        name="selected_asset_components",
        operation="add",
        expression="securities_held_outright + primary_credit",
        inputs=(
            (_reported_node_id("securities_held_outright"), "addend_1"),
            (_reported_node_id("primary_credit"), "addend_2"),
        ),
    ),
    _DerivedSpec(
        name="unselected_assets",
        operation="subtract",
        expression="total_assets - selected_asset_components",
        inputs=(
            (_reported_node_id("total_assets"), "minuend"),
            (_derived_node_id("selected_asset_components"), "subtrahend"),
        ),
    ),
    _DerivedSpec(
        name="selected_liability_components",
        operation="add",
        expression="reserve_balances + treasury_general_account",
        inputs=(
            (_reported_node_id("reserve_balances"), "addend_1"),
            (_reported_node_id("treasury_general_account"), "addend_2"),
        ),
    ),
    _DerivedSpec(
        name="unselected_liabilities",
        operation="subtract",
        expression="total_liabilities - selected_liability_components",
        inputs=(
            (_reported_node_id("total_liabilities"), "minuend"),
            (_derived_node_id("selected_liability_components"), "subtrahend"),
        ),
    ),
)

_DERIVED_BY_NAME = {spec.name: spec for spec in _DERIVED_SPECS}
_DERIVED_BY_NODE_ID = {_derived_node_id(spec.name): spec for spec in _DERIVED_SPECS}
STATE_TRACE_TARGETS = (
    "all",
    *tuple(spec.name for spec in _DERIVED_SPECS),
)
_TARGETS = frozenset(STATE_TRACE_TARGETS)
_TOPOLOGICAL_NODE_IDS = (
    *(_reported_node_id(input_name) for input_name in _REPORTED_INPUTS),
    *(_derived_node_id(spec.name) for spec in _DERIVED_SPECS),
)
_INHERITED_AUDIT_FIELDS = (
    "audit_sha256",
    "source_snapshot_content_sha256",
    "source_artifact_id",
    "source_artifact_sha256",
    "provenance_verification",
    "connector_ruleset_version",
    "source_authentication",
    "provenance_verification_scope",
    "historical_version_authenticated",
)


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{field} must be an object")
    return value


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{field} must be a non-empty string")
    return value


def _boolean(value: object, *, field: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{field} must be boolean")
    return value


def _canonical_max_timestamp(values: tuple[object, ...], *, field: str) -> str:
    parsed: list[datetime] = []
    for position, value in enumerate(values):
        text = _text(value, field=f"{field}[{position}]")
        parsed.append(parse_timestamp(text, field=f"{field}[{position}]"))
    maximum = max(parsed)
    return maximum.isoformat().replace("+00:00", "Z")


def _validate_audit_report(report: Mapping[str, Any], *, rule_id: str) -> None:
    if report.get("format") != ACCOUNTING_EXPERIMENTAL_FORMAT:
        raise ContractError("state trace requires accounting audit format /1")
    if report.get("rule_id") != rule_id or rule_id != FED_H41_BALANCE_SHEET_RULE:
        raise ContractError("state trace requires the fixed H.4.1 accounting rule")
    if report.get("boundary_id") != _BOUNDARY_ID:
        raise ContractError("state trace accounting boundary is unexpected")
    if report.get("unit") != _UNIT:
        raise ContractError("state trace accounting unit is unexpected")
    _boolean(report.get("passed"), field="accounting audit passed")

    inputs = _mapping(report.get("inputs"), field="accounting audit inputs")
    if len(inputs) != len(_REPORTED_INPUTS) or set(inputs) != set(_REPORTED_INPUTS):
        raise ContractError("state trace requires the fixed seven accounting inputs")
    derived = _mapping(report.get("derived"), field="accounting audit derived")
    derived_names = {spec.name for spec in _DERIVED_SPECS}
    if len(derived) != len(derived_names) or set(derived) != derived_names:
        raise ContractError("state trace requires the fixed six accounting derivations")

    for field in _INHERITED_AUDIT_FIELDS:
        if field not in report:
            raise ContractError(f"accounting audit lacks required trace field: {field}")
    expected_audit_sha256 = _text(report.get("audit_sha256"), field="accounting audit SHA-256")
    unhashed = dict(report)
    unhashed.pop("audit_sha256")
    if sha256_bytes(canonical_json_bytes(unhashed)) != expected_audit_sha256:
        raise ContractError("accounting audit SHA-256 is invalid")


def _revision_of(
    evaluation: CaseEvaluation,
    *,
    observation_id: str,
) -> str | None:
    matches = [
        record
        for record in evaluation.accepted_observations
        if record.get("observation_id") == observation_id
    ]
    if len(matches) != 1:
        raise ContractError(
            "state trace requires exactly one accepted observation for every audited input"
        )
    revision_of = matches[0].get("revision_of")
    if revision_of is not None and (not isinstance(revision_of, str) or not revision_of):
        raise ContractError("state trace observation revision_of must be null or a string")
    return revision_of


def _reported_node(
    evaluation: CaseEvaluation,
    *,
    input_name: str,
    record: Mapping[str, Any],
) -> dict[str, Any]:
    required_text = {
        field: _text(record.get(field), field=f"accounting input {input_name}.{field}")
        for field in (
            "series_id",
            "observation_id",
            "source_id",
            "artifact_id",
            "value",
            "unit",
            "observed_at",
            "released_at",
            "vintage_at",
            "ingested_at",
        )
    }
    if required_text["unit"] != _UNIT:
        raise ContractError(f"accounting input {input_name} has an unexpected unit")
    revision_of = _revision_of(
        evaluation,
        observation_id=required_text["observation_id"],
    )
    return {
        "node_id": _reported_node_id(input_name),
        "epistemic_kind": "fact",
        "value_origin": "reported",
        "entity_id": _ENTITY_ID,
        "boundary_id": _BOUNDARY_ID,
        "series_id": required_text["series_id"],
        "value": required_text["value"],
        "unit": required_text["unit"],
        "observation_id": required_text["observation_id"],
        "source_id": required_text["source_id"],
        "artifact_id": required_text["artifact_id"],
        "observed_at": required_text["observed_at"],
        "released_at": required_text["released_at"],
        "vintage_at": required_text["vintage_at"],
        "ingested_at": required_text["ingested_at"],
        "revision_of": revision_of,
    }


def _node_knowledge_time(node: Mapping[str, Any], *, field: str) -> object:
    if node.get("value_origin") == "reported":
        return node.get(field)
    envelope = _mapping(
        node.get("knowledge_time_envelope"),
        field=f"state node {node.get('node_id')} knowledge_time_envelope",
    )
    return envelope.get(field)


def _derived_node(
    spec: _DerivedSpec,
    *,
    value: object,
    observed_at: str,
    nodes_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    rendered_value = _text(value, field=f"accounting derived {spec.name}")
    input_node_ids = tuple(node_id for node_id, _ in spec.inputs)
    missing = [node_id for node_id in input_node_ids if node_id not in nodes_by_id]
    if missing:
        raise ContractError(
            "state trace derivation is not in fixed topological order: " + ", ".join(missing)
        )
    envelope = {
        field: _canonical_max_timestamp(
            tuple(
                _node_knowledge_time(nodes_by_id[node_id], field=field)
                for node_id in input_node_ids
            ),
            field=f"state derivation {spec.name}.{field}",
        )
        for field in _KNOWLEDGE_TIME_FIELDS
    }
    return {
        "node_id": _derived_node_id(spec.name),
        "epistemic_kind": "fact",
        "value_origin": "derived",
        "entity_id": _ENTITY_ID,
        "boundary_id": _BOUNDARY_ID,
        "value": rendered_value,
        "unit": _UNIT,
        "observed_at": observed_at,
        "operation": spec.operation,
        "expression": spec.expression,
        "input_node_ids": list(input_node_ids),
        "knowledge_time_envelope": envelope,
    }


def _all_edges() -> list[dict[str, Any]]:
    return [
        {
            "edge_id": f"edge:{spec.name}:{input_role}",
            "from_node_id": input_node_id,
            "to_node_id": _derived_node_id(spec.name),
            "edge_kind": "derivation_dependency",
            "input_role": input_role,
            "causal_interpretation": False,
        }
        for spec in _DERIVED_SPECS
        for input_node_id, input_role in spec.inputs
    ]


def _closure_node_ids(target: str) -> tuple[str, ...]:
    if target == "all":
        return _TOPOLOGICAL_NODE_IDS
    wanted = {_derived_node_id(target)}
    pending = list(wanted)
    while pending:
        node_id = pending.pop()
        spec = _DERIVED_BY_NODE_ID.get(node_id)
        if spec is None:
            continue
        for input_node_id, _ in spec.inputs:
            if input_node_id not in wanted:
                wanted.add(input_node_id)
                pending.append(input_node_id)
    return tuple(node_id for node_id in _TOPOLOGICAL_NODE_IDS if node_id in wanted)


def _validate_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    expected_node_ids: tuple[str, ...],
) -> None:
    node_ids = [node.get("node_id") for node in nodes]
    if node_ids != list(expected_node_ids):
        raise ContractError("state trace nodes violate the fixed topological order")
    if len(node_ids) != len(set(node_ids)):
        raise ContractError("state trace node IDs must be unique")
    if any(not isinstance(node_id, str) or not node_id for node_id in node_ids):
        raise ContractError("state trace node IDs must be non-empty strings")
    if any(
        node.get("epistemic_kind") != "fact"
        or node.get("value_origin") not in {"reported", "derived"}
        or node.get("entity_id") != _ENTITY_ID
        or node.get("boundary_id") != _BOUNDARY_ID
        or node.get("unit") != _UNIT
        for node in nodes
    ):
        raise ContractError("state trace node fact dimensions are invalid")

    node_id_set = set(node_ids)
    edge_ids = [edge.get("edge_id") for edge in edges]
    if len(edge_ids) != len(set(edge_ids)):
        raise ContractError("state trace edge IDs must be unique")
    position = {node_id: index for index, node_id in enumerate(node_ids)}
    successors: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    indegree = {node_id: 0 for node_id in node_ids}
    for edge in edges:
        source = edge.get("from_node_id")
        destination = edge.get("to_node_id")
        if source not in node_id_set or destination not in node_id_set:
            raise ContractError("state trace edge endpoint does not exist")
        if edge.get("edge_kind") != "derivation_dependency":
            raise ContractError("state trace edges must be derivation dependencies")
        if edge.get("causal_interpretation") is not False:
            raise ContractError("state trace derivation edges must be explicitly non-causal")
        if not isinstance(edge.get("input_role"), str) or not edge.get("input_role"):
            raise ContractError("state trace derivation edge lacks input_role")
        if position[source] >= position[destination]:
            raise ContractError("state trace edge violates the fixed topological order")
        successors[source].append(destination)
        indegree[destination] += 1

    ready = [node_id for node_id in node_ids if indegree[node_id] == 0]
    visited = 0
    while ready:
        current = ready.pop(0)
        visited += 1
        for successor in successors[current]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                ready.append(successor)
    if visited != len(node_ids):
        raise ContractError("state trace graph must be acyclic")

    expected_edges = [
        edge
        for edge in _all_edges()
        if edge["from_node_id"] in node_id_set and edge["to_node_id"] in node_id_set
    ]
    if edges != expected_edges:
        raise ContractError("state trace edges violate the fixed derivation topology")


def trace_accounting_state(
    evaluation: CaseEvaluation,
    rule_id: str,
    observed_at: str,
    target: str,
) -> dict[str, Any]:
    """Project one verified H.4.1 accounting audit into a non-causal fact DAG."""

    if not isinstance(target, str) or target not in _TARGETS:
        supported = ", ".join(sorted(_TARGETS))
        raise ContractError(
            f"unsupported accounting state trace target: {target!r}; use {supported}"
        )

    audit = audit_accounting(
        evaluation,
        rule_id=rule_id,
        observed_at=observed_at,
    )
    audit_report = _mapping(audit, field="accounting audit")
    _validate_audit_report(audit_report, rule_id=rule_id)
    inputs = _mapping(audit_report.get("inputs"), field="accounting audit inputs")
    derived = _mapping(audit_report.get("derived"), field="accounting audit derived")
    canonical_observed_at = _text(
        audit_report.get("observed_at"), field="accounting audit observed_at"
    )

    all_nodes: list[dict[str, Any]] = []
    nodes_by_id: dict[str, Mapping[str, Any]] = {}
    for input_name in _REPORTED_INPUTS:
        node = _reported_node(
            evaluation,
            input_name=input_name,
            record=_mapping(inputs.get(input_name), field=f"accounting input {input_name}"),
        )
        all_nodes.append(node)
        nodes_by_id[node["node_id"]] = node
    for spec in _DERIVED_SPECS:
        node = _derived_node(
            spec,
            value=derived.get(spec.name),
            observed_at=canonical_observed_at,
            nodes_by_id=nodes_by_id,
        )
        all_nodes.append(node)
        nodes_by_id[node["node_id"]] = node

    included_node_ids = _closure_node_ids(target)
    included = set(included_node_ids)
    nodes = [node for node in all_nodes if node["node_id"] in included]
    edges = [
        edge
        for edge in _all_edges()
        if edge["from_node_id"] in included and edge["to_node_id"] in included
    ]
    _validate_graph(nodes, edges, expected_node_ids=included_node_ids)

    report: dict[str, Any] = {
        "format": EXPERIMENTAL_FORMAT,
        "rule_id": rule_id,
        "target": target,
        "case_id": _text(audit_report.get("case_id"), field="accounting audit case_id"),
        "observed_at": canonical_observed_at,
        "information_cutoff": _text(
            audit_report.get("information_cutoff"),
            field="accounting audit information_cutoff",
        ),
        "entity_id": _ENTITY_ID,
        "boundary_id": _BOUNDARY_ID,
        "unit": _UNIT,
        "materialization_mode": "retrospective_reconstruction",
        "historical_evidence": False,
        "rights_propagation": "inherits_source_artifact_terms",
        "causal_interpretation": False,
        "explicitly_excluded_epistemic_kinds": list(_EXCLUDED_EPISTEMIC_KINDS),
        "nodes": nodes,
        "edges": edges,
        "passed": _boolean(audit_report.get("passed"), field="accounting audit passed"),
        **{field: audit_report[field] for field in _INHERITED_AUDIT_FIELDS},
    }
    report["trace_sha256"] = sha256_bytes(canonical_json_bytes(report))
    return report


__all__ = [
    "EXPERIMENTAL_FORMAT",
    "STATE_TRACE_TARGETS",
    "trace_accounting_state",
]
