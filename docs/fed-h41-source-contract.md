# Federal Reserve H.4.1 dated-release source contract

Status: implemented by connector ruleset `fed-h41-release-normalization/1`.

This contract defines what the first H.4.1 connector may retrieve, what it may
normalize, and—most importantly—what it may not claim about historical
availability.

## Canonical source

The connector accepts one release date and constructs exactly one URL:

```text
https://www.federalreserve.gov/releases/h41/YYYYMMDD/h41.htm
```

It permits only HTTPS on `www.federalreserve.gov`, uses no query, fragment,
credentials, redirect, secret, mirror, or fallback, and accepts at most 2 MiB of
`text/html`. `--start` and `--end` must be the same date. Ruleset 1 supports
releases on or after 2021-08-12, the first audited archive date using the current
`t#r#c#` cell-ID structure. An earlier layout needs a separate parser ruleset.

The [official H.4.1 archive](https://www.federalreserve.gov/releases/h41/default.htm)
is the source index. The
[H.4.1 about page](https://www.federalreserve.gov/releases/h41/about.htm)
describes the release as generally published on Thursday around 4:30 p.m.
Eastern Time. That schedule is not an item-level publication timestamp and is
never copied into `released_at`.

## Selected observations

Ruleset 1 reads five reported Wednesday stock values. It locates rows by a table
prefix and unique exact label, then requires the value cell to be bound to the
table's `Wednesday` header. Row numbers are deliberately not fixed because the
Board can add or remove lines.

| Series | Source table and row | Value column | Unit |
| --- | --- | --- | --- |
| `fed.h41.total_assets` | Table 5, `Total assets` | Wednesday | `USD_million` |
| `fed.h41.securities_held_outright` | Table 1, `Securities held outright` | Wednesday | `USD_million` |
| `fed.h41.primary_credit` | Table 1, `Primary credit` | Wednesday | `USD_million` |
| `fed.h41.treasury_general_account` | Table 1 continued, `U.S. Treasury, General Account` | Wednesday | `USD_million` |
| `fed.h41.reserve_balances` | Table 1 continued, `Reserve balances with Federal Reserve Banks` | Wednesday | `USD_million` |

The unit immediately preceding each selected table must be exactly `Millions of
dollars`. Values must be non-negative ASCII integers with valid source grouping;
the normalizer removes commas but does not rescale the number. The four selected
components may not exceed total assets. It does not require components to sum
exactly: the release itself warns that components may differ from totals because
of rounding, and the selected lines are not an exhaustive accounting identity.

The parser fails closed on a missing or duplicate release statement, path/body
date mismatch, future release date, inconsistent Wednesday headers, wrong unit,
duplicate or missing cell/row, near-match label, wrong value column, invalid
number, unsupported DOM, or malformed UTF-8. A cover-note table or changed row
number cannot redirect the parser because it never uses table ordinal or a fixed
row position.

## Time and historical-version boundary

H.4.1 exposes several dates that must not be collapsed:

- the path and page identify a release date;
- the selected column identifies the Wednesday observation date; and
- the core records when it actually obtained or replayed the exact bytes.

`observed_at` is the Wednesday date serialized as a canonical UTC date anchor;
it is not a claim that the balance existed at a midnight instant.
`released_at`, `vintage_at`, and the current pre-alpha `ingested_at` all use the
core live-capture or replay wall-clock. The page's date, the general 4:30 p.m.
schedule, `Last-Modified`, and a recording's self-reported receipt time are kept
separate and cannot move eligibility backward.

Every connector capture therefore has:

- `source_published_at: null`;
- `historical_evidence: false`;
- `historical_version_authenticated: false`; and
- `point_in_time_scope: known_at_retrieval_not_at_value_date`.

A dated official URL is not proof that today's bytes are the same bytes that
were available on the page date. The Board has announced delayed releases and
corrections, and dated pages can be updated later. A real historical replay must
bind the exact bytes to the old cutoff with independent evidence, such as a
contemporaneous trusted archive or authenticated digest. This connector does not
manufacture that proof.

The current Data Download Program and current XML package are excluded because
they do not provide a dated artifact version. The Board's
[Data Download help](https://www.federalreserve.gov/datadownload/help/)
states that pre-revision or real-time data are not available. PDF is also
excluded from ruleset 1; there is no silent format or source fallback.

## Rights and fixture decision

The reviewed source decision uses:

- `license_id: Federal-Reserve-Board-Public-Domain-Website-Information`;
- [Board website disclaimer](https://www.federalreserve.gov/disclaimer.htm);
- artifact-level `redistribution: restricted`;
- `commercial_use: allowed`; and
- attribution to the Board of Governors of the Federal Reserve System.

The disclaimer states that, unless otherwise indicated, information on the
Board website is public domain and may be copied and distributed when the Board
is cited. The decision here is narrower than the whole website: it applies only
to the audited Board-authored H.4.1 table and text excerpt. A complete live HTML
response may also contain site chrome, infrastructure scripts, external icons,
Federal Reserve seals, logos, trademarks, or third-party material, so the raw
artifact is conservatively marked `restricted`. The source material is not
relabeled CC0 or Apache-2.0, and neither capture nor transformation may imply
Board endorsement.

The checked-in March 16, 2023 fixture contains five real reported values in a
small derived HTML document. Its recording is labeled `test_only_excerpt`; it is
not complete response bytes or an authenticated 2023 vintage. Its adjacent
`NOTICE.md` is part of the fixture's rights and provenance boundary.
