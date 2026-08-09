"""Protocols for independently versioned plugins."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Mapping
from typing import Any, Protocol


class Connector(Protocol):
    """Collect bytes and normalize only artifacts frozen by the core runtime."""

    spec: Mapping[str, Any]

    async def collect(self, request: Mapping[str, Any], context: Any) -> AsyncIterator[bytes]: ...

    def normalize(self, artifact: Any, context: Any) -> Iterable[Mapping[str, Any]]: ...


class ModelAdapter(Protocol):
    """Run a model from a frozen snapshot without fetching live data."""

    spec: Mapping[str, Any]

    def validate_inputs(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def run(self, request: Mapping[str, Any], context: Any) -> Mapping[str, Any]: ...
