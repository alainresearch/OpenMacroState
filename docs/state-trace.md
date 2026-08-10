# Experimental H.4.1 state trace

Status: implemented as a fixed, read-only pre-alpha probe. The command and JSON
shape are experimental and are not part of `schemas/v1`.

OpenMacroState can trace each deterministic value in its fixed Federal Reserve
H.4.1 accounting audit back through the arithmetic dependencies, seven accepted
reported observations, one preserved source artifact, the connector ruleset,
and the sealed case snapshot.

This answers a narrow question:

> Which verified reported facts and exact operations produced this value?

It does not answer why the balance sheet changed.

## Run a trace

First create and validate the same offline H.4.1 capture used by the accounting
audit:

```bash
oms connector capture fed-h41-release \
  --start 2023-03-16 --end 2023-03-16 \
  --recording tests/fixtures/connectors/fed_h41_release/recording.json \
  --output build/fed-h41-release
oms validate build/fed-h41-release
```

Trace the accounting residual:

```bash
oms trace state build/fed-h41-release \
  --rule fed-h41-balance-sheet-v1 \
  --observed-at 2023-03-15T00:00:00Z \
  --target balance_sheet_residual
```

Add `--json` for the deterministic machine-readable result. Use `--target all`
to emit the complete fixed graph. The supported derived targets are:

- `liabilities_plus_capital`;
- `balance_sheet_residual`;
- `selected_asset_components`;
- `unselected_assets`;
- `selected_liability_components`; and
- `unselected_liabilities`.

A specific target returns only that node and its complete upstream closure. Node
and edge order is topological and deterministic.

## What the graph represents

The full graph contains seven `fact/reported` nodes and six `fact/derived`
nodes. These are two separate dimensions:

- `epistemic_kind: fact` says what kind of proposition the node represents;
- `value_origin: reported|derived` says how its value entered the trace.

No inference, prediction, or scenario node is synthesized. Every edge is named
`derivation_dependency` and carries `causal_interpretation: false`. The arrows
mean “is an ordered arithmetic input to,” not “causes,” “drives,” or
“transmits to.”

The residual and unselected-component remainders are diagnostics. They are not
economic accounts called “other assets” or “other liabilities.”

## Lineage and time

Before constructing a trace, the runtime executes the existing accounting audit
exactly once. That audit:

1. reads only observations already accepted under the case cutoff;
2. reopens the preserved H.4.1 HTML with path and size limits;
3. verifies byte length, SHA-256, artifact identity, request and retrieval
   metadata;
4. re-runs `fed-h41-release-normalization/3`; and
5. requires all seven regenerated core observations to match exactly.

Reported nodes retain their observation, source, artifact, observation time,
release time, vintage time, ingestion time, and revision reference. A derived
node carries the maximum release, vintage, and ingestion timestamps of its
required upstream inputs. Those are lineage clocks, not a claim that the value
was computed at the historical observation time.

The top-level `audit_sha256`, source-snapshot hash, artifact hash, parser
ruleset, and source-authentication fields are inherited into the trace. The
`trace_sha256` commits to the canonical report with only that self-referential
field excluded.

## What the proof does not establish

The checked-in fixture is a small `test_only_excerpt` containing real reported
values. It is not exact original wire bytes and is not an authenticated 2023
vintage. The trace therefore remains:

- `materialization_mode: retrospective_reconstruction`;
- `source_authentication: unverified_recording`;
- `historical_evidence: false`; and
- `historical_version_authenticated: false`.

Exact local re-normalization proves how preserved bytes mechanically produced
the accepted records. It does not prove who originally served an unverified
recording, when the source first published those bytes, that the figures are
economically true, or that a researcher computed the derived value in 2023.

An accounting pass also does not prove liquidity, solvency, policy stance,
valuation, or a causal mechanism. Source rights continue to apply to every
trace; derived metadata does not automatically become unrestricted or
Apache-2.0 data.

## Failure behavior

The trace is offline and does not alter the case. Source bytes, timestamps,
units, IDs, parser metadata, graph endpoints, topology, or hash drift fail
closed. A valid trace of a failed accounting identity is still emitted so the
failure can be inspected, but the CLI exits with status 2.

The future stable state-graph design is under public review in
[RFC 0002 Draft PR #25](https://github.com/alainresearch/OpenMacroState/pull/25).
The probe does not prejudge acceptance of that stable design.
