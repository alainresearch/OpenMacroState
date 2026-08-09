# OpenMacroState Roadmap

This roadmap communicates direction, not a delivery promise. Scope and sequencing
may change after public review. A version ships only when its release gates pass.

## v0.1 — Macro Time Machine

**Goal:** make one historical macro judgment reproducible under a real
point-in-time information boundary.

The current `cases/2023-banks` and `reveals/2023-banks` pair is a synthetic
software fixture. It tests the boundary but does not itself satisfy the goal of
an evidence-reviewed historical replay.

Planned capabilities:

- explicit observation, release, vintage, ingestion, and cutoff timestamps;
- immutable artifact and observation manifests;
- claims with evidence links, alternatives, horizons, and falsifiers;
- a deterministic CLI for replaying bundled cases;
- physically separate research and post-resolution reveal bundles;
- at least one polished, evidence-reviewed historical replay in addition to the
  synthetic `2023-banks` fixture;
- initial official-source connectors and synthetic test fixtures;
- human-readable and machine-readable replay output;
- unit, integration, future-leakage, and accounting-invariant tests; and
- contributor, governance, security, and data-license foundations.

Release gates:

- the documented demo succeeds from a clean supported Python environment;
- no network or AI key is required for the bundled demonstration;
- every bundled artifact has provenance and a redistribution decision;
- the replay fails closed on evidence later than the cutoff;
- output is deterministic except for declared nondeterministic metadata; and
- a new contributor can complete one scoped issue using public documentation.

## v0.2 — Dollar State Engine

**Goal:** represent and trace the balance-sheet state of the dollar system.

Candidate scope:

- Federal Reserve, Treasury, commercial-bank, dealer, non-bank, and foreign nodes;
- reserves, Treasury supply, repo, dealer balance sheets, basis, and FX swaps;
- reusable accounting identities and unit checks;
- a `trace` workflow for inspecting proposed transmission chains;
- more official-source connectors and release-calendar metadata; and
- replay cases covering distinct liquidity and funding regimes.

Graduation depends on review by both domain and software contributors. The engine
will not encode a single causal interpretation as an accounting identity.

## v0.3 — Model Adapters

**Goal:** compare models through explicit, inspectable interfaces rather than
forcing them into one theoretical framework.

Candidate adapters include public models or libraries such as HARK and other
macro, household, or fiscal frameworks whose licenses permit integration.

Each adapter must declare:

- model and upstream version;
- required inputs and units;
- outputs and uncertainty representation;
- calibration or estimation assumptions;
- institutional regime and valid domain;
- known failure states; and
- reproduction instructions.

## v1.0 — Global Macro Research OS

**Goal:** establish a stable public protocol for auditable multi-country macro
research.

Candidate scope:

- regional nodes for the United States, China, the euro area, Japan, and selected
  emerging markets;
- commodity, energy, trade, credit, and cross-asset transmission;
- stable plugin interfaces and schema migration policy;
- a reviewed library of daily, event-driven, and historical replay workflows;
- versioned documentation and long-term compatibility commitments; and
- multiple active maintainers across independent organizations.

## Continuous workstreams

The following work is not deferred to a single version:

- evidence integrity and source corrections;
- data-license and attribution review;
- security and dependency maintenance;
- documentation, examples, translations, and accessibility;
- contributor onboarding and maintainer succession;
- benchmark and evaluation design; and
- review of AI-assisted workflows for leakage and unsupported claims.

## Proposing roadmap changes

Open a GitHub Discussion for exploratory ideas. Use an RFC for changes that alter
the research contract, a public schema, compatibility, licensing, or governance.
Accepted work is represented by an Issue or milestone; appearance in this file
alone does not mean that a task is staffed.
