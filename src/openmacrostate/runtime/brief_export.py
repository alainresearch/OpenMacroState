"""Write a separate H.4.1 research brief without modifying its source bundles."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from openmacrostate.api.v1.errors import ContractError
from openmacrostate.runtime.brief import build_h41_brief
from openmacrostate.runtime.brief_render import (
    render_brief_csv,
    render_brief_html,
    render_brief_markdown,
)
from openmacrostate.runtime.case import CaseEvaluation
from openmacrostate.runtime.connectors import validate_new_output_directory
from openmacrostate.runtime.jsonio import write_json, write_text_atomic

_INCOMPLETE_MARKER = ".openmacrostate-brief.incomplete"


def validate_brief_output(
    output_directory: str | Path, *, protected_paths: Iterable[str | Path]
) -> Path:
    """Apply the capture writer's existing no-overwrite and path protections."""
    try:
        return validate_new_output_directory(output_directory, protected_paths=protected_paths)
    except ContractError as exc:
        message = str(exc).replace("connector output", "brief output")
        message = message.replace("capture never overwrites", "brief export never overwrites")
        raise ContractError(message) from exc


def export_h41_brief(
    current: CaseEvaluation,
    *,
    output_directory: str | Path,
    previous: CaseEvaluation | None = None,
) -> dict[str, Any]:
    protected = [current.case_dir]
    if previous is not None:
        protected.append(previous.case_dir)
    output = validate_brief_output(output_directory, protected_paths=protected)
    report = build_h41_brief(current, previous)
    documents = {
        "index.html": render_brief_html(report),
        "observations.csv": render_brief_csv(report),
        "brief.md": render_brief_markdown(report),
    }
    try:
        output.mkdir(mode=0o700)
        write_text_atomic(output / _INCOMPLETE_MARKER, "Brief export incomplete.\n")
        write_json(output / "brief.json", report)
        for filename, text in documents.items():
            write_text_atomic(output / filename, text)
        (output / _INCOMPLETE_MARKER).unlink()
    except OSError as exc:
        raise ContractError(f"cannot complete brief export: {exc}") from exc
    return report
