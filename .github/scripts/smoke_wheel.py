"""Exercise the built wheel without development dependencies or checkout imports."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def main() -> None:
    dist = Path(sys.argv[1]).resolve()
    wheels = list(dist.glob("openmacrostate-*.whl"))
    if len(wheels) != 1:
        raise SystemExit(f"expected exactly one OpenMacroState wheel in {dist}")
    repository = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)

    with tempfile.TemporaryDirectory(prefix="oms-wheel-smoke-") as directory:
        working = Path(directory)
        isolated = working / "venv"
        venv.EnvBuilder(with_pip=True).create(isolated)
        scripts = isolated / ("Scripts" if os.name == "nt" else "bin")
        suffix = ".exe" if os.name == "nt" else ""
        python = scripts / f"python{suffix}"

        def run(*arguments: str | Path) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [str(argument) for argument in arguments],
                cwd=working,
                env=environment,
                check=True,
                text=True,
                capture_output=True,
            )

        run(python, "-m", "pip", "install", wheels[0])
        run(python, "-m", "pip", "check")
        for command in ("oms", "openmacrostate"):
            run(scripts / f"{command}{suffix}", "--help")
        cli = scripts / f"oms{suffix}"
        run(cli, "example", "2023-banks", "--output", "example")
        if not (working / "example" / "scores.json").is_file():
            raise SystemExit("installed wheel did not produce the bundled example scores")
        for connector in ("frbny_sofr", "treasury_debt_to_penny", "fed_h41_release"):
            recording = (
                repository / "tests" / "fixtures" / "connectors" / connector / "recording.json"
            )
            result = run(cli, "connector", "inspect-recording", recording, "--json")
            inspected = json.loads(result.stdout)
            if (
                inspected.get("valid") is not True
                or inspected.get("source_authenticated") is not False
                or inspected.get("historical_eligibility_established") is not False
            ):
                raise SystemExit(f"unexpected installed inspector result: {inspected}")
        run(
            cli,
            "connector",
            "capture",
            "fed-h41-release",
            "--start",
            "2023-03-16",
            "--end",
            "2023-03-16",
            "--recording",
            repository / "tests/fixtures/connectors/fed_h41_release/recording.json",
            "--output",
            "h41-capture",
            "--brief-output",
            "h41-brief",
        )
        run(
            cli,
            "brief",
            "h41",
            "h41-capture",
            "--previous",
            "h41-capture",
            "--output",
            "h41-comparison",
        )
        for directory in ("h41-brief", "h41-comparison"):
            for filename in ("index.html", "observations.csv", "brief.md", "brief.json"):
                if not (working / directory / filename).is_file():
                    raise SystemExit(f"installed wheel did not produce {directory}/{filename}")
        compared = json.loads((working / "h41-comparison/brief.json").read_text(encoding="utf-8"))
        if compared["comparison"]["kind"] != "identical" or len(compared["rows"]) != 7:
            raise SystemExit("installed wheel produced an unexpected H.4.1 comparison")
        print("PASS clean wheel: CLI, example, recordings, H.4.1 brief and comparison")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(exc.stdout or "", file=sys.stderr)
        print(exc.stderr or "", file=sys.stderr)
        raise SystemExit(exc.returncode) from exc
