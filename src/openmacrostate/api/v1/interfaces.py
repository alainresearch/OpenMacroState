"""Protocols for independently versioned plugins."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from openmacrostate.api.v1.connector_types import FetchRequest, FrozenArtifact, ObservationDraft


class Connector(Protocol):
    """Plan retrievals and normalize only artifacts frozen by the core runtime.

    Connectors do not receive a network client, secret store, or output path. The
    core validates each fetch plan, owns retrieval and hashing, and supplies the
    exact immutable bytes to ``normalize``.
    """

    spec: Mapping[str, Any]
    ruleset_version: str

    def plan(self, request: Mapping[str, Any]) -> tuple[FetchRequest, ...]: ...

    def normalize(self, artifact: FrozenArtifact) -> Iterable[ObservationDraft]: ...


class ModelAdapter(Protocol):
    """Run a model from a frozen snapshot without fetching live data."""

    spec: Mapping[str, Any]

    def validate_inputs(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def run(self, request: Mapping[str, Any], context: Any) -> Mapping[str, Any]: ...
