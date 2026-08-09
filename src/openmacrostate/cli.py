"""Command-line interface for the deterministic OpenMacroState alpha."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from openmacrostate import __version__
from openmacrostate.api.v1.errors import OpenMacroStateError
from openmacrostate.connectors import (
    builtin_connector_ids,
    get_builtin_connector,
    list_builtin_connectors,
)
from openmacrostate.resources import bundled_example
from openmacrostate.runtime.case import CaseEvaluation, evaluate_case, score_case
from openmacrostate.runtime.connectors import run_connector
from openmacrostate.runtime.http import LiveHttpTransport, RecordedHttpTransport
from openmacrostate.runtime.jsonio import load_json, write_json, write_jsonl, write_text_atomic

_OUTPUT_MARKER = ".openmacrostate-output.json"
_OUTPUT_FILES = {
    _OUTPUT_MARKER,
    "artifact_manifest.json",
    "claims.jsonl",
    "observations.jsonl",
    "predictions.jsonl",
    "quarantine.jsonl",
    "rejected_claims.jsonl",
    "report.md",
    "scores.json",
    "snapshot.json",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openmacrostate",
        description="Audit point-in-time macro research case packs.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate", help="verify pre-reveal integrity and optionally write a sealed snapshot"
    )
    validate.add_argument("case_dir", type=Path)
    validate.add_argument("--json", action="store_true", dest="as_json")
    validate.add_argument("--snapshot", type=Path)

    demo = subparsers.add_parser(
        "demo", help="run cutoff filtering, reveal-gated scoring, and report generation"
    )
    demo.add_argument("case_dir", type=Path)
    demo.add_argument("--reveal", type=Path, required=True)
    demo.add_argument("--evaluation-at", required=True)
    demo.add_argument("--output", type=Path, required=True)
    demo.add_argument(
        "--force",
        action="store_true",
        help="replace a prior marked output for the same case",
    )

    example = subparsers.add_parser(
        "example", help="run a bundled synthetic example from a source checkout or wheel"
    )
    example.add_argument("name", choices=["2023-banks"])
    example.add_argument("--output", type=Path, required=True)
    example.add_argument("--force", action="store_true")

    connector = subparsers.add_parser(
        "connector", help="capture official-source bytes through a policy-enforced built-in"
    )
    connector_commands = connector.add_subparsers(dest="connector_command", required=True)
    list_connectors = connector_commands.add_parser(
        "list", help="list built-in review-trusted connectors and metadata"
    )
    list_connectors.add_argument("--json", action="store_true", dest="as_json")

    capture = connector_commands.add_parser(
        "capture", help="write a new, complete capture case without overwriting"
    )
    capture.add_argument("connector_id", choices=builtin_connector_ids())
    capture.add_argument("--start", required=True, help="inclusive value date, YYYY-MM-DD")
    capture.add_argument("--end", required=True, help="inclusive value date, YYYY-MM-DD")
    capture_mode = capture.add_mutually_exclusive_group()
    capture_mode.add_argument("--recording", type=Path, help="replay an exact recorded response")
    capture_mode.add_argument(
        "--online", action="store_true", help="explicitly permit one allowlisted HTTPS request"
    )
    capture.add_argument("--output", type=Path, required=True)
    return parser


def _human_summary(evaluation: CaseEvaluation) -> str:
    summary = evaluation.summary()
    return (
        f"PASS {summary['case_id']} | cutoff={summary['information_cutoff']} | "
        f"observations={summary['accepted_observations']} accepted/"
        f"{summary['quarantined_observations']} quarantined | "
        f"claims={summary['accepted_claims']} accepted/"
        f"{summary['rejected_claims']} rejected | "
        f"predictions={summary['accepted_predictions']} accepted/"
        f"{summary['rejected_predictions']} rejected | "
        f"research_checksums={summary['verified_research_files']} verified"
    )


def _report(evaluation: CaseEvaluation, scoring: Mapping[str, Any]) -> str:
    summary = evaluation.summary()
    quarantine_rows = (
        "\n".join(
            f"- `{record['observation_id']}` — {record['quarantine']['primary_reason']}"
            for record in evaluation.quarantined_observations
        )
        or "- None"
    )
    rejected_claim_rows = (
        "\n".join(
            f"- `{record['claim_id']}` — {', '.join(record['rejection']['reasons'])}"
            for record in evaluation.rejected_claims
        )
        or "- None"
    )
    score_lines = []
    for score in scoring["scores"]:
        log_loss = score["binary_log_loss"]
        rendered_log_loss = "∞" if log_loss is None else f"{log_loss:.12f}"
        score_lines.append(
            f"- `{score['prediction_id']}`: p={score['probability']:.4f}, "
            f"y={score['outcome_value']}, Brier={score['brier_score']:.4f}, "
            f"log loss={rendered_log_loss}"
        )
    score_rows = "\n".join(score_lines) or "- No accepted predictions"
    if summary["fixture_kind"] == "synthetic":
        notice = "SYNTHETIC SOFTWARE FIXTURE — NOT HISTORICAL EVIDENCE OR INVESTMENT ADVICE."
        interpretation_tail = "All values in this case were invented to test software."
    else:
        notice = "RESEARCH OUTPUT — VERIFY SOURCES, LICENSES, AND ASSUMPTIONS BEFORE USE."
        interpretation_tail = "Source limitations remain part of the audit record."
    return f"""# OpenMacroState replay report

> **{notice}**

## Case

- ID: `{evaluation.case_id}`
- Title: {evaluation.case["title"]}
- Information cutoff: `{evaluation.information_cutoff}`
- Fixture kind: `{summary["fixture_kind"]}`
- Historical evidence: `{str(summary["historical_evidence"]).lower()}`
- Network or AI used: `false`

## Pre-reveal audit

- Observations: {summary["accepted_observations"]} accepted;
  {summary["quarantined_observations"]} quarantined
- Claims: {summary["accepted_claims"]} accepted; {summary["rejected_claims"]} rejected
- Predictions: {summary["accepted_predictions"]} accepted;
  {summary["rejected_predictions"]} rejected
- Research integrity entries: {summary["verified_research_files"]} SHA-256 checks passed

### Quarantined observations

{quarantine_rows}

### Rejected claims

{rejected_claim_rows}

## Post-reveal scoring

- Evaluation time: `{scoring["evaluation_at"]}`
- Reveal not-before time: `{scoring["reveal"]["not_before"]}`
- Reveal integrity entries: {len(scoring["reveal"]["verified_files"])} SHA-256 checks passed

{score_rows}

## Interpretation

The deliberately late observation was excluded because its release and vintage
timestamps are after the cutoff. Authenticated retrospective ingestion may occur
later than the historical cutoff; ingestion time alone does not rewrite public
availability. The claim depending on the late record was rejected transitively.
The outcome bundle was supplied and verified only after pre-reveal selection had
completed and the declared reveal time had passed. {interpretation_tail}
"""


def _overlaps(path: Path, protected: Path) -> bool:
    return path == protected or path in protected.parents or protected in path.parents


def _write_demo(
    evaluation: CaseEvaluation,
    reveal_dir: Path,
    evaluation_at: str,
    output_dir: Path,
    *,
    force: bool,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    reveal_dir = reveal_dir.resolve()
    if _overlaps(output_dir, evaluation.case_dir) or _overlaps(output_dir, reveal_dir):
        raise OpenMacroStateError(
            "output directory must not be an ancestor or descendant of an input bundle"
        )
    marker_path = output_dir / _OUTPUT_MARKER
    if output_dir.exists():
        if not output_dir.is_dir():
            raise OpenMacroStateError("output path exists and is not a directory")
        entries = list(output_dir.iterdir())
        if not force:
            raise OpenMacroStateError("output directory already exists; pass --force to replace it")
        if entries:
            if marker_path.is_symlink() or not marker_path.is_file():
                raise OpenMacroStateError(
                    "refusing to replace a non-empty directory without a regular "
                    "OpenMacroState output marker"
                )
            marker = load_json(marker_path)
            if not isinstance(marker, dict):
                raise OpenMacroStateError("output marker must be a JSON object")
            if marker.get("case_id") != evaluation.case_id:
                raise OpenMacroStateError("output marker belongs to a different case")
            for name in sorted(_OUTPUT_FILES):
                target = output_dir / name
                if not target.exists() and not target.is_symlink():
                    continue
                if target.is_symlink() or not target.is_file() or target.lstat().st_nlink != 1:
                    raise OpenMacroStateError(
                        f"refusing to replace non-regular output file: {target}"
                    )
    scoring = score_case(evaluation, reveal_dir, evaluation_at=evaluation_at)
    if not output_dir.exists():
        try:
            output_dir.mkdir(parents=True)
        except OSError as exc:
            raise OpenMacroStateError(f"cannot create output directory: {exc}") from exc
    manifest = {
        "schema_version": "1.0.0",
        "case_id": evaluation.case_id,
        "fixture_kind": evaluation.case["fixture_kind"],
        "historical_evidence": evaluation.summary()["historical_evidence"],
        "algorithm": "sha256",
        "research": {
            "manifest_sha256": evaluation.research_manifest_sha256,
            "files": list(evaluation.verified_files),
        },
        "reveal": scoring["reveal"],
    }
    write_json(output_dir / "artifact_manifest.json", manifest)
    write_json(output_dir / "snapshot.json", evaluation.snapshot())
    write_jsonl(output_dir / "observations.jsonl", list(evaluation.accepted_observations))
    write_jsonl(output_dir / "quarantine.jsonl", list(evaluation.quarantined_observations))
    write_jsonl(output_dir / "claims.jsonl", list(evaluation.accepted_claims))
    write_jsonl(output_dir / "rejected_claims.jsonl", list(evaluation.rejected_claims))
    write_jsonl(output_dir / "predictions.jsonl", list(evaluation.accepted_predictions))
    write_json(output_dir / "scores.json", scoring)
    write_text_atomic(output_dir / "report.md", _report(evaluation, scoring))
    write_json(
        marker_path,
        {
            "schema_version": "1.0.0",
            "generator": "openmacrostate",
            "case_id": evaluation.case_id,
        },
    )
    return scoring


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "connector":
            if args.connector_command == "list":
                connectors_data = list_builtin_connectors()
                trust_notice = "Built-in review trust is not a third-party sandbox."
                if args.as_json:
                    output_data = {
                        "connectors": list(connectors_data),
                        "trust_notice": trust_notice,
                    }
                    print(json.dumps(output_data, ensure_ascii=False, sort_keys=True))
                else:
                    lines = [trust_notice, ""]
                    for info in connectors_data:
                        hosts = ", ".join(info["allowed_hosts"])
                        modes = ", ".join(info["capture_modes"])
                        lines.extend(
                            [
                                f"{info['connector_id']} v{info['version']}",
                                f"  Source name: {info['source_name']}",
                                f"  Allowed host: {hosts}",
                                f"  Capture modes: {modes}",
                                f"  Redistribution status: {info['redistribution_status']}",
                                f"  Documentation link: {info['documentation_link']}",
                                "",
                            ]
                        )
                    print("\n".join(lines).rstrip())
                return 0
            if args.recording is None and not args.online:
                raise OpenMacroStateError(
                    "connector capture requires exactly one of --recording or --online; "
                    "network access is never implicit"
                )
            connector = get_builtin_connector(args.connector_id)
            if args.recording is not None:
                transport = RecordedHttpTransport(args.recording)
                protected_paths = (args.recording, args.recording.parent)
            else:
                transport = LiveHttpTransport()
                protected_paths = ()
            capture = run_connector(
                connector,
                {"start": args.start, "end": args.end},
                transport,
                args.output,
                protected_paths=protected_paths,
            )
            evaluation = evaluate_case(capture.case_dir)
            print(_human_summary(evaluation))
            print(
                f"WROTE {capture.case_dir} | connector={args.connector_id} | "
                f"mode={capture.capture_mode} | observations={len(capture.observation_ids)}"
            )
            return 0
        if args.command == "example":
            example = bundled_example(args.name)
            evaluation = evaluate_case(example.case_dir)
            scoring = _write_demo(
                evaluation,
                example.reveal_dir,
                example.evaluation_at,
                args.output,
                force=args.force,
            )
            print(_human_summary(evaluation))
            print(f"WROTE {args.output.resolve()} | scores={len(scoring['scores'])}")
            return 0
        evaluation = evaluate_case(args.case_dir)
        if args.command == "validate":
            if args.snapshot is not None:
                snapshot_path = args.snapshot.resolve()
                if _overlaps(snapshot_path.parent, evaluation.case_dir):
                    raise OpenMacroStateError(
                        "snapshot output must not be inside or above the case bundle"
                    )
                if snapshot_path.exists() or snapshot_path.is_symlink():
                    raise OpenMacroStateError("snapshot output already exists")
                write_json(snapshot_path, evaluation.snapshot())
            if args.as_json:
                print(json.dumps(evaluation.summary(), ensure_ascii=False, sort_keys=True))
            else:
                print(_human_summary(evaluation))
            return 0
        scoring = _write_demo(
            evaluation,
            args.reveal,
            args.evaluation_at,
            args.output,
            force=args.force,
        )
        print(_human_summary(evaluation))
        print(f"WROTE {args.output.resolve()} | scores={len(scoring['scores'])}")
        return 0
    except OpenMacroStateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
