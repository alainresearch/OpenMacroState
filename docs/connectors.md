# Connector trust and capture contract

Connectors turn source responses into normalized observation drafts. They do not
decide whether an observation is eligible for a historical cutoff, and they do
not own networking, hashing, or case output. Those controls remain in the core
runtime.

The first three official-source vertical slices are `frbny-sofr`, for the
Federal Reserve Bank of New York's Secured Overnight Financing Rate (SOFR),
`treasury-debt-to-penny`, for total U.S. public debt outstanding, and
`fed-h41-release`, for a dated Federal Reserve Board balance-sheet release. They
are pre-alpha **prospective-capture** connectors, not proof that OpenMacroState
held an old source vintage when its value date occurred.

> **Pre-alpha status:** this command contract is implemented on the current
> development tree but may change before a stable release. Command help in the
> checked-out version is authoritative.

## Trust boundary

Only connectors in the fixed built-in registry are invokable by the pre-alpha
command line. "Built-in" means that the connector code is reviewed and trusted
as part of the OpenMacroState release; it does not mean that Python connector
code is sandboxed or safe to load from an arbitrary package.

The boundary is intentionally narrow:

- a connector declares a fixed identifier, allowed host, source identifiers,
  size limits, and source-license metadata;
- it plans a declarative request but never receives a network client, secret
  store, or output path;
- the core validates the plan, retrieves or replays the exact bytes, records
  limited response metadata, and calculates SHA-256;
- the connector normalizes only the immutable artifact returned by the core;
  and
- the case runtime, not the connector, applies cutoff and evidence-closure
  rules.

Third-party connector templates under `contrib/templates/` are not dynamically
loaded. A proposed connector must first pass source, license, security,
determinism, and time-semantics review before it can join the trusted registry.
This pre-alpha is not a malicious-plugin sandbox.

## Discovering connectors

Built-in connectors can be discovered without touching the network or writing
files:

```bash
oms connector list
```

For deterministic structured output:

```bash
oms connector list --json
```

The command reports each review-trusted connector's ID, version, source name,
allowed hosts, capture modes, redistribution status, and source-policy link. It
also repeats the boundary that review trust is not a third-party sandbox. The
current list contains `fed-h41-release`, `frbny-sofr`, and
`treasury-debt-to-penny`.

## Recorded and online modes

Network access is never an implicit fallback. The capture command requires
exactly one of two mutually exclusive modes:

- `--recording PATH` replays a recorded response offline after checking the
  declared request, byte length, SHA-256, and body path;
- `--online` makes an explicit HTTPS request through the core-owned transport.

If neither flag is present, or both are present, capture fails closed. Online
capture does not accept a user-supplied URL. Each built-in constructs its own
bounded official endpoint from validated start and end dates. SOFR permits only
`markets.newyorkfed.org`; Debt to the Penny permits only
`api.fiscaldata.treasury.gov`; H.4.1 permits only `www.federalreserve.gov`.

A recording manifest can truthfully report what its recorder claims, but its
`retrieved_at` value is self-asserted metadata. Byte length and SHA-256 prove
that the replayed bytes match the manifest; they do not authenticate when those
bytes were captured. Unless a separately reviewed authentication proof binds
the exact bytes to an earlier time, offline replay uses the current core replay
wall-clock as the eligibility and conservative retrieval time. The receipt time
remains available only as an unauthenticated claim and cannot move the cutoff
backward.

The reproducible offline path is:

```bash
mkdir -p build
oms connector capture frbny-sofr \
  --start 2023-03-22 \
  --end 2023-03-22 \
  --recording tests/fixtures/connectors/frbny_sofr/recording.json \
  --output build/frbny-sofr-capture

oms validate build/frbny-sofr-capture
```

The equivalent Treasury offline replay is:

```bash
oms connector capture treasury-debt-to-penny \
  --start 2026-08-05 \
  --end 2026-08-06 \
  --recording tests/fixtures/connectors/treasury_debt_to_penny/recording.json \
  --output build/treasury-debt-to-penny-capture

oms validate build/treasury-debt-to-penny-capture
```

The dated H.4.1 fixture uses equal start and end values because one capture is
one release artifact:

```bash
oms connector capture fed-h41-release \
  --start 2023-03-16 \
  --end 2023-03-16 \
  --recording tests/fixtures/connectors/fed_h41_release/recording.json \
  --output build/fed-h41-release-capture

oms validate build/fed-h41-release-capture
```

An intentional live capture is:

```bash
mkdir -p build
oms connector capture frbny-sofr \
  --start 2026-08-03 \
  --end 2026-08-06 \
  --online \
  --output build/frbny-sofr-live
```

The output is a new capture case containing source and observation records; it
does not invent claims or predictions. Online output records what the core
obtained over the fixed HTTPS route at the live capture time and labels that
fact `source_authentication=core_observed_https`. This is a local core
observation, not a source signature. Offline output uses
`source_authentication=unverified_recording`, records the replay wall-clock for
eligibility, and keeps the manifest's receipt time separately as an
unauthenticated claim. A recording labeled `test_only_excerpt` is suitable for
a parser contract test but must never be presented as the complete official
response. Even a `complete_response` recording carries only a
`recording_completeness_claim`; it neither authenticates its source or capture
time nor escapes source terms and attribution requirements.

Connector capture cases always set `historical_evidence` to `false`. Recorded
captures also set `real_source_data` and `complete_source_response` to `false`;
only a core-observed live HTTPS response may set them to `true`. None of these
fields proves historical availability. That stronger claim requires an
evidence-reviewed case and an accepted authentication path outside this capture
command.


### Offline recording validation

Before using a recorded HTTP response for deterministic replay, you can validate its structural and cryptographic integrity completely offline using the `inspect-recording` command.

This command verifies the JSON schema, ensures the `body_file` path is safe (blocking symlink and directory traversal attacks), and strictly checks that the file's byte length and SHA-256 hash perfectly match the manifest.

**Note:** This command verifies internal consistency and self-reported timestamps. It does *not* establish source authentication or historical eligibility.

***examples***

```bash
oms connector inspect-recording tests/fixtures/connectors/frbny_sofr/recording.json
```

Output:

```text
PASS HTTP recording
recording_kind: test_only_excerpt
  claim: self-reported completeness claim
retrieved_at: 2026-08-09T15:18:38Z
  claim: unauthenticated receipt claim
source authentication: not established
historical eligibility: not established
```

**JSON output:** For programmatic use, append the `--json` flag:

```bash
oms connector inspect-recording tests/fixtures/connectors/frbny_sofr/recording.json --json
```

Output:

```json
{
  "historical_eligibility_established": false, 
  "recording_kind": "test_only_excerpt", 
  "recording_kind_claim": "self-reported completeness claim", 
  "retrieved_at": "2026-08-09T15:18:38Z", 
  "retrieved_at_claim": "unauthenticated receipt claim", 
  "source_authenticated": false, 
  "valid": true}
```
## FRBNY SOFR source

The connector uses the New York Fed's date-bounded Markets API rather than a
moving `latest` endpoint. A representative request is:

```text
https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?startDate=2026-08-03&endDate=2026-08-06
```

The [official Markets API documentation](https://markets.newyorkfed.org/static/docs/markets-api.html)
and the
[SOFR reference-rate documentation](https://www.newyorkfed.org/markets/reference-rates/sofr)
remain the authoritative source. The normalizer expects the source's effective
date, rate, and type. It retains percentiles, transaction volume, revision
indicator, and footnote identifier when they are present, while allowing those
optional statistics or metadata to be absent. Missing identity, date, or
primary-rate fields fail closed.

The normalizer also fails closed on an empty `refRates` array. The official API
can legitimately return an empty array for weekends, dates before SOFR began,
or dates not yet published; this pre-alpha chooses an explicit error instead of
silently emitting an empty successful capture. Accepted value dates begin on
2018-04-02 and must be strictly earlier than the core retrieval calendar date in
`America/New_York`. This is a fail-closed calendar sanity bound, not proof of the
source's exact publication time. Numeric source fields must be JSON numbers,
volume cannot be negative, and published percentiles must be ordered around the
median rate.

SOFR is the broad cost of borrowing cash overnight collateralized by Treasury
securities. That makes this connector one useful dollar-funding state variable;
it does not by itself explain monetary policy, Treasury supply, bank reserves,
dealer balance sheets, or market causality.

## Five time fields

An SOFR row carries an economic date, but that date is not proof of when the row
was public or when OpenMacroState captured it. The connector and core therefore
keep these concepts separate:

| Field | Conservative SOFR treatment |
| --- | --- |
| `observed_at` | Serialized as the canonical date anchor `YYYY-MM-DDT00:00:00Z`. This is not a claim about a midnight instant; extensions preserve the SOFR value date, date-only precision, and `America/New_York` calendar convention. |
| `released_at` | Live mode uses the core-observed fetch completion time as a conservative availability upper bound. Unauthenticated offline replay uses the current replay wall-clock, not the recording's claimed receipt time. |
| `vintage_at` | The same conservative live-capture or replay wall-clock, because the response does not expose a separately verifiable vintage timestamp for each row. |
| `ingested_at` | The current pre-alpha uses the same conservative core-observed live-capture or offline-replay wall-clock; it does not claim a separately measured registration clock. |
| `information_cutoff` | The case boundary against which availability and evidence closure are evaluated. |

For the same reason, an artifact does not receive an invented
`source_published_at`. When the source supplies no exact item-level timestamp,
that field remains unknown rather than being inferred from `effectiveDate`.

Example: retrieving a 2018 SOFR row in 2026 proves that the value was present in
the response retrieved in 2026. Replaying a file whose manifest claims it was
retrieved in 2018 proves only that the current bytes match that manifest. Neither
operation proves that this system possessed those exact bytes, or that the same
row version was public, in 2018. Without an independently authenticated
pre-cutoff artifact, the row cannot be admitted to a 2018 replay.

## Publication and revision rule

The New York Fed says SOFR is normally published on the business day after its
value date, at approximately 8:00 a.m. ET. It may make a same-day revision at
approximately 2:30 p.m. ET when the published rate changes by more than one
basis point. Lagged summary statistics can also differ from the originally
published statistics. See the official
[publication and revision rules](https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates).

These schedule statements are operational guidance, not row-level timestamps.
OpenMacroState therefore follows the more conservative rule:

- do not synthesize 8:00 a.m. as `released_at`;
- do not promote a recording receipt's self-reported time into availability;
- retain the source's revision indicator as metadata, not as a vintage clock;
- never overwrite an earlier capture when later bytes or values differ;
- write changed bytes to a new immutable capture; the current pre-alpha does
  not automatically link separate captures as revisions, so operators must
  preserve that relationship until a reviewed version-link contract exists; and
- admit each version only from the time supported by its own capture or a
  separately reviewed authentication proof.

For a future prospective archive, operators should capture shortly after the
morning publication and again after the revision window. Scheduling is not part
of the current connector; an external scheduler must invoke explicit captures
and preserve failures as failures.

## U.S. Treasury Debt to the Penny source

The `treasury-debt-to-penny` connector uses the official Treasury Fiscal Data
[`Debt to the Penny` dataset](https://fiscaldata.treasury.gov/datasets/debt-to-the-penny/debt-to-the-penny)
endpoint. It never accepts an arbitrary URL. Its one request
fixes the exact `api.fiscaldata.treasury.gov` host, dataset path, URL-encoded
field selection and date filter, ascending sort, JSON format, page number 1,
and page size 367. Start must be on or after 1993-04-01, and a request may span
at most 367 inclusive calendar days.

The connector selects only `record_date`, `tot_pub_debt_out_amt`, and
`src_line_nbr`. This is intentional: older rows can expose component fields as
the string `"null"` or use a documented `$0.00` sentinel. The v0.1 connector
normalizes only total public debt outstanding and does not infer or validate a
component identity where those components are not reliably populated.

Each accepted row becomes one `treasury.debt.total_public_outstanding`
observation in USD. The total must be a positive fixed-two-decimal JSON string.
JSON numbers, zero, `null`, `"null"`, exponent notation, commas, currency
symbols, and other formats fail closed. `src_line_nbr` must be the documented
string `"1"`. Rows must be non-empty, strictly ascending, unique, and inside
the requested range.

Pagination is an integrity check, not a navigation feature. The connector
requires `count == total-count == len(data)`, `total-pages == 1`, null `next`
and `prev` links, and exact page-1/page-size-367 link fragments. It never follows
source-provided links. Unknown row, metadata, or link fields and malformed
metadata types fail closed. These checks prove only that the captured response
is one complete bounded page under the fixed query; they do not authenticate a
past release time.

Treasury's data dictionary and dataset introduction give potentially confusing
descriptions of `record_date`, while the official release calendar provides
estimated schedule times rather than row-level publication evidence. The
connector records this ambiguity and does not synthesize a release timestamp.
Both the requested end date and every returned `record_date` must be strictly
earlier than the core retrieval calendar date in `America/New_York`.
`observed_at` is a canonical UTC date anchor, not a midnight event claim.
`released_at`, `vintage_at`, and the current pre-alpha `ingested_at` use the
conservative core live-capture or replay wall-clock; `source_published_at`
remains unknown. The endpoint exposes no row revision or vintage field.

The checked-in fixture contains real values for 2026-08-05 and 2026-08-06 but
was reserialized for review. It is machine-labeled `test_only_excerpt`, not the
exact original response bytes and not an authenticated historical capture.

The authoritative endpoint contract and open-data policy are in Treasury
Fiscal Data's [API documentation](https://fiscaldata.treasury.gov/api-documentation/).
The project records redistribution and commercial use as allowed for the
Treasury-generated data records captured here. It does not label them CC0 or
Apache-2.0, grant rights in trademarks or third-party material, or imply
Treasury endorsement.

## Federal Reserve H.4.1 dated-release source

The `fed-h41-release` connector constructs one dated Board HTML URL from equal
`--start` and `--end` release dates. Ruleset 3 supports the audited current DOM
era from 2021-08-12 onward. It selects seven Wednesday stock values: total assets,
total liabilities, total capital, securities held outright, primary credit, the
Treasury General Account, and reserve balances. Each remains in the reported
`USD_million` unit.

The parser binds unique exact row labels to exact table prefixes and the
`Wednesday` value column. Each selected table must immediately follow its exact
heading and `Millions of dollars` unit paragraphs inside one plain `div`
parent, and each
value header must resolve to real header cells in the same table. It does not
use the first number, a fixed row number, or HTML table ordinal. Wrong units,
hidden or detached semantic context, duplicate IDs or rows, date mismatch,
future dates, malformed values, and unsupported structure fail closed.

The H.4.1 parser evaluates semantic HTML, including native hidden states and
supported inline hidden markers. It does not fetch stylesheets or claim to
reproduce arbitrary browser CSS selectors and computed visibility.

The release path date and Wednesday observation date are source claims, not
availability timestamps. `released_at`, `vintage_at`, and `ingested_at` use the
core capture or replay wall-clock; `source_published_at` remains unknown. A
dated URL can be corrected later, so every capture remains prospective and
`historical_evidence=false` without independent cutoff-time authentication.

The exact source, parser, time, exclusion, fixture, and rights decisions are in
the [H.4.1 source contract](fed-h41-source-contract.md). The connector does not
fall back to DDP, current XML, PDF, FRED, or a mirror.

The three Table 5 totals also carry provisional namespaced accounting metadata.
The fixed experimental
[`fed-h41-balance-sheet-v1` audit](accounting-audit.md) checks
`assets = liabilities + capital` only when source, artifact, unit, and
observation time match, with an exact 1 `USD_million` tolerance for source
rounding. This audit is not a stable public schema or a general state graph.

## Source and license requirements

FRBNY reference-rate content is subject to the New York Fed
[Terms of Use](https://www.newyorkfed.org/privacy/termsofuse.html), including
source attribution, modification labeling, distribution conditions, and the
specific reference-rate notice and non-endorsement language. It is not relicensed
under Apache-2.0 merely because connector code is Apache-2.0.

Treasury Debt to the Penny captures use the source decision documented above
and in the [data-license policy](data-licensing.md). Generated bundles retain
the source, terms URL, review date, and non-endorsement boundary next to the
data and normalized observations.

Federal Reserve Board H.4.1 captures use the page-level public-domain decision
documented in the [H.4.1 source contract](fed-h41-source-contract.md). It covers
only the audited Board-authored table and text content, excludes seals, logos,
trademarks, and third-party material, retains Board attribution, and does not
imply endorsement.

Do not replace this direct official source with FRED or ALFRED. Their useful
vintage interface does not override their current terms or third-party rights;
OpenMacroState's recorded, hashed, software-driven workflow is incompatible with
the current permissions. See the [data-license policy](data-licensing.md).

## Connector review checklist

A connector contribution must demonstrate:

- a canonical official source and exact allowed hosts;
- bounded requests, byte limits, no implicit credentials, and fail-closed
  parsing;
- deterministic normalization from frozen bytes;
- explicit observation, release, vintage, and ingestion semantics;
- revision, missing-data, timezone, and calendar behavior;
- offline fixtures that state whether they are complete, excerpts, or
  synthetic;
- source-specific license metadata and required notices; and
- tests proving that later retrieval cannot masquerade as earlier capture.

Connector review establishes a reproducible acquisition contract. It does not
certify a causal interpretation or make source data investment advice.
