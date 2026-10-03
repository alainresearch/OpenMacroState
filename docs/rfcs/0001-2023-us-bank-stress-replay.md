# RFC 0001: Unscored H.4.1 primary-credit evidence canary

- Status: Draft — awaiting independent review
- Authors: @alainresearch (with disclosed AI assistance)
- Shepherd: @alainresearch (bootstrap project lead; not an independent reviewer)
- Created: 2026-08-10
- Revised: 2026-09-05
- Discussion: [GitHub Issue #11](https://github.com/alainresearch/OpenMacroState/issues/11)
- Review window: Not started; start and earliest decision timestamps unrecorded
- Supersedes:
- Superseded by:

## Summary

Build a small, unscored evidence canary around two dated Federal Reserve H.4.1
HTML releases. The question is mechanical:

> Does the Primary credit Wednesday stock in the March 16, 2023 release reach
> at least ten times the same stock in the March 9, 2023 release?

The research cutoff is `2023-03-11T04:59:59Z`, or March 10 at 23:59:59 in New
York. The baseline cell is Table 1, Primary credit, Wednesday March 8, in the
March 9 release. Its expected reported value is USD 4,581 million. The fixed
multiplier is 10; the resolver must extract the baseline and compute the
threshold, rather than accept an asserted result. The outcome cell is Table 1,
Primary credit, Wednesday March 15, in the March 16 release.

This is a present-day reconstruction designed with knowledge of history. It
contains no prediction probabilities, Brier scores, log scores, auxiliary
events, or model performance claims. The exercise tests evidence admission,
exact extraction, arithmetic, and research/reveal separation. It does not yet
fulfil the roadmap's complete real historical macro-judgment milestone.

This revision is a design proposal only. It admits no source bytes, changes no
runtime or schema, and implements no canary. Source evidence remains
`historical_evidence: false` until a reviewed proof contract and its separately
reviewed implementation support the exact historical availability claim.

## Problem and users

The existing `cases/2023-banks` and `reveals/2023-banks` directories contain a
synthetic fixture. They demonstrate software behavior but cannot authenticate a
real 2023 information set. Keep them unchanged.

A two-release canary gives source, software, and macro reviewers a tractable
way to examine three independent questions:

1. Which exact bytes were available by the relevant historical gate?
2. Which table cells and operations produced the result?
3. Can research inputs remain isolated from later evidence and its metadata?

A successful replay demonstrates only those bounded properties. A primary-credit
stock is neither a lending flow nor a count of borrowing banks. Its change does
not establish solvency, the distribution of stress, the use of all emergency
facilities, or a causal mechanism. Broader economic claims and competing
mechanisms belong to a later case design with its own evidence and review.

## Research-integrity effects

### Time and retrospective construction

The design keeps four different concepts visible:

- the Wednesday observation date represented by a reported stock;
- independently supported availability of the exact source version;
- the current system's actual retrieval and construction times; and
- the historical research cutoff or reveal gate being tested.

The current construction time must never be backdated. `made_at` belongs to the
prediction contract and is not a place to store this unscored reconstruction.
No dummy prediction, invented historical probability, or adjusted timestamp may
be used to make the current runtime admit the case.

The implementation proposal must define how actual construction/retrieval
metadata and historical eligibility coexist without conflating them. The field
names used in this RFC describe requirements, not additions to `schemas/v1`.
A dated URL, source authority, present-day checksum, page release date, scheduled
publication hour, or self-reported recording timestamp is insufficient to prove
when the exact bytes were public.

Until the proof contract, rights decisions, implementation, and case evidence
pass their respective review gates, the candidate remains unauthenticated and
ineligible as evidence at the 2023 cutoff. A local parser demonstration may run
under honest present-day metadata, but must not be presented as an admitted
historical replay.

### Fixed economic and extraction boundary

| Role | Dated release | Exact source locator | Observation date | Unit |
| --- | --- | --- | --- | --- |
| Research baseline | 2023-03-09 | Table 1 / Primary credit / Wednesday | 2023-03-08 | `USD_million` |
| Reveal outcome | 2023-03-16 | Table 1 / Primary credit / Wednesday | 2023-03-15 | `USD_million` |

Only these two reported stocks participate in the comparison. The resolver must
bind labels to the release's actual Wednesday column and verify the observation
date, table heading, unit, source URL, and release date. A weekly average, a
neighboring row, another facility, a current series, or a later revision cannot
substitute for either cell. Other cells present in the preserved HTML do not
become additional economic targets.

## Detailed design

### Source inventory and control-plane boundary

The two intended original-source URLs are:

- Research: [H.4.1 HTML, March 9, 2023](https://www.federalreserve.gov/releases/h41/20230309/h41.htm).
- Reveal: [H.4.1 HTML, March 16, 2023](https://www.federalreserve.gov/releases/h41/20230316/h41.htm).

This RFC is a public design/control document. It is not part of the research
archive or an input to an analysis process. Its knowledge of a future release
and its locator must not leak into historical research inputs. The frozen
comparison rule and planned target observation date may be declared before
resolution; realized future evidence and its metadata may not.

HTML matches the current H.4.1 connector's source format. PDF, current time
series, additional institutions, SOFR, Treasury data, closure events, and policy
announcements are outside this phase. The current connector captures/replays
HTML conservatively and does not authenticate old vintages; merely using that
connector does not satisfy the historical proof requirement.

### Exact-version proof contract

For each candidate artifact, a source-specific proof record must bind:

1. The original HTTPS source URL and its requested release date.
2. The independent archive or timestamp authority, its capture timestamp, and
   the basis for trusting that authority's timestamp and source attribution.
3. A stable archive record identity, such as CDX index identity and WARC record
   location/identifier when available, plus the corresponding retrieval recipe.
4. The original response payload's exact digest and byte length. Specify the
   digest algorithm, decoding boundary, and how an archive wrapper, rewritten
   links, compression, or transformed replay response is distinguished from
   the original payload. A digest of an archive viewer page is insufficient.
5. The proof material needed to reproduce the binding, each item's own digest,
   the actual present-day retrieval time, and the verifier identity/version.
6. The historical gate being claimed and the verification result, including
   missing evidence, uncertainty, conflicts, or later corrections.

For research, the verified capture must establish public availability of the
exact baseline payload no later than `2023-03-11T04:59:59Z`. For reveal, the
payload must satisfy the separately declared evaluation availability boundary.
This first design retains `reveal_not_before: 2023-03-18T04:00:00Z`; it is a
fixed reveal gate, not an auxiliary-event window or a publication timestamp.
Evaluation at that gate requires proof that the exact reveal version was
available by then. If no acceptable proof exists, the canary fails admission;
the implementation must not silently widen the gate or substitute today's page.

An archive timestamp is evidence from a named authority, not a cryptographic
proof of every assertion the source makes. Review must decide whether the
specific authority, payload binding, completeness, and offline verification
material are sufficient. A CDX entry alone does not authenticate arbitrary
locally supplied bytes. Archive unavailability, digest mismatch, ambiguous
payload identity, missing proof, or unsupported trust must fail closed.

This RFC does not choose an already accepted proof authority or assert that
suitable archive records have been obtained. The proof format, trust assumptions,
and any necessary public-schema or security-boundary changes need explicit
review before admission.

### Rights and offline reproduction

Each source payload and each retained archive/proof artifact needs an individual
rights decision, attribution, permitted-use scope, and redistribution status.
Repository Apache-2.0 licensing does not relicense source or archive material.

The [Board disclaimer](https://www.federalreserve.gov/disclaimer.htm) is a
starting source for review, not blanket permission for every byte in a full
HTML response. Site chrome, scripts, logos, trademarks, and third-party material
require attention. Archive access also does not itself confer redistribution
rights. Do not infer permission for a complete response from an approved table
excerpt.

Offline verification requires local checksummed source bytes and all proof
material needed by the accepted verifier. A reference-only URL cannot satisfy
that requirement. If bytes cannot be bundled publicly, specify a lawful local
acquisition procedure, preserve the exact identified version, and demonstrate
that subsequent verification works offline. The public release must state what
is omitted and whether a fresh reviewer can actually acquire it.

A sanitized excerpt has a different digest and cannot silently replace the
original payload bound by an archive proof. If an extraction derivative is used,
its deterministic derivation, original-payload binding, and rights must be
reviewed. If neither a lawful reproducible acquisition route nor a reviewed
derivative route is available, the case remains blocked.

### Research and reveal separation

Use a new research/reveal pair with separate directories, manifests, checksum
roots, and source/proof ledgers. Do not place both bundles beneath an
analysis-readable archive or shared recursively hashed manifest.

The research side contains only the admitted baseline evidence, its eligible
provenance, and the frozen comparison specification. It must contain no reveal
payload, outcome value, result, reveal source URL, content digest, archive
identifier, later report, or summary derived from them. A checksum or filename
can leak future information just as prose can.

A distinct reveal-building role creates the reveal manifest only after the
research manifest and rule are frozen. Roles and actual execution times must be
recorded honestly; this sequencing does not erase the author's prior historical
knowledge or turn the construction into a forecast. Lack of an independent
human reviewer cannot be remedied by relabeling an AI run as that reviewer.

The evaluation controller keeps reveal locators, proof material, and the reveal
gate outside analysis inputs. Before the gate, evaluation must reject without
reading or hashing reveal payloads or their metadata. At or after the gate, it
may open the separate reveal bundle only under the accepted proof and rights
contract. The resulting comparison report belongs to the evaluation side, never
back in the frozen research archive.

### Deterministic threshold resolver

The proposed rule is `primary-credit-10x-v1`:

1. Verify the two admitted payloads and their exact source/version identities.
2. Extract the two fixed Table 1 / Primary credit / Wednesday cells, checking
   the dates and `USD_million` units stated above.
3. Require the baseline to equal the fixed expected 4,581 `USD_million`; reject
   a changed value or cell identity instead of silently redefining the target.
4. Compute `threshold = 10 * baseline` using exact integer arithmetic, then
   `threshold_met = outcome >= threshold`. Equality meets the threshold.
5. Emit an evaluation report binding the inputs, extraction/parser identity,
   rule version, multiplier, units, computed threshold, comparison result,
   historical proof status, and frozen research/reveal manifest identities.

The expected threshold is 45,810 `USD_million`, but the implementation must
recompute it. This document deliberately provides no asserted outcome value or
precomputed comparison result for the resolver to copy. Missing, malformed,
negative, non-finite, mismatched, or unverified inputs must not become zero,
carried-forward values, or assumed results.

The implementation proposal must specify the unscored report contract and its
compatibility boundary. It must not manufacture a prediction record or invoke
forecast scoring to carry this Boolean comparison. Any public contract or
security-boundary change requires its own applicable RFC/review gate; this
proposal does not authorize a case-specific bypass of existing validation.

## Alternatives and scope decisions

The wider banking-stress case is deferred. More institutions, auxiliary events,
causal hypotheses, and probabilities multiply source and interpretation burdens
before the two-release evidence path works. This canary is an intermediate
step; a broader case can follow with reviewed scope and evidence.

Current downloaded pages and synthetic excerpts are useful for parser tests,
but cannot stand in for authenticated historical payloads. Current series, dated
PDFs, or another source format require separate source/extraction contracts and
are not silent fallback routes.

A stable graph, cross-source state engine, or model adapter is unnecessary for
this comparison. Existing experimental tooling may inform implementation, but
neither its existence nor its test results accept a new proof contract.

## Compatibility and migration

This PR changes documentation only. It does not modify `schemas/v1`, connectors,
case data, reveal data, the synthetic fixture, or runtime acceptance rules.
Implementation and evidence admission remain separate reviewable changes.

The design must be evaluated against current main before implementation; the
Draft branch's age must not freeze obsolete connector or runtime assumptions.
Existing experimental outputs are not a compatibility promise for a new proof
or unscored report format.

## Test and evaluation plan

An implementation and candidate evidence set cannot graduate until:

1. A source/provenance reviewer and a separate macro reviewer check each source
   identity, locator, Wednesday date, unit, extraction, timestamp rationale, and
   the limited economic interpretation. Rights decisions receive qualified
   review, with actual reviewers and conflicts recorded.
2. Both exact payloads pass the accepted availability verifier for their gates.
   Fabricated archive metadata, a transformed viewer response, wrong original
   URL, missing proof, conflicting versions, or an altered digest fail closed.
3. Research and reveal manifests are physically separate and frozen in the
   declared role/order sequence. Leakage scans reject future values, result
   fields, URLs, paths, digests, archive identifiers, and summaries on the
   research side.
4. Offline reproduction from a clean supported environment verifies the same
   local bytes, accepted evidence set, extraction locators, semantic report,
   and deterministic hashes without network access. Actual retrieval/build
   metadata stays truthful and is separated from deterministic semantic hashes.
5. Substituting a weekly average, neighboring row, wrong observation date,
   release, unit, later revision, or current download fails. Dropping or
   replacing a proof item must not preserve historical eligibility.
6. The resolver calculates both the threshold and comparison from admitted
   cells. Focused synthetic boundary tests cover below, equal to, and above
   the threshold, and are clearly labeled software tests rather than source
   evidence. A changed baseline, multiplier, rule, or input identity changes
   the frozen commitment or fails validation.
7. Evaluation before the gate fails without reading or hashing reveal material.
   Evaluation at the gate succeeds only when the separate reveal proof and
   rights requirements pass. No evaluation output mutates research inputs.
8. No probability, forecast score, backdated `made_at`, automatic historical
   admission, or causal claim is emitted. `historical_evidence: false` remains
   visible wherever historical admission has not been approved.

No test pass alone establishes source truth, historical publication, or rights.
Independent review must assess those claims within the recorded trust model.

## Adoption, review, and rollback

The repository owner, @alainresearch, serves as shepherd in the existing
bootstrap maintainer capacity. This names the person coordinating the proposal;
it neither creates a new repository role nor supplies independent review.

The formal minimum 14-day public comment window has **not started**. Keep the
RFC Draft while this narrowed scope and qualified independent review coverage
are arranged. The shepherd must post the UTC start timestamp and earliest
possible decision timestamp on the PR when review formally begins. Substantial
scope or proof-contract changes require a renewed review window; elapsed Draft
age does not count as acceptance.

Follow the [RFC process](README.md) and
[governance bootstrap exception](../../GOVERNANCE.md). Seek the strongest
available independent review and do not waive provenance, licensing, or security
requirements because the relevant area lacks registered maintainers. AI-assisted
editing or audit is disclosed work, not an independent human approval.

Adoption proceeds through distinct decisions:

1. Publicly review and decide this narrowed design.
2. Separately review the proof/trust and unscored resolver implementation,
   including any necessary public-contract changes.
3. Separately review the concrete source/proof ledgers, rights, bundles, and
   reproduction evidence before admitting a historical canary.
4. Decide whether a broader real macro-judgment case is justified afterward.

Acceptance of the design does not mean those later steps are staffed or passed.
A provenance failure, rights change, or discovered revision quarantines the
candidate or admitted artifact and its dependent result; it does not rewrite
sealed evidence, recast a failed gate as success, or alter the synthetic fixture.

## Unresolved questions

The [review packet](0001-review-packet.md) maps these questions to evidence
entry points, missing preparation material, and scoped review records.

- Which independent reviewers will cover macro interpretation, provenance/time,
  rights, and the implementation's security boundary?
- Which archive authority and exact payload-binding method meet the required
  assurance, and can a fresh reviewer obtain the same verification material?
- Can both source payloads and their proof material be bundled, or is a lawful,
  reproducible local-acquisition/derivative route needed?
- What reviewed experimental report and proof representation support this
  unscored canary without violating current schemas or time semantics?
- Can the two exact versions be authenticated for the declared gates? If not,
  the proposed historical canary remains unadmitted.

## Decision record

Pending. This scope revision replaces the wider scored banking-stress design
within the same Draft RFC. It does not accept the RFC, start its comment clock,
implement the resolver, admit historical evidence, or certify a 2023 forecast.
