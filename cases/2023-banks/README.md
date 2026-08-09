# 2023 Banks synthetic research Case Pack

This is a completely offline software-test fixture. It contains no real bank
data and makes no historical claim.

## Research-bundle contract

- `case.json` is the only entry point for prediction-time research.
- `inputs/artifacts.jsonl` resolves every observation `artifact_id` to a local,
  content-addressed source object under `artifacts/`.
- Four observations describe versions released before the cutoff but registered
  on 2026-08-09. They are eligible only under
  `availability_mode: retrospective_authenticated` because their artifact has a
  verified version-release proof no later than the cutoff.
- The deliberate trap has `observed_at` before the cutoff but `released_at` and
  `vintage_at` after it. Authentication does not make a late version eligible.
- `inputs/claims.jsonl` contains two eligible descriptive claims and one claim
  that must be rejected transitively.
- `inputs/predictions.jsonl` freezes a fixed-probability baseline exactly at the
  research cutoff.
- `expected/assertions.json` contains research-phase assertions only.
- `checksums/sha256.json` covers every contract-bearing research file except
  itself. It contains no post-resolution material.

Post-resolution material is distributed as a separate reveal bundle outside
this case directory. A research validator must not need that bundle.

All JSON files are standard JSON and all JSONL files contain one standard JSON
object per line. No YAML parser or network access is required.
