"""Built-in, review-trusted connectors.

Third-party connector code is not sandboxed in this pre-alpha. Only connectors
registered here may be invoked by the command line.
"""

from __future__ import annotations

from openmacrostate.api.v1.errors import ContractError
from openmacrostate.api.v1.interfaces import Connector
from openmacrostate.connectors.frbny_sofr import FrbnySofrConnector

_BUILTINS = {"frbny-sofr": FrbnySofrConnector}


def builtin_connector_ids() -> tuple[str, ...]:
    return tuple(sorted(_BUILTINS))


def get_builtin_connector(connector_id: str) -> Connector:
    connector_type = _BUILTINS.get(connector_id)
    if connector_type is None:
        raise ContractError(f"unknown built-in connector: {connector_id}")
    return connector_type()


def is_builtin_connector_instance(connector: object) -> bool:
    """Accept exact registered classes only; subclasses are not review-trusted."""
    return type(connector) in frozenset(_BUILTINS.values())


__all__ = ["builtin_connector_ids", "get_builtin_connector", "is_builtin_connector_instance"]
