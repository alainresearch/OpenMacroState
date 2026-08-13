# RFC 0002: First-class macro state graph and derived-value lineage

- Status: Draft
- Authors: OpenMacroState contributors
- Shepherd: Alain Research (bootstrap project lead)
- Created: 2026-08-10
- Discussion: [GitHub Issue #24](https://github.com/alainresearch/OpenMacroState/issues/24)
- Supersedes:
- Superseded by:

## Summary

OpenMacroState should represent macro-financial state as a typed graph whose
nodes preserve economic boundary, unit, time, provenance, and epistemic status,
and whose executable derived values retain an exact path back to accepted source
observations and preserved artifacts.

The graph must keep two questions separate:

1. **What kind of statement is this?** A fact, inference, prediction, or
   scenario.
2. **Where did its value come from?** A reported observation, deterministic
   derivation, explicit assumption, or model.

That separation permits a deterministic calculation to be a derived fact
without mislabeling it as a causal inference. It also prevents an inference,
forecast, or scenario from becoming a fact merely because it appears next to
reported data.

This RFC proposes a staged contract. The first executable probe is a reversible,
experimental H.4.1 state trace over the already reviewed accounting audit. It
does not add to or change `schemas/v1`. A stable public state-graph schema may be
proposed only after the review period and evidence from the probe.

## Problem and users

The current runtime can answer whether one fixed Federal Reserve H.4.1 identity
passes. It cannot yet answer, in a reusable machine-readable form:

- which state variables participated in a result;
- which transformations produced a derived value;
- whether an arrow means arithmetic dependency, accounting identity,
  institutional exposure, or a causal hypothesis;
- when each input was observed and when it became eligible knowledge;
- which artifact and parser produced each reported value;
- whether a value is revised, disputed, unknown, assumed, or modeled; or
- which upstream facts must be removed when a source or vintage is challenged.

Macro researchers need those answers to inspect a conclusion. Connector authors
need them to avoid incompatible entity, time, boundary, and unit joins. Model
authors need a boundary between evidence and assumptions. Reviewers need to
trace a claim without trusting prose or an AI-generated explanation.

## Research-integrity effects

### The unit of synthesis

The graph joins bounded propositions and values, not expert names, personas, or
votes. Every admitted node must state its applicability and evidence boundary.
Ten commentaries that descend from one underlying artifact remain one source
family, not ten independent observations.

### Orthogonal classification

Every future stable state node must carry an `epistemic_kind`:

- `fact` — a source-reported value or a deterministic derivation whose inputs
  and transformation are completely specified;
- `inference` — a conclusion that depends on identification assumptions,
  interpretation, or uncertain reasoning;
- `prediction` — a statement fixed before a declared horizon and outcome, with
  `made_at`, target, and scoring semantics; or
- `scenario` — a conditional result under explicit interventions or assumptions.

Every value-bearing node must separately carry a `value_origin`:

- `reported` — normalized from a source artifact;
- `derived` — produced by a deterministic, versioned transformation;
- `assumed` — supplied as a declared premise; or
- `modeled` — emitted by a named, versioned model or adapter.

The combinations are constrained. The initial probe admits only `fact/reported`
and `fact/derived`. It must not synthesize inference, prediction, or scenario
nodes. A future `inference`, `prediction`, or `scenario` requires its own
contract rather than a relabeled arithmetic node.

### Accounting is not causality

An accounting equality constrains admissible values but does not identify why
they changed. A funding relationship describes institutional exposure but does
not by itself identify a shock or response. A causal hypothesis must therefore
remain distinguishable from executable derivation and accounting edges.

### Point-in-time integrity

A graph result is eligible only if all of its dependencies are eligible under
the case information cutoff. A derived node inherits a knowledge-time envelope
that is no earlier than the latest required input release and vintage. Ingestion
time remains a system fact and cannot be backdated into source availability.

An observation date, a dated URL, a scheduled release time, exact local
re-normalization, and authenticated historical availability are distinct facts.
The graph must preserve those distinctions.

## Detailed design

### 1. Two layers

The proposed design separates:

- a **state definition**, which names entities, variables, units, relations,
  transformations, assumptions, and admissibility rules; and
- a **state result**, which binds one definition to a case snapshot, information
  cutoff, exact input observations, derived values, and a canonical graph hash.

The first probe has an internal fixed definition for
`fed-h41-balance-sheet-v1`. It emits only an experimental state result. It does
not introduce a user-authored definition format.

### 2. Stable object boundaries

The future stable graph should not make one overloaded object represent a
semantic definition, a value assertion, a formula, and an audit result. It
separates at least:

- **state node** — a versioned semantic definition for an entity, boundary,
  account, instrument, or measure, including quantity kind, canonical unit,
  temporal semantics, accounting side, sign convention, and definition hash;
- **state value** — an immutable value assertion for one node and observed
  coordinate; a reported value references exactly one accepted observation,
  while a derived value references exactly one derivation;
- **state edge** — a binary institutional, classification, version, conflict,
  or topology relationship, never an implicit multi-input formula;
- **derivation** — an ordered n-ary calculation with one output, exact numeric
  and unit rules, parameters, implementation identity, and input/output hashes;
- **constraint result** — the outcome of an accounting identity or invariant,
  separate from an economic state value;
- **conflict set** — unresolved parallel assertions and any explicit resolution
  record; and
- **scenario overlay** — an immutable conditional layer over a named factual
  graph, never a mutation of the factual baseline.

Changing the meaning, boundary, unit, quantity kind, or temporal semantics of a
state node produces a new definition identity. A source revision creates a new
state value for the same compatible node; it does not rewrite the old value.

The experimental probe may project each definition and bound value together in
one display-oriented `node` object. That convenience is explicitly not the
future stable interchange design.

### 3. State-node semantics

A future stable node requires at least:

- a stable node identifier;
- `epistemic_kind` and `value_origin`;
- entity and accounting boundary identifiers;
- variable identifier, value, and unit when value-bearing;
- observation or state time;
- release, vintage, ingestion, and cutoff semantics where applicable;
- status such as present, unknown, or conflicted;
- source observation, artifact, transformation, assumption, or model lineage;
  and
- institutional regime or applicability constraints when they affect meaning.

`unknown` is never silently converted to zero, an empty string, a carried-forward
value, or a model estimate. Such a substitution creates a new assumed or modeled
node and must be visible.

The H.4.1 probe uses the entity `us.federal_reserve_banks` and boundary
`us.federal_reserve_banks.consolidated`. Its seven reported nodes retain the
source observation ID, source ID, artifact ID, four timestamps, revision link,
unit, and exact parser/artifact proof inherited from the accounting audit.

### 4. Edge semantics

The stable design may admit the following disjoint edge families:

- `derivation_dependency` — an ordered executable input to a deterministic
  transformation;
- `accounting_identity` — an equality or inequality over a common entity,
  boundary, unit, and time;
- `funding_exposure` — a sourced institutional or contractual relationship;
- `causal_hypothesis` — a non-factual proposed mechanism with assumptions,
  alternatives, falsifiers, horizon, and valid regime;
- `revises` or `supersedes` — a source-declared or contract-validated version
  relationship; and
- `conflicts_with` — unresolved incompatible evidence or definitions.

Only a reviewed derivation may produce a derived value. Multi-input arithmetic
and accounting constraints are n-ary objects rather than a misleading set of
pairwise formulas. An accounting or dependency edge must carry
`causal_interpretation: false`. A causal-hypothesis edge cannot be used as
arithmetic lineage and cannot become a fact through graph traversal.

The initial probe emits only `derivation_dependency` edges. Each edge identifies
the ordered input role, source node, target node, and explicitly states
`causal_interpretation: false`.

### 5. Derived-value lineage

Every deterministic derived node must specify:

- a transformation or rule identifier and version;
- exactly one output and exactly one of reported-observation or derivation
  origin for each value;
- exact operator and expression;
- an ordered list of input node IDs and their roles;
- input and output units;
- rounding, tolerance, missing-value, and overflow policies;
- the maximum release, vintage, and ingestion time across required inputs;
- a separately declared materialization mode and computation time, with
  nondeterministic build metadata excluded from the semantic hash;
- the case snapshot hash and upstream audit or validation hash; and
- a canonical lineage or graph hash that excludes only its own hash field.

The operator is part of identity. Reordering commutative inputs still changes the
declared lineage unless a transformation contract explicitly canonicalizes
them. A display label is not a transformation definition.

The initial H.4.1 probe exposes six derived facts in fixed topological order:

1. `liabilities_plus_capital`;
2. `balance_sheet_residual`;
3. `selected_asset_components`;
4. `unselected_assets`;
5. `selected_liability_components`; and
6. `unselected_liabilities`.

Type propagation uses explicit channels. A factual derived value may use only
factual inputs. Inference may cite facts and other named inferences but remains
inference. A prediction may cite facts and inferences but remains a prediction.
A scenario starts from a factual base plus explicit scenario overrides, and
every resulting value remains scenario output. No implicit coercion between
those channels is permitted.

### 6. Revision, vintage, and conflicts

A revision relationship is valid only when the connector or evidence contract
can establish compatible series, entity, boundary, observation period, and
source semantics. Similar labels do not prove a revision chain.

When two eligible nodes disagree and neither supersession nor error correction
is established, both remain in a conflict set. The runtime must not resolve a
conflict through model voting, source count, averaging, recency, or author
reputation unless a separately named resolution policy is declared. A resolved
view retains the excluded members and the policy that selected or transformed
them.

Current H.4.1 recordings do not authenticate old source vintages. The initial
probe therefore preserves `historical_version_authenticated: false` and does not
manufacture revision edges.

Revision selection occurs only after cutoff eligibility. The first stable
contract should admit a small explicit policy set such as exact IDs,
first-eligible release, latest-eligible vintage, or preserve-all, with
exact/fail-closed as the default. File order, ingestion order, source count, and
the current value are not selection policies. Different sources are not members
of one revision chain merely because their labels resemble each other.

### 7. Determinism and graph validity

A state result must fail closed on:

- duplicate node or edge IDs;
- an edge whose endpoint is absent;
- a derivation cycle;
- a derived node that precedes a dependency in topological order;
- mismatched entity, boundary, unit, observation time, or knowledge time;
- missing or quarantined source observations;
- a source artifact, parser, observation, timestamp, or hash mismatch;
- a reported value with no accepted observation, a derived value with no
  derivation, or a value claiming both origins;
- an undeclared transformation, assumption, model, or conflict resolution; or
- non-finite, non-canonical, or out-of-domain values.

Canonical JSON ordering, node order, edge order, and hash scope are part of the
experimental probe's reproducibility tests. They are not yet a stable wire
promise.

### 8. Experimental H.4.1 trace

The proposed CLI is:

```text
oms trace state CASE_DIR \
  --rule fed-h41-balance-sheet-v1 \
  --observed-at 2023-03-15T00:00:00Z \
  --target balance_sheet_residual \
  --json
```

`--target all` emits the full seven-reported-node, six-derived-node graph. A
specific target emits that derived node and its complete upstream closure. The
trace first runs the existing exact-artifact accounting audit once. It then
projects the verified result into deterministic state nodes and dependency
edges. It never fetches, changes the case, creates an observation, or persists a
derived node.

The JSON format is named
`experimental/openmacrostate-state-trace/1`. It includes the accounting audit
hash, source snapshot hash, artifact hash, connector ruleset, source
authentication status, historical-version status, graph nodes and edges, and a
canonical trace hash. It explicitly excludes inference, prediction, and scenario
nodes and states that graph arrows have no causal interpretation.

An accounting check may fail while the trace remains valid evidence of how the
failed result was computed. The CLI therefore emits the trace and returns status
2 when the underlying fixed audit fails.

The fixture values come from Board-reported cells, but the checked-in excerpt is
not original wire bytes and does not authenticate a 2023 vintage. The trace must
therefore retain `unverified_recording`, `historical_evidence: false`, and
`historical_version_authenticated: false`. A separate prospective live capture
may prove only that the core saw those bytes at its actual retrieval time.

The accounting residual and unselected-component remainders are diagnostics,
not economic accounts named “other assets” or “other liabilities.” Passing the
identity does not establish source truth, solvency, liquidity, policy stance, or
causal transmission.

## Compatibility and migration

This RFC does not modify any object under `schemas/v1`, the case bundle,
observation records, claims, predictions, reveal bundles, connectors, or plugin
API. Existing commands and outputs remain unchanged.

The new command and JSON shape are experimental. Before a stable schema is
introduced, a follow-up decision must define:

- versioned state-definition and state-result schemas;
- compatibility and deprecation policy;
- extension and plugin boundaries;
- conflict and revision validation rules; and
- migration from the experimental H.4.1 projection.

If the RFC is rejected, the experimental command can be removed before a stable
release without migrating case data. If accepted with changes, the probe is test
evidence rather than a compatibility constraint.

## Security, privacy, and licensing

The probe is offline and reads only an already validated case bundle. It uses the
existing bounded artifact read, path containment, regular-file, byte-length,
SHA-256, media-type, request, response, connector, parser, and exact-record replay
checks. It adds no network, plugin loading, code evaluation, user expression
language, or secret handling.

The result contains IDs, timestamps, values, and hashes already eligible in the
case. It does not embed the restricted H.4.1 HTML bytes. Existing source terms
and attribution remain controlling; a graph hash does not change data rights.

AI output is never admitted as source evidence. An AI system may explain a trace
only as an optional consumer of the same frozen evidence and must not add hidden
nodes or edges.

## Alternatives

### Keep only fixed audit reports

This is simplest but cannot answer upstream lineage queries or distinguish graph
semantics as the project expands.

### Adopt a general graph database now

Neo4j, RDF, a property-graph library, or a large ontology would add storage and
vocabulary decisions before the project has validated its smallest useful graph.
The proposal instead starts with deterministic JSON and no new dependency.

### Treat every arrow as causal

This produces an attractive diagram but violates the project charter. Most early
edges are arithmetic, accounting, or institutional, not identified causes.

### Encode the graph in `schemas/v1` immediately

That would create a public compatibility promise before the RFC review and
before revision, conflict, and cross-source semantics have adversarial evidence.

### Use expert or agent voting to resolve conflicts

Correlated models and duplicated source families would create false consensus.
The proposal preserves conflict and requires an explicit resolution policy.

## Drawbacks and risks

- A graph can make a weak story look mechanically authoritative. Explicit edge
  types and non-causal labels reduce but do not eliminate that risk.
- The experimental shape may attract downstream use before stabilization.
- Exact provenance makes outputs larger and more demanding to review.
- Cross-source alignment will be slow because entity, time, unit, and vintage
  equivalence require evidence rather than string matching.
- A fixed H.4.1 slice may overfit the first accounting example. Graduation must
  test at least one different institution or state definition.
- Hashes prove byte and transformation identity, not source truth, economic
  meaning, or historical availability.

## Test and evaluation plan

The experimental probe must demonstrate:

1. seven reported facts and six derived facts in deterministic topological
   order for `--target all`;
2. an exact upstream closure for every supported derived target;
3. correct values, operations, ordered input roles, units, entity, boundary,
   four-time envelope, source observation IDs, artifact ID, and ruleset;
4. byte-identical JSON and trace hash across repeated runs and equivalent RFC3339
   timezone spellings;
5. no inference, prediction, scenario, causal, model, or assumption node
   synthesized by the H.4.1 trace;
6. a failed accounting identity still emits a trace and exits 2;
7. raw-byte, path, SHA, parser, source, observation-ID, timestamp, unit, boundary,
   duplicate-ID, missing-endpoint, cycle, and ordering attacks fail closed;
8. no network socket or case write during trace;
9. wheel and sdist installation outside the checkout can run capture, validate,
   accounting audit, and state trace; and
10. Python 3.10 through 3.13 required CI checks remain green.

Independent red-team review must distinguish lack of a found bug from positive
proof of each claimed invariant.

## Adoption and rollback

### Stage 0 — public design review

Keep this RFC Draft for at least 14 days under the governance process. Record
material objections and alternatives in Issue #24 or the RFC pull request.

### Stage 1 — experimental probe

Ship the fixed H.4.1 trace in a pre-alpha release with no `schemas/v1` changes.
Document the exact command, limits, provenance scope, and removal risk. Collect
review evidence and contributor feedback.

### Stage 2 — contract proposal

After RFC review, either reject the direction, revise the RFC, or accept a
bounded stable design. Stable schemas require their own explicit versioning and
two-maintainer or bootstrap-equivalent review gate.

### Stage 3 — broader state engine

Only after stable semantics exist should the project add cross-source state
relations, user-authored definitions, funding edges, model adapters, or causal
hypotheses.

Rollback of Stage 1 removes the trace module, CLI branch, tests, and experimental
docs. It does not rewrite source captures, case bundles, accounting reports, or
released artifacts.

## Unresolved questions

- Should a stable contract permit a deterministic derived fact to carry a
  distinct epistemic subtype, or are the two orthogonal axes sufficient?
- How should state definitions identify institutional regime changes?
- Which revision relationships can connectors assert automatically?
- What is the minimum evidence for declaring two source series equivalent?
- Should unresolved conflicts be first-class nodes, sets, or result metadata?
- Which canonicalization rules should become stable across languages?
- How should uncertainty attach to deterministic values derived from rounded
  source data?
- Which second institutional boundary is the right graduation test?

## Decision record

Pending public review. The decision must record the outcome, evidence, material
alternatives, dissent, conflicts, and conditions for revisiting it. Opening the
RFC or shipping the experimental probe does not constitute acceptance of a
stable graph schema.
