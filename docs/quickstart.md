# Quickstart

Make an H.4.1 brief from the included recording, then open the result in your
browser. The first example runs offline after installation.

## Install the repository version

Use Python 3.10 or newer, Git, and an isolated virtual environment. The brief
workflow is available in the repository's development version;
[GitHub pre-release v0.1.0a6](https://github.com/alainresearch/OpenMacroState/releases/tag/v0.1.0a6)
does not include it. OpenMacroState is not published to PyPI.

```bash
git clone https://github.com/alainresearch/OpenMacroState.git
cd OpenMacroState
python -m venv .venv
source .venv/bin/activate
python -m pip install .
```

The command examples use a POSIX shell. In Windows PowerShell, the environment
activation command is `.venv\Scripts\Activate.ps1`; use PowerShell continuation
syntax if entering a multiline command.

Developer tools are optional for ordinary use. The [contributor setup](#contributor-setup)
installs them separately.

## Make your first brief

Run from the repository checkout:

```bash
mkdir -p build
oms connector capture fed-h41-release \
  --start 2023-03-16 --end 2023-03-16 \
  --recording tests/fixtures/connectors/fed_h41_release/recording.json \
  --output build/h41-capture \
  --brief-output build/h41-brief
```

Open `build/h41-brief/index.html` in your browser. It shows seven reported
Wednesday stock values in `USD_million`, an accounting check, and the source
record. Copy the table into a spreadsheet, or use the CSV and Markdown downloads.

This recording is a **`test_only_excerpt`**: a small derived HTML fixture with
seven reported H.4.1 values. Its date identifies the release being illustrated;
it does not authenticate the exact version available in 2023. Its source and
receipt-time claims remain unverified, and the brief displays that status.
No AI key or network request is needed for this example.

The two output directories serve different purposes:

| Directory | Contents |
| --- | --- |
| `build/h41-capture` | Preserved artifact, observations, provenance, and capture case |
| `build/h41-brief` | `index.html`, `observations.csv`, `brief.md`, and experimental `brief.json` |

Choose new output paths when repeating the example. Brief output must be a new
directory with an existing parent, outside the input capture directories; it
has no `--force` option.

## Rebuild a brief from a saved capture

The saved capture can be reused without repeating acquisition:

```bash
oms brief h41 build/h41-capture --output build/h41-brief-copy
```

This command works offline. It verifies and reads the capture, then writes the
four report files in the new output directory. It does not modify the capture.
The [brief guide](h41-brief.md) describes the checks and experimental format.

## Try a comparison offline

Replay the same fixture a second time, after the first capture above:

```bash
oms connector capture fed-h41-release \
  --start 2023-03-16 --end 2023-03-16 \
  --recording tests/fixtures/connectors/fed_h41_release/recording.json \
  --output build/h41-capture-again
oms brief h41 build/h41-capture-again \
  --previous build/h41-capture --output build/h41-comparison
```

Open `build/h41-comparison/index.html`. Because both inputs replay the same
fixture, this demonstrates unchanged bytes and values, rather than a real
period-to-period movement. Each replay records the core replay time; it does
not create a new economic observation. Each delta is the
current value minus the previous value.

For research use, supply a separately saved earlier capture as `--previous`.
The brief distinguishes a new observation period from changed values or changed
source bytes for the same period. It does not label these differences an
authenticated official revision. A missing or invalid capture causes an error;
it does not produce a zero-change report. See [comparison rules](h41-brief.md#comparison-rules).

## Explicit online capture

For a real official response, select `--online` instead of `--recording`.
This example retrieves a known dated release today:

```bash
oms connector capture fed-h41-release \
  --start 2023-03-16 --end 2023-03-16 --online \
  --output build/h41-live-capture \
  --brief-output build/h41-live-brief
```

This is an intentional HTTPS request to the Federal Reserve Board. The output
records the bytes retrieved now; it is not proof of what was available in 2023.
For a different release, consult the [official release index](https://www.federalreserve.gov/releases/h41/default.htm)
and set both dates to that release date. The connector does not select the
latest release automatically. Source rights remain governed by the
[H.4.1 source contract](fed-h41-source-contract.md).

## Synthetic research demo

The separate `2023-banks` teaching fixture exercises research cutoffs and
post-resolution scoring. Every value, claim, prediction, and outcome is invented.
It needs no network connection, data-provider account, or AI key.

```bash
oms validate cases/2023-banks
oms demo cases/2023-banks --reveal reveals/2023-banks \
  --evaluation-at 2023-03-13T22:00:00Z --output build/demo
```

`cases/2023-banks` holds research inputs and their checksums;
`reveals/2023-banks` holds outcomes and separate checksums. `validate` does not
locate, read, or hash the reveal. `demo` requires both paths and the explicit
evaluation time; it rejects evaluation before the reveal gate without reading
outcome bytes. The packaged equivalent is
`oms example 2023-banks --output build/example`.

A successful demo produces nine audit outputs:

- `artifact_manifest.json` — research and reveal integrity records;
- `snapshot.json` — eligible pre-reveal plaintext and deterministic audit roots;
- `observations.jsonl` — eligible observations;
- `quarantine.jsonl` — ineligible observations and their reasons;
- `claims.jsonl` — eligible claims;
- `rejected_claims.jsonl` — rejected claims and their reasons;
- `predictions.jsonl` — predictions eligible for scoring;
- `scores.json` — gated Brier scores and binary log loss; and
- `report.md` — actual audit counts, rejection reasons, and scoring results.

The directory also contains `.openmacrostate-output.json`, an ownership marker.
The demo refuses existing outputs by default. Its separate `--force` option
allows only an empty directory or a marked output for the same case, never an
input bundle. The brief command has no equivalent overwrite option.

For a machine-readable validation result, use
`oms validate cases/2023-banks --json`. To save the eligible research snapshot,
use `oms validate cases/2023-banks --snapshot build/research-snapshot.json`.
Keep quarantine and rejection diagnostics out of an analysis process: their
future metadata is not part of the eligible research view.

## Understand the time boundary

The research model separates observation, release, vintage, ingestion, and
research cutoff. Observation dates alone cannot establish when a version was
available. Current official-source captures use conservative core capture or
replay times for availability; an old date in a URL or recording is insufficient
historical proof.

The synthetic demo exercises `retrospective_authenticated` with an explicitly
invented proof. Real late-ingested evidence remains ineligible until a reviewed
historical authentication path is available. The brief leaves that boundary
unchanged. Read the [research contract](research-contract.md) for the full
five-time model and [connector contract](connectors.md) for capture semantics.

## Contributor setup

For editing the source and running the checks, install the development extras:

```bash
python -m pip install -e '.[dev]'
python -m ruff check .
pytest
```

If a command fails, include the command, Python version, operating system, and
redacted error in a bug report. Useful next reading:

- [H.4.1 brief guide](h41-brief.md)
- [Connector trust and capture contract](connectors.md)
- [Data licensing](data-licensing.md)
- [Contribution guide](../CONTRIBUTING.md)
