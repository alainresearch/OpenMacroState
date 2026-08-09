"""Built-in, review-trusted connectors.

Third-party connector code is not sandboxed in this pre-alpha. Only connectors
registered here may be invoked by the command line.
"""

from __future__ import annotations

from typing import Any

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


def list_builtin_connectors() -> tuple[dict[str, Any], ...]:
    from openmacrostate.runtime.connectors import validate_connector_spec

    result: list[dict[str, Any]] = []
    for connector_id in builtin_connector_ids():
        connector = get_builtin_connector(connector_id)
        spec = validate_connector_spec(connector.spec)
        license_info = spec["license"]
        result.append(
            {
                "connector_id": spec["plugin_id"],
                "version": spec["plugin_version"],
                "source_name": license_info["attribution"],
                "allowed_hosts": list(spec["allowed_hosts"]),
                "capture_modes": ["online", "recording"],
                "redistribution_status": license_info["redistribution"],
                "documentation_link": license_info["terms_url"],
            }
        )
    return tuple(result)


__all__ = [
    "builtin_connector_ids",
    "get_builtin_connector",
    "is_builtin_connector_instance",
    "list_builtin_connectors",
]
