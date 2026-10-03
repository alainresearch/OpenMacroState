# RFC 0001 review packet

Prepared against RFC revision `04ceff8b231daa4278605ff8f9a95e54efaed93e`
on 2026-10-03. This is a working sheet for the
[Draft H.4.1 canary](0001-2023-us-bank-stress-replay.md), not a new proof
contract, approval, or historical evidence bundle. All decisions below are
pending; `historical_evidence: false` remains in force. The formal comment
window has not started. The [existing RFC process](README.md) governs decisions.

## Start here

Read the [September 5 scope and review update](https://github.com/alainresearch/OpenMacroState/pull/18#issuecomment-5550865364)
and the RFC's [unresolved questions](0001-2023-us-bank-stress-replay.md#unresolved-questions).
Review exact-version proof and lawful offline reproduction first. Resolve the
report and resolver contract after those feasibility questions; a larger state
graph is [deferred](https://github.com/alainresearch/OpenMacroState/pull/25#issuecomment-5550839897).

The source locators to inspect are fixed:

| Candidate | Original-source entry point | Cell and gate to check |
| --- | --- | --- |
| Research | [March 9 HTML](https://www.federalreserve.gov/releases/h41/20230309/h41.htm) | Table 1 / Primary credit / Wednesday March 8; `USD_million`; exact version available by `2023-03-11T04:59:59Z` |
| Reveal | [March 16 HTML](https://www.federalreserve.gov/releases/h41/20230316/h41.htm) | Table 1 / Primary credit / Wednesday March 15; `USD_million`; exact version available by the separate evaluation gate `2023-03-18T04:00:00Z` |

These are locators, not authenticated historical payloads. This document belongs
to the public design/control material and must never enter research inputs: it
contains the future reveal locator and gate. Do not add an outcome value here.

Existing implementation context: the [H.4.1 source contract](../fed-h41-source-contract.md),
[parser](../../src/openmacrostate/connectors/fed_h41_release.py),
[collection contract](../../schemas/v1/collection.schema.json), and
[fixture notice](../../tests/fixtures/connectors/fed_h41_release/NOTICE.md).
The fixture is a test excerpt; none of these authenticates a 2023 version.

## Material the preparer still needs to supply

This change supplies no archive payload, proof candidate, rights determination,
implementation, or independent review. Design reviewers can identify gaps now;
concrete admission findings need the following material in the appropriate
separate review:

- **One research candidate and one separate reveal candidate.** For each, list
  the original URL, archive authority and record ID, claimed archive timestamp,
  retrieval recipe, exact-payload digest/length and decoding boundary, retained
  proof-item digests, actual retrieval time, proposed verifier/version, trust
  assumptions, and missing material. Follow the RFC's
  [proof contract](0001-2023-us-bank-stress-replay.md#exact-version-proof-contract).
  A current download or an unbound CDX entry does not fill this gap.
- **An item-level rights ledger.** Cover each source payload and proof item,
  with the terms locator, attribution, proposed retention/redistribution scope,
  and a reproducible local acquisition route if public bundling is unavailable.
  Use the [data policy](../data-licensing.md) and the RFC's
  [rights boundary](0001-2023-us-bank-stress-replay.md#rights-and-offline-reproduction);
  mark unresolved rights as unresolved.
- **A small implementation proposal after feasibility review.** Specify the
  proof verifier interface, unscored report fields, research/reveal layout,
  exact resolver behavior, and tests. Identify any public-contract change for
  its applicable review; do not put new fields into `schemas/v1` via this sheet.

Keep candidate payloads and proof ledgers on their respective research or
reveal side. A public review index may reference both, but is control material
and must not become an analysis-readable shared manifest.

## Questions and concrete review outputs

| Review coverage to arrange | Question requiring a decision | Evidence and sufficient review output |
| --- | --- | --- |
| Provenance/time | Does the proposed authority and verification method bind the exact original payload to the relevant gate, including archive rewriting/compression and source attribution? | Inspect both separate candidate/proof records. Record the trust assumptions, missing proofs, and a reproducible offline verification recipe. Explain how altered bytes, fabricated timestamps, wrong original URL, transformed viewer responses, and conflicting versions are rejected. If either candidate cannot establish its gate, record that historical admission is unavailable. |
| Rights | Can a new reviewer lawfully obtain and retain the exact source and proof bytes needed for offline verification? | Review every rights-ledger item, including archive material and non-table HTML content. Record supported permissions and unresolved restrictions. Where bundling is unavailable, assess the exact-version acquisition route; a sanitized derivative requires a reviewed binding to its original. An unsupported route remains a blocker. |
| Macro/extraction, separate from source/provenance review | Are both cells the specified Wednesday Primary credit stocks in `USD_million`, and is the 10× comparison economically bounded and reproducible? | Record the release, table/row/header, observation date, unit, and extraction locator for each candidate. Verify the fixed baseline 4,581 and integer threshold 45,810 from the baseline cell; require the outcome to be extracted at evaluation. Check that weekly averages and neighboring facilities fail, and that the result makes no flow, solvency, causal, or forecasting claim. |
| Runtime/security | Can the proposed verifier and unscored resolver preserve the frozen inputs and fail before reading reveal material when the gate is closed? | Review the proposed report/proof representation and compatibility impact. Map the RFC's acceptance cases to tests: no pre-gate reveal reads or hashes; no URL/digest/filename leakage into research; below/equal/above threshold; missing/wrong cell, date, unit, or proof rejection; clean offline reproduction; no backdated metadata or prediction record. Flag any required schema/security review separately. |

These are review subjects, not appointments or a new approval rule. The shepherd
is @alainresearch in the existing bootstrap capacity. Independent coverage is
still to be arranged; the owner or an AI-assisted audit cannot fill an
independent-review slot by relabeling their work.

## Return a bounded review record

Each reviewer can use this short record, with links to findings on the existing
[PR #18](https://github.com/alainresearch/OpenMacroState/pull/18):

```text
Reviewed RFC commit and review date:
Reviewer, relevant expertise, role, and disclosed conflicts:
Scope: design / implementation / concrete evidence admission
Question(s) and candidate/proof or implementation identifiers reviewed:
Finding: supported within stated scope / needs changes / unable to assess
Evidence, reproduction steps, and observed results:
Blocking gaps, requested change, and condition for reconsideration:
Items not reviewed:
```

Leave identity, findings, and evidence fields unfilled until a real review is
performed. A design finding must not be presented as implementation validation
or concrete historical evidence admission. Link material dissent and retain
unresolved questions rather than counting a checklist as consensus.

## Handoff acceptance

- [ ] Each requested review has named coverage and an explicit scope; no
  appointment or approval is inferred from this packet.
- [ ] Proof and rights findings identify a feasible candidate route or state
  exactly why it remains blocked; absent material is visible.
- [ ] The bounded design questions have recorded findings and unresolved
  objections, ready for the shepherd to handle under the existing RFC process.
- [ ] Implementation and concrete evidence admission are still tracked as
  separate decisions under the RFC's [adoption steps](0001-2023-us-bank-stress-replay.md#adoption-review-and-rollback).

Completing this handoff does not start the public decision clock, accept the
RFC, authorize release, or change `historical_evidence: false`. Codex assisted
the preparation of this worksheet; no independent approval is claimed.
