"""Locate small examples distributed with source checkouts and wheels."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import files
from pathlib import Path

from openmacrostate.api.v1.errors import OpenMacroStateError


@dataclass(frozen=True, slots=True)
class BundledExample:
    name: str
    case_dir: Path
    reveal_dir: Path
    evaluation_at: str


_EXAMPLES = {
    "2023-banks": "2023-03-13T22:00:00Z",
}


def _installed_directory(suffix: str) -> Path | None:
    package_files = files("openmacrostate")
    if package_files is None:
        return None
    normalized_suffix = suffix.replace("\\", "/")
    for item in package_files:
        if str(item).replace("\\", "/").endswith(normalized_suffix):
            return Path(item.locate()).resolve().parent
    return None


def bundled_example(name: str) -> BundledExample:
    """Return paths for a named, synthetic example without fetching the network."""
    evaluation_at = _EXAMPLES.get(name)
    if evaluation_at is None:
        choices = ", ".join(sorted(_EXAMPLES))
        raise OpenMacroStateError(f"unknown bundled example {name!r}; choose: {choices}")

    repository_root = Path(__file__).resolve().parents[2]
    source_case = repository_root / "cases" / name
    source_reveal = repository_root / "reveals" / name
    if (source_case / "case.json").is_file() and (source_reveal / "reveal.json").is_file():
        return BundledExample(name, source_case, source_reveal, evaluation_at)

    case_dir = _installed_directory(f"share/openmacrostate/examples/cases/{name}/case.json")
    reveal_dir = _installed_directory(f"share/openmacrostate/examples/reveals/{name}/reveal.json")
    if case_dir is None or reveal_dir is None:
        raise OpenMacroStateError(f"bundled example {name!r} is absent from this installation")
    return BundledExample(name, case_dir, reveal_dir, evaluation_at)
