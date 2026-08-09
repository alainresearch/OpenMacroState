"""Public structured error types."""


class OpenMacroStateError(Exception):
    """Base class for expected OpenMacroState failures."""


class ContractError(OpenMacroStateError):
    """A plugin or wire record violated its declared contract."""


class CaseValidationError(OpenMacroStateError):
    """A case pack could not be validated safely."""
