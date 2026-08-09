# Quickstart

## Requirements

- Python 3.10 or newer
- Git
- an isolated virtual environment

## Install from source

```bash
git clone https://github.com/alainresearch/openmacrostate.git
cd openmacrostate
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## Understand the two bundles

The demo uses two independent directory trees:

```text
cases/2023-banks/    prediction-time research inputs and research checksums
reveals/2023-banks/  post-resolution outcomes and separate reveal checksums
```

The research bundle contains artifacts, observations, claims, and predictions,
but no outcome path. The reveal bundle has its own `reveal.json`, artifacts,
outcomes, and checksum manifest. Keeping them physically separate makes the
pre-reveal boundary testable and allows a real reveal to be distributed or
access-controlled independently. The bundled pair is colocated only because it
is an entirely synthetic software fixture; directory separation is not DRM.

## Five research times and two availability modes

An observation keeps five concepts distinct:

1. `observed_at` — the economic period or instant the value describes;
2. `released_at` — when the source made that observation version public;
3. `vintage_at` — the timestamp of the particular version or revision carried;
4. `ingested_at` — when OpenMacroState acquired or registered it; and
5. `information_cutoff` — the latest information boundary for the research case.

`observed_at` alone never proves availability. Both availability modes require
`released_at` and `vintage_at` to be no later than the applicable boundary:

- `prospective_capture` also requires `ingested_at` no later than that boundary;
- `retrospective_authenticated` permits later ingestion only when the linked,
  checksummed artifact record carries a proof bound to the same source, exact
  content digest, and publication time no later than the boundary.

The bundled synthetic case uses `retrospective_authenticated` to exercise a
later backfill. That mode must not be described as prospective capture, and its
invented proof is not evidence about the real 2023 banking system. The pre-alpha
runtime recognizes only this explicit synthetic proof type; late-ingested real
evidence fails closed until an archive or signature verifier is implemented.

## Validate the bundled fixture

```bash
openmacrostate validate cases/2023-banks
```

For a machine-readable validation summary, add `--json`:

```bash
openmacrostate validate cases/2023-banks --json
```

To persist the deeply frozen pre-reveal record and its content root, add
`--snapshot` with a path outside the input bundle:

```bash
openmacrostate validate cases/2023-banks --snapshot build/research-snapshot.json
```

This snapshot is the eligible plaintext view intended for analysis. It contains
accepted records and an audit commitment, but no rejected observation, claim,
artifact metadata, or future value. Quarantine and rejection files are separate
validator diagnostics and must not be supplied to an AI or model during replay.

Validation verifies declared SHA-256 checksums, applies the information cutoff,
and rejects claims or predictions whose evidence is missing or ineligible. It
does not write an output directory. The command has no reveal argument: it does
not locate, open, hash, or parse anything under `reveals/`, so validation still
works when the reveal bundle is absent.

If OpenMacroState was installed from a wheel rather than a repository checkout,
run the packaged synthetic fixture with:

```bash
openmacrostate example 2023-banks --output build/example
```

The `example` command resolves the separately packaged research and reveal trees
and uses the fixture's fixed historical evaluation time. It remains synthetic.

## Run the offline demo

```bash
openmacrostate demo cases/2023-banks --reveal reveals/2023-banks --evaluation-at 2023-03-13T22:00:00Z --output build/demo
```

`--evaluation-at` is an explicit post-resolution evaluation time. It cannot be
in the future, must be at or after `reveal.not_before`, and must be no earlier
than any outcome record's `resolved_at`. The outcome's same-source artifact must
also have been published by that time. Before the gate passes, outcome bytes are
not opened.

The bundled `cases/2023-banks` case is a **synthetic teaching fixture**, not a
historical reconstruction. Every number, identifier, claim, prediction, and
outcome was invented to test the software. It requires no network connection,
data-provider account, or AI key.

A successful demo produces these nine audit outputs:

- `artifact_manifest.json` — independent research and reveal integrity records;
- `snapshot.json` — eligible pre-reveal plaintext and deterministic audit roots;
- `observations.jsonl` — observations eligible at the information cutoff;
- `quarantine.jsonl` — ineligible observations and their rejection reasons;
- `claims.jsonl` — claims whose timestamps and evidence closure are eligible;
- `rejected_claims.jsonl` — rejected claims and their evidence diagnostics;
- `predictions.jsonl` — predictions eligible for post-reveal scoring;
- `scores.json` — reveal-gated Brier scores and binary log loss; and
- `report.md` — a human-readable summary carrying the synthetic-fixture warning.

The directory also contains `.openmacrostate-output.json`, an ownership marker
used to recognize a generated directory. It is operational metadata, not a
tenth audit output.

The safe default is no overwrite: even a previous demo directory causes the
command to stop. For a deliberate repeat, append `--force`. Forced replacement
is accepted only for an empty directory or a marked output for the same case;
the command rejects unmarked non-empty directories, another case's marker,
input-bundle overlap, and unsafe generated-file links. `--force` never authorizes
writing into either the research or reveal bundle.

Treat the machine-readable outputs as the audit record and `report.md` as a
derived view. Nothing in this fixture supports an inference about the real 2023
banking system.

## Verify the installation

```bash
python -m ruff check .
pytest
```

If the command fails, include the exact command, Python version, operating system,
and complete redacted error in a bug report. Do not post credentials, restricted
data, or undisclosed vulnerabilities publicly.

## Next steps

- Read the [connector contract](connectors.md) before recording or proposing an
  official source. Network capture must be explicit and a later retrieval cannot
  be backdated into an earlier replay.
- Read the [research contract](research-contract.md) before creating a case or
  connector.
- Read the [data-license policy](data-licensing.md) before adding source material.
- Choose a contribution lane in [CONTRIBUTING.md](../CONTRIBUTING.md).
