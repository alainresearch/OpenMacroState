# Experimental accounting audit

Status: implemented as a fixed pre-alpha CLI rule. The command, report shape,
and accounting metadata may change before a stable release.

OpenMacroState's first accounting audit checks one reported balance-sheet
identity from the Federal Reserve Board's H.4.1 release:

```text
total assets = total liabilities + total capital
```

This is a deterministic consistency check, not a causal model, valuation rule,
or claim that the three values were historically available on their observation
date. The [H.4.1 source contract](fed-h41-source-contract.md) continues to govern
source, time, version, and redistribution semantics.

## Run the audit

Capture the checked-in offline fixture, validate the resulting case, and audit
the Wednesday observation date:

```bash
oms connector capture fed-h41-release \
  --start 2023-03-16 --end 2023-03-16 \
  --recording tests/fixtures/connectors/fed_h41_release/recording.json \
  --output build/fed-h41-release
oms validate build/fed-h41-release
oms audit accounting build/fed-h41-release \
  --rule fed-h41-balance-sheet-v1 \
  --observed-at 2023-03-15T00:00:00Z
```

`--observed-at` identifies the reported Wednesday stock date, not the Thursday
release-path date. Add `--json` for the experimental machine-readable report:

```bash
oms audit accounting build/fed-h41-release \
  --rule fed-h41-balance-sheet-v1 \
  --observed-at 2023-03-15T00:00:00Z \
  --json
```

The audit does not fetch from the network or alter the case. It evaluates the
case first and reads values only from `accepted_observations`; quarantined
observations can never satisfy the identity. It then re-reads the already
checksummed local H.4.1 artifact with a strict size bound, verifies its digest,
runs the current connector normalizer again, and requires the seven accepted
records to match the regenerated core records exactly.

## Fixed rule

`fed-h41-balance-sheet-v1` requires exactly one accepted observation for each
of these series:

| Role | Series |
| --- | --- |
| Total assets | `fed.h41.total_assets` |
| Total liabilities | `fed.h41.total_liabilities` |
| Total capital | `fed.h41.total_capital` |
| Selected asset component | `fed.h41.securities_held_outright` |
| Selected asset component | `fed.h41.primary_credit` |
| Selected liability component | `fed.h41.treasury_general_account` |
| Selected liability component | `fed.h41.reserve_balances` |

All seven inputs must have the requested `observed_at`, source ID
`federal.reserve.board.h41.dated_release`, unit `USD_million`, and the same
immutable artifact. Their release, vintage, and ingestion times must all equal
that artifact's core retrieval time. Missing or duplicate terms and mismatched
source, parser, cell lineage, unit, quality, time, observation ID, or artifact
boundaries fail closed.

The calculation uses decimal arithmetic:

```text
residual = total assets - total liabilities - total capital
pass when abs(residual) <= 1 USD_million
```

Two coverage checks also require the selected asset components to remain within
total assets and the selected liability components to remain within total
liabilities, with the same fixed rounding tolerance. They detect wrong columns
or mixed boundaries; they do not claim that the selected components exhaust
either side of the balance sheet.

The tolerance is fixed at exactly **1 USD million** because H.4.1 reports
rounded whole millions. It is not a percentage tolerance and cannot be changed
from the command line. A passing result exits with status 0; a failed identity
or invalid audit request exits with status 2.

## Experimental boundary

This slice deliberately does **not** add a stable public accounting schema. The
connector places provisional role and boundary metadata under the namespaced
observation extension `org.openmacrostate.accounting`, and `--json` emits an
experimental report rather than a `schemas/v1` interchange object. Consumers
must not treat either shape as compatibility-stable.

The current rule also does not:

- persist a general state graph or derived observation;
- infer causality, transmission, solvency, or policy stance;
- reconcile the four selected H.4.1 diagnostic state variables to the balance-
  sheet totals;
- join different sources, artifacts, units, entities, or observation dates; or
- authenticate an old release vintage merely because the URL contains a date.

Exact local re-normalization proves that the audited values were derived from
the preserved bytes under the named parser ruleset. It does **not** prove who
originally served unverified recording bytes or when those bytes first became
public. Source authentication and historical availability remain separate
questions in the case and artifact metadata.

A reusable state graph, user-defined identities, derived nodes, or a stable
machine contract requires a separately reviewed RFC and versioned schemas.
