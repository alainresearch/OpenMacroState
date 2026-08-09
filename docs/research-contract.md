# Point-in-time research contract

This document is normative for replay eligibility and evidence integrity.

## Five research times

OpenMacroState distinguishes:

1. **Observation time** — the period or instant the value describes.
2. **Release time** — when the source made that observation version public.
3. **Vintage time** — the timestamp of the particular version or revision used.
4. **Ingestion time** — when OpenMacroState acquired or registered the record.
5. **Information cutoff** — the latest information boundary for the research.

These times are not interchangeable. A value describing January but released in
March is unavailable to a February cutoff. A revised value carries its own
release and vintage times, not those of the original observation. An
`observed_at` before the cutoff is therefore not sufficient for eligibility.

Timestamps should include a timezone. Date-only releases require a documented
availability convention. When availability is uncertain, the replay fails closed:
the artifact is excluded or explicitly marked ineligible.

## Eligibility rules and assurance modes

Every case declares one cutoff-policy mode. In both modes, `released_at` and
`vintage_at` must be no later than the boundary being evaluated. The runtime
applies that rule at the case cutoff and closes evidence again at each claim's
cutoff and each prediction's creation time.

- **`prospective_capture`** requires `ingested_at` no later than the applicable
  boundary. It represents material actually captured by the system in time.
- **`retrospective_authenticated`** permits ingestion after the boundary only
  when the linked artifact contains a verified availability proof identifying
  the exact source and artifact digest, a non-empty verifier and proof method,
  and a `version_released_at` equal to the artifact's `source_published_at` and
  no later than the boundary. It represents a later reconstruction and must not
  be relabeled as prospective capture.

The pre-alpha runtime implements only a deliberately labeled synthetic-fixture
proof verifier. It fails closed for late-ingested real evidence until a reviewed
archive or signature verifier exists. A Boolean `verified` field alone is never
sufficient authentication.

Late collection does not make a late release eligible. If the version itself was
released or vintaged after the boundary, the observation remains quarantined.
Likewise, a retrospective proof is only as strong as its source and review; a
synthetic fixture proves software behavior, not historical availability.

The rule applies to data, documents, prices, model inputs, news, policy statements,
and auxiliary metadata. Later outcome data belongs to evaluation, not research.

## Research and reveal separation

A research case bundle contains only prediction-time artifacts, observations,
claims, predictions, and its own integrity manifest. A post-resolution reveal
bundle is a separate directory with a separate entry point, outcome artifacts,
outcome records, activation time, license record, and integrity manifest. The
research case must not contain or point to reveal outcome bytes.

`openmacrostate validate CASE_DIR` operates only on the research bundle. It must
remain successful when no reveal path exists and must never discover or read a
reveal implicitly. Scoring requires an explicit reveal path and evaluation time.
The runtime checks `reveal.not_before` before it opens outcome bytes, verifies
the reveal independently, and requires its `case_id` to match the frozen case.
Every scored outcome must resolve to an artifact from the same source. That
artifact must have been published by `evaluation_at`; a later retrieval requires
the same bound availability-proof discipline as research evidence.

For an actual prospective exercise, the reveal bundle must also be withheld by
the surrounding distribution or access-control process until its activation
time. Filesystem separation makes the contract auditable; it is not by itself a
confidentiality mechanism.

A checksum manifest proves consistency with a declared bundle, not the identity
or truthfulness of its publisher. Someone who can rewrite both data and manifest
can produce a new internally consistent bundle. Published research should anchor
the sealed snapshot root in repository history and, where the risk justifies it,
a signed release, transparency log, or independent archive.

## Artifacts and observations

An artifact is a preserved source object or a stable reference to one. Its record
should include source identity, retrieval information, content hash when
available, media type, source terms, and release metadata.

An observation is a typed fact extracted from an artifact. It retains the source
link, unit, frequency, adjustment, observation time, release time, and revision
identity needed to reconstruct eligibility.

Frozen artifacts are append-only. Corrections create a new record that identifies
what it supersedes and why.

## Transformations

A material derived value records:

- input artifact or observation identifiers;
- code and parameter version;
- units and transformations;
- deterministic ordering and rounding rules; and
- validation or accounting checks.

Derived values cannot acquire an earlier release time than their latest required
input.

## Claims

Claims distinguish at least:

- observed fact;
- accounting implication;
- model-dependent inference;
- causal hypothesis;
- scenario; and
- forecast.

A material claim names supporting and contradicting evidence, assumptions,
mechanism, credible alternatives, confidence or uncertainty, and the authoring
agent. In the v1 executable contract, `claim.as_of` cannot be later than the
claim's `information_cutoff`; a future proposition belongs in a prediction with
a horizon, outcome variable, falsification condition, and scoring rule recorded
before the outcome is opened.

The frozen `snapshot.json` contains only eligible plaintext records and eligible
artifact metadata. Excluded records remain available to validator diagnostics
and are committed by an audit digest, but their values, statements, identifiers,
and artifact metadata are not copied into the analysis snapshot. Downstream AI
or model code receives the eligible snapshot, never `quarantine.jsonl` or the
rejected-record files.

## Evaluation

Evaluation may use evidence released after the cutoff, but must keep it in a
separate reveal phase. `evaluation_at` must not be in the future, must be at or
after `reveal.not_before`, and cannot precede an outcome's resolution time. The
original claim remains immutable. Scores, corrections, and retrospectives append
to the record and link back to it.

## AI-assisted analysis

AI may operate only on the eligible snapshot supplied to it. Prompts, model
identity, relevant parameters, tool calls, and outputs should be recorded when
they materially affect a claim. AI output is a proposal or inference, never a
source observation. The deterministic workflow must remain usable without it.

## Failure behavior

The system should stop or emit a conspicuous invalid result when it cannot verify
cutoff eligibility, provenance, required units, schema compatibility, or an
accounting invariant. Silent substitution and best-guess timestamps are not
acceptable defaults for publishable output.
