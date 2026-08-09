# RFC 0001: Evidence-reviewed 2023 US banking-stress replay

- Status: Draft
- Authors: OpenMacroState contributors
- Shepherd: Unassigned
- Created: 2026-08-10
- Discussion: [GitHub Issue #11](https://github.com/alainresearch/OpenMacroState/issues/11)
- Supersedes:
- Superseded by:

## Summary

Build the first real OpenMacroState historical replay around a narrow question
that can be scored from fixed, dated Federal Reserve releases:

> At 2023-03-10 23:59:59 in New York, using only official information that was
> public by then, what probability should a researcher assign to Wednesday
> primary-credit loans outstanding in the next H.4.1 release reaching at least
> ten times its fixed baseline?

The research cutoff is `2023-03-11T04:59:59Z`. The baseline is the Primary
credit row, Wednesday column, in the 2023-03-09 H.4.1 release: USD 4,581 million.
The binary threshold is USD 45,810 million. It is predeclared in this replay
contract before reveal bytes are admitted, but the target was designed in 2026
with knowledge of 2023 history. The outcome comes from the same row and column
in the 2023-03-16 H.4.1 release.

This RFC specifies the question, evidence inventory, competing mechanisms,
prediction rules, reveal boundary, and release gates. It does **not** yet admit
the late-downloaded official files as authenticated historical evidence. The
executable case may graduate only after a reviewed proof path binds each exact
research artifact to pre-cutoff public availability.

## Problem and users

The repository's `2023-banks` example is deliberately synthetic. It proves that
the software can quarantine future observations and keep outcomes separate, but
it cannot demonstrate that a real macro judgment can be reconstructed without
hindsight.

A useful first historical case must expose three common errors:

- disguising a retrospectively designed target as a contemporaneous forecast;
- replacing original releases with current or revised data; and
- treating a file downloaded today as proof that the same bytes were public at
  the historical cutoff.

The proposed target begins after Silicon Valley Bank had already been closed.
It asks whether stress would become large enough to appear in a system-level
Federal Reserve liquidity measure. This is useful to macro researchers,
provenance reviewers, model authors, and maintainers because it has a fixed
information boundary, a fixed numerical threshold, and a dated official reveal.

## Research-integrity effects

### Information and accounting boundary

- Research cutoff: `2023-03-11T04:59:59Z`, equal to 2023-03-10 23:59:59 EST.
- Unit: USD millions, exactly as reported in H.4.1.
- Baseline cell: H.4.1 dated 2023-03-09, Table 1, Primary credit,
  Wednesday 2023-03-08.
- Outcome cell: H.4.1 dated 2023-03-16, Table 1, Primary credit,
  Wednesday 2023-03-15.
- Binary event: outcome cell greater than or equal to ten times the baseline.
- Weekly averages, current-series downloads, later revisions, and differently
  named Federal Reserve facilities cannot substitute for either cell.

The target cell is a Wednesday stock of primary-credit loans outstanding. It is
not a lending flow, a count of borrowing banks, or a measure of every emergency
liquidity channel. A large increase does not establish that stress was evenly
distributed across banks, that every borrower was insolvent, or that one
proposed mechanism caused the change.

### Historical status

The proposed case begins with:

```yaml
historical_evidence: false
target_availability_mode: retrospective_authenticated
model_evaluation_status: retrospective_contaminated_model
target_design_status: retrospective_target_design
```

The target mode describes the assurance the finished case must eventually
provide, not an assurance the current runtime already provides. A present-day
SHA-256 digest proves only that bytes have not changed since the present
capture. It does not prove those bytes existed or were public in March 2023.

All three targets were designed after their historical outcomes occurred. They
are predeclared only relative to this case's future reveal step, not relative to
March 2023. Because present-day general-purpose models can already know those
outcomes, their probabilities in this replay are demonstrations of the research
protocol, not out-of-sample forecasting performance. Genuine predictive
evaluation requires a probability frozen before the cutoff, a model and training
corpus frozen before the cutoff, or an independently frozen deterministic
prediction rule.

### Evidence selection

An item may enter the research bundle only if it was selected under a rule that
could have been applied before the outcome:

1. it is an official regulator, central-bank, or fixed SEC filing source;
2. it was public by the cutoff under a reviewed availability rationale;
3. its exact version and relevant table, filing component, or order are fixed;
4. it bears directly on funding, duration exposure, deposit behavior, industry
   resilience, or the known closure; and
5. it is not selected merely because the institution later failed.

For that reason, a Signature Bank 10-K is excluded from the first research
bundle. Selecting it only because Signature failed after the cutoff would add
post-outcome entity-selection bias.

## Detailed design

### Predictions

The primary and two auxiliary predictions are separate. Each records its own
probability, Brier score, and binary log loss; no post-hoc composite score is
permitted.

```yaml
case_id: 2023-us-bank-stress-official-v1
information_cutoff: 2023-03-11T04:59:59Z
cutoff_timezone: America/New_York

primary_prediction:
  id: primary_credit_10x
  baseline_usd_millions: 4581
  threshold_usd_millions: 45810
  resolved_by: h41_2023_03_16_primary_credit_wednesday
  rule: value >= 45810

secondary_predictions:
  - id: additional_idi_closure_7d
    deadline_exclusive: 2023-03-18T04:00:00Z
  - id: new_broad_fed_facility_7d
    deadline_exclusive: 2023-03-18T04:00:00Z

reveal_not_before: 2023-03-18T04:00:00Z
scores:
  - brier
  - binary_log_loss
aggregation: none
```

The auxiliary window is the half-open interval after the cutoff and before
2023-03-18 00:00:00 EDT. It represents seven New York calendar days, not 168
elapsed UTC hours: the 2023-03-12 daylight-saving transition makes it 167 hours.
The reveal gate opens at the exclusive endpoint, so no event instant is
simultaneously eligible as both hidden outcome and revealed evidence.

`additional_idi_closure_7d` resolves true when, within that interval, a US state
or federal banking authority formally closes at least one FDIC-insured
depository institution other than SVB. A voluntary liquidation does not count,
and creation of a bridge bank does not count as a second closure.

`new_broad_fed_facility_7d` resolves true when the Federal Reserve formally
announces, in the same half-open window, a previously nonexistent lending or liquidity
program offered to a class of depository institutions rather than one named
institution. A change to existing discount-window terms alone does not count.

### Research source ledger

The research archive and its hash tree are physically independent from the
reveal archive. Exact artifact digests, extraction locators, licensing decisions,
and historical-availability proofs belong in the source ledger created during
implementation.

| Source fixed before cutoff | Intended use | Version and availability risk |
| --- | --- | --- |
| [Federal Reserve 2023-02-01 FOMC statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20230201a.htm) and [implementation note](https://www.federalreserve.gov/newsevents/pressreleases/monetary20230201a1.htm) | Policy-rate and primary-credit-rate setting | Current web bytes require a historical proof or dated official archive rationale. |
| [SVB Financial 2022 10-K index](https://www.sec.gov/Archives/edgar/data/719739/000071973923000021/0000719739-23-000021-index.htm) and [filing](https://www.sec.gov/Archives/edgar/data/719739/000071973923000021/sivb-20221231.htm) | Deposits, AFS/HTM values, rate risk, and funding disclosures | Fix accession `0000719739-23-000021`, component paths, acceptance metadata, and exact bytes. Treat issuer statements as reported evidence. |
| [FDIC Q4 2022 release](https://www.fdic.gov/news/press-releases/2023/pr23013.html) and [chairman's statement](https://www.fdic.gov/news/speeches/2023/spfeb2823.html) | Industry unrealized losses, deposit decline, capital, liquidity, and competing evidence of resilience | Preserve the 2023-02-28 vintage; later Call Report revisions cannot replace it. |
| [Silvergate 2023-03-08 8-K index](https://www.sec.gov/Archives/edgar/data/1312109/0001312109-23-000058-index.html) and [company exhibit](https://www.sec.gov/Archives/edgar/data/1312109/000131210923000058/ex991sipressrelease3x8x23.htm) | A known voluntary liquidation before cutoff | Fix accession `0001312109-23-000058`; do not classify voluntary liquidation as a regulatory closure. |
| [SVB 2023-03-08 8-K](https://www.sec.gov/Archives/edgar/data/719739/000119312523064680/d430920d8k.htm) and [investor letter](https://www.sec.gov/Archives/edgar/data/719739/000119312523064680/d430920dex993.htm) | Securities sale, loss, planned financing, and deposit trajectory | Fix accession `0001193125-23-064680`; issuer assertions remain reported evidence. |
| [Federal Reserve H.4.1 dated 2023-03-09](https://www.federalreserve.gov/releases/h41/20230309/h41.pdf) and [release directory](https://www.federalreserve.gov/releases/h41/20230309/) | Fixed primary-credit baseline | Bind the dated PDF, table, row, Wednesday column, and USD-millions unit. |
| [Federal Reserve H.8 dated 2023-03-10](https://www.federalreserve.gov/releases/h8/20230310/h8.pdf) | Latest available aggregate commercial-bank balance-sheet context | Use only that vintage and only observations available within it; do not substitute a current series. |
| [California DFPI signed SVB order](https://dfpi.ca.gov/wp-content/uploads/sites/337/2023/03/DFPI-Orders-Silicon-Valley-Bank-03102023.pdf) and [official action page](https://dfpi.ca.gov/enforcement_action/silicon-valley-bank/) | Establish the known closure and regulator's stated grounds before cutoff | California material is not covered by the federal-government-work rule; use `fetch_only` or `reference_only` until rights and historical availability are reviewed. |

Date-only sources are conservatively mapped to the end of the source's local
calendar day. EDGAR acceptance time is not silently promoted to a guaranteed
public-availability instant. Fixed accession numbers and dated URLs reduce
ambiguity but do not replace a reviewed proof for the exact bytes.

### Reveal source ledger

The reveal bundle has its own directory, license record, checksum manifest, and
`not_before` gate. No reveal file, summary, result field, URL, content digest, or
outcome value may appear in the research archive. A reveal file downloaded after
its claimed resolution time also needs a reviewed proof binding the exact
version to public availability no later than evaluation; a dated URL alone is
not sufficient.

| Reveal source | Resolution use |
| --- | --- |
| [Joint Federal Reserve release dated 2023-03-12](https://www.federalreserve.gov/newsevents/pressreleases/monetary20230312b.htm) | Depositor-protection and systemic-risk actions; context only unless tied to an auxiliary rule. |
| [Federal Reserve BTFP announcement dated 2023-03-12](https://www.federalreserve.gov/newsevents/pressreleases/monetary20230312a.htm) | Resolve the new-broad-facility auxiliary event. |
| [New York DFS Signature action](https://www.dfs.ny.gov/reports_and_publications/press_releases/pr20230312) and [FDIC bridge-bank release](https://www.fdic.gov/news/press-releases/2023/pr23018.html) | Resolve the additional-closure auxiliary event without double counting the bridge bank. |
| [Federal Reserve H.4.1 dated 2023-03-16](https://www.federalreserve.gov/releases/h41/20230316/h41.pdf) and [release directory](https://www.federalreserve.gov/releases/h41/20230316/) | Resolve the primary event from the predeclared row, column, and unit. |

Later Federal Reserve, FDIC, or state post-mortems may be analyzed only after
scoring. They cannot enter the research snapshot or determine the primary event.

### Competing mechanisms

The claim ledger must preserve at least these alternatives without voting them
into a single story:

1. **Institution-specific concentration and governance.** SVB's depositor base,
   asset structure, and decisions produce a large local failure but limited
   aggregate primary-credit loans outstanding.
2. **Common duration risk plus uninsured-deposit runs.** Shared unrealized losses
   and runnable funding produce a system-level liquidity response, additional
   closures, or a broad facility.
3. **Credit-loss deterioration.** Asset-credit impairment, rather than liquidity
   and valuation pressure, drives the event. Pre-cutoff industry asset-quality
   evidence must be retained as a genuine competing observation.
4. **Monetary tightening and liability repricing.** Higher rates affect both
   securities valuations and deposit funding costs.
5. **Information contagion and common-client channels.** Closely timed failures
   coordinate depositor behavior beyond institutions with identical books.
6. **Policy containment and collateral transformation.** Stress can be severe
   while liquidity tools prevent a larger number of closures.
7. **Idiosyncratic failure within a resilient system.** Aggregate capital and
   liquidity evidence supports a limited-spillover interpretation.

The official aggregates do not identify each mechanism's causal share. The
case must not publish percentage causal decompositions that the design cannot
support.

## Compatibility and migration

The first merge of this RFC is documentation only. It does not change schemas,
the synthetic fixture, or runtime acceptance rules.

Implementation should add a new case and reveal pair rather than mutate
`cases/2023-banks`. If a real historical-availability verifier requires public
schema or proof changes, that change must be separately reviewed and versioned.
The case must fail closed under the existing runtime until the proof contract is
implemented; maintainers must not add a case-specific boolean bypass.

## Security, privacy, and licensing

- Apache-2.0 covers repository-authored code and prose, not the source files.
- Federal Reserve material is reviewed item by item under the Board's
  [disclaimer](https://www.federalreserve.gov/disclaimer.htm); each use credits
  the Board as source, and third-party images, logos, and trademarks are excluded.
- SEC accession metadata and issuer filings retain source attribution. Company
  exhibits are company-reported material, not statements by the SEC and not US
  government works merely because EDGAR hosts them. Each issuer-authored item
  receives its own `bundled`, `fetch_only`, `reference_only`, or `blocked`
  decision; it defaults to `fetch_only` or `reference_only` until rights review.
- FDIC items receive separate source and redistribution decisions under the
  [FDIC website policies](https://www.fdic.gov/about/website-policies).
- California DFPI and New York DFS material is not automatically a US federal
  government work. It remains `fetch_only` or `reference_only` until reviewed.
- No FRED or ALFRED material is used.
- The bundle excludes personal data, depositor identities, unnecessary images,
  logos, and unrelated filing attachments.

## Alternatives

### Predict whether SVB would fail

Rejected for the first case. By a clean end-of-day March 10 cutoff, SVB had
already been closed. Moving the cutoff earlier would make the exact public
information boundary harder to authenticate and would encourage post-hoc target
selection.

### Predict whether a broad policy backstop would be announced

Retained as an auxiliary outcome, not the primary outcome. The definition of a
"backstop" is more contestable than a fixed H.4.1 cell.

### Use a current time series or FRED/ALFRED vintage

Rejected. A current series can incorporate revisions, and current FRED/ALFRED
terms conflict with this project's software-driven archival workflow.

### Ship the present-day downloads as a historical case immediately

Rejected. Source authority and a dated URL do not authenticate the historical
availability of today's exact bytes.

## Drawbacks and risks

- Historical availability may remain unverified for some otherwise authoritative
  files, delaying an executable case.
- The 10x threshold is intentionally coarse and measures only one aggregate
  liquidity response.
- A threshold chosen after knowing 2023 history can still exhibit target-design
  hindsight. The RFC freezes it now and reports that limitation; it cannot turn
  the exercise into a contemporaneous forecast.
- Official sources can be revised, moved, or silently updated.
- Aggregate data cannot distinguish solvency, liquidity, institution mix, or
  causal contribution without additional assumptions.

## Test and evaluation plan

The implementation cannot graduate until all of the following pass:

1. A source reviewer and a separate macro reviewer approve every locator,
   extraction, unit, timestamp rationale, and redistribution decision.
2. Every accepted research artifact has an exact digest and an approved
   pre-cutoff availability proof bound to source identity and version. Every
   reveal artifact has the equivalent proof for public availability no later
   than its declared resolution or evaluation time.
3. The research manifest is frozen before a separate role builds the reveal
   manifest.
4. A clean-environment replay reproduces the same eligible observation and claim
   roots without network access.
5. Automated leakage scanning confirms that the research archive contains no
   reveal path, URL, digest, outcome value, post-cutoff report, or derived result.
6. Replacing the original FDIC Q4 vintage with a later revision fails.
7. Replacing the H.4.1 Wednesday cell with the weekly-average cell fails.
8. Moving a date-only source to the beginning rather than the end of its local
   day fails.
9. Changing a source digest, accession component, table locator, unit, cutoff,
   threshold, prediction probability, or scoring rule changes the snapshot root
   or fails validation.
10. Evaluation before `reveal_not_before` fails without reading or hashing reveal
    plaintext; evaluation exactly at the exclusive event-window endpoint may
    open only a reveal bundle whose versions pass their own availability proofs.

## Adoption and rollback

Adoption has three stages:

1. open this Draft RFC for public evidence and macro review, assign a shepherd,
   and complete the minimum 14-day comment period before any decision or merge;
2. implement the source ledger and historical-proof verifier behind a separate
   pull request only after the RFC decision, while keeping
   `historical_evidence: false`; and
3. add the case/reveal pair only after all release gates pass.

At any stage, a rights change, provenance failure, or newly discovered revision
can demote an artifact to `fetch_only` or `reference_only`, quarantine it, and
return the case to Draft without altering the synthetic fixture.

## Unresolved questions

- Which proof authorities and proof formats are sufficient for dated Fed PDFs,
  EDGAR components, and state-regulator documents?
- Should the first real verifier be source-specific or expose a general public
  archive/timestamp protocol?
- Can the original 2023-02-28 FDIC Q4 package be redistributed, or should the
  bundle contain only a locator, digest, and extraction recipe?
- Who will serve as shepherd, macro reviewer, provenance reviewer, and license
  reviewer without combining incompatible approval roles?
- Should the two auxiliary predictions ship in v1 or remain a scored extension?
- What deterministic baseline probability, declared before this replay's reveal
  step but not represented as a March 2023 forecast, should accompany the
  retrospective model demonstration?

## Decision record

Pending public review. Acceptance of this RFC will approve the case design, not
assert that the source files have passed historical-availability authentication
or that any retrospective model score is out of sample.
