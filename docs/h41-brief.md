# H.4.1 briefs

Use an H.4.1 brief to inspect seven Federal Reserve balance-sheet values, compare
two saved captures, and take the numbers into a spreadsheet or research note.
The HTML page, CSV, and Markdown retain the source and capture context needed
to check the result later. No AI service is involved.

This command is in the repository's development version, after `v0.1.0a6`.
Follow the [source-install quickstart](quickstart.md#install-the-repository-version).
The JSON report is an experimental sidecar, separate from `schemas/v1`.

## First brief from the included recording

From the repository checkout, run:

```bash
mkdir -p build
oms connector capture fed-h41-release \
  --start 2023-03-16 --end 2023-03-16 \
  --recording tests/fixtures/connectors/fed_h41_release/recording.json \
  --output build/h41-capture \
  --brief-output build/h41-brief
```

Open `build/h41-brief/index.html`. The recording is a `test_only_excerpt`,
containing seven reported values in a derived HTML document. It exercises the
parser and report; it is not a complete official response or authenticated
2023 vintage. Its [fixture notice](../tests/fixtures/connectors/fed_h41_release/NOTICE.md)
explains its origin and rights.

The capture directory and brief directory are separate. To make another brief
from the preserved capture, without acquiring anything:

```bash
oms brief h41 build/h41-capture --output build/h41-brief-copy
```

For the offline two-capture example, follow the
[comparison walkthrough](quickstart.md#try-a-comparison-offline). For a dated
page retrieved from the Board today, follow
[explicit online capture](quickstart.md#explicit-online-capture). The latter
records today's retrieval rather than claiming a 2023 capture.

## Inputs and outputs

The command accepts a case produced by the `fed-h41-release` connector. It must
contain one observation period and exactly seven accepted observations, all in
`USD_million`:

| Series | Source stock |
| --- | --- |
| `fed.h41.total_assets` | Total assets |
| `fed.h41.total_liabilities` | Total liabilities |
| `fed.h41.total_capital` | Total capital |
| `fed.h41.securities_held_outright` | Securities held outright |
| `fed.h41.primary_credit` | Primary credit |
| `fed.h41.treasury_general_account` | Treasury General Account |
| `fed.h41.reserve_balances` | Reserve balances |

The new output directory contains:

| File | Purpose |
| --- | --- |
| `index.html` | A local page with values, comparison when supplied, table copying, export links, and source/audit details |
| `observations.csv` | Exact values in the reported unit, with previous values and deltas when supplied |
| `brief.md` | A readable summary for a research note, carrying the capture and comparison context |
| `brief.json` | The experimental structured report, including rows, capture identities, comparison kind, and audit details |

Amounts and deltas in the JSON report are exact integer strings. No rescaling to
billions or rounding to a display precision is needed to reproduce a delta.
The page's copy action provides tab-separated text for a spreadsheet; if browser
clipboard access is unavailable, use the selectable fallback text or CSV.

The output path must not already exist, its parent must exist, and it must be
outside both input capture directories. The command does not overwrite files
and has no `--force` option. It only reads input captures and writes the new
brief directory. Existing captured bundles remain usable for later inspection.

## Comparison rules

The saved case supplied immediately after `h41` is the current capture.
`--previous` adds an earlier capture:

```text
oms brief h41 CURRENT_CASE --previous PREVIOUS_CASE --output NEW_BRIEF_DIRECTORY
```

Replace these placeholders with your saved paths. The previous observation date
must be no later than the current observation date. When both observation dates
are the same, the previous ingestion time must also be no later than the current
ingestion time. Across different observation periods, you can capture the newer
release first and retrieve the older release afterward; both retain their actual
capture times. Each input must pass the checks independently. Every delta is
`current_value - previous_value`; a missing value is never treated as zero.

| `comparison.kind` | What the brief can say |
| --- | --- |
| `single_capture` | Seven values are shown, with no previous values or claimed movement |
| `new_period` | The observation dates differ; the brief gives the actual interval and changes between the selected periods |
| `same_period_values_changed` | The observation date is the same and one or more selected values differ between these captures |
| `same_period_artifact_changed` | The observation date and selected values match, but the preserved source bytes differ |
| `identical` | The preserved source bytes and selected values match; capture metadata may still differ |

Only an interval of exactly seven days is a seven-day comparison. A larger gap
must not be called a weekly movement or have missing weeks filled in. Same-period
differences describe the two captures; they do not certify an official revision,
a publication time, or the cause of a change. Changes outside the seven selected
values can alter an artifact hash without changing the displayed values.

A comparison of two dated release pages fetched today is useful for comparing
what those pages currently report. It does not establish which versions were
available at their original release dates. Each capture retains its own source
URL, byte hash, authentication status, clocks, and audit identity.

## Checks and failed reports

For each input, the brief requires a valid H.4.1 capture with exactly the seven
accepted observations and no quarantined observations. It replays the preserved
artifact through the connector and requires the regenerated observations to
match the stored ones. The fixed
[accounting audit](accounting-audit.md) checks
`assets = liabilities + capital` within 1 `USD_million` of reported rounding.

Invalid evidence, including a wrong source, missing or extra observation, mixed
period, tampered artifact, or failed replay, is rejected before a brief is
written. An invalid previous capture is rejected as well; it does not become
an empty baseline or a zero-change result.

Valid, exactly replayed inputs can still fail a numerical accounting check.
In that case the command writes a diagnostic brief marked **FAIL**, including
the failed checks, and exits with status `2`. Inspect the reported reasons;
the presence of export files does not mean the accounting check passed.

The audit establishes consistency of this local evidence and calculation. It
does not independently authenticate the source or a historical version.
`historical_evidence` and historical-version authentication remain false.
The current capture/replay time stays separate from the Wednesday observation
date. See the [H.4.1 source contract](fed-h41-source-contract.md) and
[research contract](research-contract.md) for the detailed time rules.

The brief includes the reported stocks and arithmetic differences. It does not
infer money flows, borrower counts, solvency, economic causes, or forecast
performance. Source attribution and redistribution terms remain attached to the
material; report generation does not expand source rights.

## Troubleshooting

| Symptom | Next step |
| --- | --- |
| `brief` is not recognized | Install the current repository checkout with `python -m pip install .`; the `v0.1.0a6` release predates this command |
| Output exists or its parent is missing | Create the parent directory, then choose a new brief path |
| A capture fails validation or replay | Inspect the capture error and original files; acquire/replay a fresh valid bundle rather than editing sealed observations |
| The previous capture is later than the current one | Check the observation dates; for the same observation date, also check that previous ingestion is no later than current ingestion |
| The page cannot copy to the clipboard | Use the selectable table text or download `observations.csv` |

Keep the original captures alongside the exports if you need a later offline
reproduction. The experimental `brief.json` format may change before a stable
release; the preserved capture remains the evidence record.
