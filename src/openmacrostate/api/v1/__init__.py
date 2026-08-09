"""Stable plugin API v1."""

from openmacrostate.api.v1.connector_types import FetchRequest, FrozenArtifact, ObservationDraft
from openmacrostate.api.v1.errors import (
    CaseValidationError,
    ContractError,
    OpenMacroStateError,
)
from openmacrostate.api.v1.interfaces import Connector, ModelAdapter
from openmacrostate.api.v1.types import Artifact, Observation

__all__ = [
    "CaseValidationError",
    "Artifact",
    "Connector",
    "ContractError",
    "FetchRequest",
    "FrozenArtifact",
    "ModelAdapter",
    "Observation",
    "ObservationDraft",
    "OpenMacroStateError",
]
