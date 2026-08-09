# Contributing to OpenMacroState

Thank you for helping build a public memory for macro research. Contributions are
welcome from economists, market practitioners, students, journalists, software
engineers, data stewards, technical writers, and reproducibility reviewers.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you
also agree to the public governance and review process in [GOVERNANCE.md](GOVERNANCE.md).

## Choose a contribution lane

### Data connectors

Add or repair acquisition, release-time, normalization, and provenance logic for
a source. A connector contribution normally includes:

- a public source and stable source identifier;
- observation and release-time semantics;
- units, frequency, seasonal-adjustment, and revision behavior;
- error handling that fails closed rather than silently substituting data;
- deterministic fixtures and tests; and
- a completed license and redistribution assessment.

Read the [connector trust and capture contract](docs/connectors.md) before
starting. The pre-alpha command line invokes only review-trusted connectors in a
fixed built-in registry; it does not sandbox or dynamically load arbitrary
third-party Python. Tests should use recorded, verified responses or clearly
labeled synthetic/excerpt fixtures. Live access must remain an explicit user
choice and must never be a fallback when a recording is absent. A recording's
hash verifies its bytes, not its self-reported capture time; without an
authenticated proof, offline replay must use the current core replay time for
eligibility. A recording is also not source authentication: only the fixed
core-owned live HTTPS path is labeled `core_observed_https`, and that label is
not a cryptographic source signature.

### Historical replay cases

Propose or implement a bounded historical question. A case should declare its
knowledge cutoff, allowed evidence, target claims, competing explanations,
evaluation horizon, and expected outputs. Later information belongs in a
physically separate reveal bundle with its own artifacts, checksums, and license
record, never in the frozen research bundle. `openmacrostate validate` must work
without locating or reading that reveal.

### Mechanisms and model adapters

Document balance sheets, accounting identities, transmission paths, or adapters
to external models. State units, institutional boundaries, calibration choices,
valid regimes, and known failure conditions. Major additions should begin with a
design Discussion or RFC before implementation.

### Documentation and examples

Improve explanations, tutorials, API references, diagrams, translations,
accessibility, and runnable examples. Documentation fixes may be submitted
directly. A translated page should link to its canonical source and identify the
source revision it follows.

### Review and community work

Valuable non-code contributions include reproducing bugs, validating source
licenses, checking timestamps, reviewing an economic mechanism, answering a
Discussion, triaging an Issue, and testing setup instructions on a clean machine.

## Where to start

- Use GitHub Discussions for questions, exploratory proposals, and requests for
  design guidance.
- Use GitHub Issues for reproducible defects and accepted, bounded work.
- Look for `good first issue`, `help wanted`, an effort label, and a skill label.
- Comment before claiming an Issue. A maintainer will confirm scope and expected
  review support.

Small corrections can go straight to a pull request. Before spending significant
time on a new schema, core feature, large connector, or replay case, open a
Discussion or Issue and wait for scope agreement.

## Development setup

Use a supported Python version in an isolated environment:

```bash
git clone https://github.com/alainresearch/openmacrostate.git
cd openmacrostate
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Run the complete test suite:

```bash
pytest
```

Run the public offline demonstration:

```bash
openmacrostate demo cases/2023-banks --reveal reveals/2023-banks --evaluation-at 2023-03-13T22:00:00Z --output build/demo
```

If setup or the demo fails, open a bug report with the operating system, Python
version, exact command, complete error, and the smallest reproducible example.
Never paste credentials or proprietary source data into an Issue.

## Make a focused change

1. Fork the repository and create a descriptive branch.
2. Keep unrelated refactors out of the same pull request.
3. Add tests before or with the implementation.
4. Update user-facing documentation and examples.
5. Record data rights, attribution, and provenance where applicable.
6. Run `pytest` and the affected demo or case locally.
7. Complete the pull-request checklist honestly.

A pull request should explain:

- the research or user problem;
- what changed and what intentionally did not change;
- how the result was verified;
- whether public schemas, outputs, or behavior change;
- whether data or third-party material is added;
- whether AI materially assisted the contribution; and
- what uncertainty or follow-up work remains.

Draft pull requests are welcome for early design feedback. Maintainers may close
an unscoped implementation that bypasses an active design discussion, but should
explain how to restart it productively.

## Definition of done

The exact bar depends on the contribution lane. In general, merged work must:

- be understandable and appropriately scoped;
- pass required automated checks;
- include tests for new behavior and regressions;
- preserve the replay cutoff and provenance chain;
- distinguish observations, transformations, assumptions, and inferences;
- include documentation for public behavior;
- comply with source and dependency licenses; and
- receive the required review under the governance rules.

Claims of causal identification, forecast performance, or historical availability
require evidence proportionate to the claim. Passing unit tests is necessary but
does not replace domain review.

## Point-in-time and evidence rules

- Never select an observation using a later revised value when an as-released
  value is required.
- Never infer availability solely from the period an observation describes.
- Keep observation, release, vintage, ingestion, and cutoff times distinct.
- Never backdate `released_at` or `vintage_at` from an economic observation date
  or an approximate publication schedule.
- Label `prospective_capture` and `retrospective_authenticated` honestly; a later
  authenticated reconstruction is not evidence of in-time system capture.
- Preserve source artifacts or hashes sufficient to audit a transformation.
- Record timezone and release-calendar assumptions when they affect eligibility.
- Treat missing release metadata as unknown, not as evidence that a value was
  available.
- Do not rewrite a frozen claim after its evaluation window opens. Append a
  correction or superseding claim with a reason.

See [docs/research-contract.md](docs/research-contract.md) for the normative model.

## Data and third-party licensing

Apache-2.0 covers repository-authored code and documentation. It does not grant
permission to redistribute external data, charts, articles, model files, or API
responses.

Every connector or case that depends on external material must document:

- publisher and source URL;
- access or retrieval date;
- source terms or license URL;
- whether redistribution and modification are permitted;
- required attribution;
- whether the repository contains the data, a synthetic fixture, or only fetch
  instructions; and
- any geographic, account, rate, or purpose restriction relevant to users.

When rights are unclear, do not commit the material. Link to or fetch from the
official source, use a minimal synthetic fixture, and label the Issue
`needs: license-review`. Do not bypass authentication, paywalls, robots controls,
technical access restrictions, or source rate limits.

The detailed policy is in [docs/data-licensing.md](docs/data-licensing.md).
Current project policy excludes FRED and ALFRED connector recordings because
their terms conflict with software-driven storage, archival, and optional AI
use. Prefer the originating official publisher and request a new license review
instead of silently substituting a mirror.

## AI-assisted contributions

AI tools are optional. Contributors remain fully responsible for submitted work.
If an AI system materially generated code, prose, tests, source mappings, or
research claims:

- disclose the tool and the nature of assistance in the pull request;
- independently verify every factual claim, citation, license, and calculation;
- ensure no confidential data, credentials, or restricted source material was
  disclosed to the tool;
- review generated code for security, leakage, and fabricated dependencies; and
- preserve deterministic behavior when AI is unavailable.

AI output is not a primary source. A model's confident statement does not satisfy
the evidence requirement.

## RFC process

An RFC is required for changes to:

- the point-in-time research contract or time semantics;
- public artifact, observation, claim, or prediction schemas;
- compatibility or deprecation policy;
- security or trust boundaries;
- project-wide data-license policy;
- governance, contributor permissions, or the project charter; or
- architecture that imposes a significant irreversible cost on contributors.

Copy [docs/rfcs/0000-template.md](docs/rfcs/0000-template.md) into `docs/rfcs/`
using the next available number. Open a pull request marked `rfc`, and link a
Discussion when useful. The normal comment period is at least 14 days. Accepted
RFCs record alternatives and dissent; rejected RFCs remain useful project memory.

Bug fixes, new connectors behind stable interfaces, documentation corrections,
and bounded replay cases normally do not require an RFC.

## Review expectations

These are service goals, not guarantees:

- acknowledge a new Issue or pull request within three calendar days;
- provide a substantive response within 14 days; and
- aim to resolve or explicitly defer accepted work within 90 days.

Contributors should respond to requested changes within 14 days or leave a short
status note. Inactive work may be closed to keep the queue honest; it can be
reopened when work resumes.

Maintainers review the contribution, not the contributor. Requests for change
should be specific, respectful, and connected to documented project requirements.

## Attribution

Contributors retain copyright in their contributions and license them to the
project under Apache-2.0. Release notes should credit material contributions,
including first-time contributors, documentation, review, and data stewardship.

If your contribution implements or derives from academic work, cite the original
work in code or documentation in addition to crediting the implementation.
