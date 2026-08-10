# OpenMacroState

[![CI](https://github.com/alainresearch/OpenMacroState/actions/workflows/ci.yml/badge.svg)](https://github.com/alainresearch/OpenMacroState/actions/workflows/ci.yml)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](https://www.python.org/)
[![Code/docs: Apache-2.0](https://img.shields.io/badge/code%20%26%20docs-Apache--2.0-blue.svg)](LICENSE)
[![Pre-release: v0.1.0a6](https://img.shields.io/badge/pre--release-v0.1.0a6-orange.svg)](https://github.com/alainresearch/OpenMacroState/releases/tag/v0.1.0a6)

**An auditable, point-in-time operating system for global macro research.**

OpenMacroState is building a way for researchers to reconstruct what could have
been known at a historical cutoff, connect evidence to explicit mechanisms,
record falsifiable claims, and score those claims after outcomes arrive.

> Replay what the world knew, not what history later revised.

## The value in 30 seconds

OpenMacroState turns exact source bytes into a research record that can answer
four questions later: **what was available, when was it available, which claim
used it, and how did the claim score?**

It does this without asking an AI model to remember the boundary:

1. freeze a core-observed official response or separately recorded bytes;
2. hash it and preserve its retrieval metadata without treating a self-reported
   receipt time as historical proof;
3. normalize observations with five distinct time fields;
4. reject evidence that was not eligible at the research cutoff; and
5. keep later outcomes in a separate reveal bundle until scoring is allowed.

```mermaid
flowchart LR
    A["Official source<br/>or recorded response"] --> B["Core-owned transport<br/>and SHA-256 freeze"]
    B --> C["Review-trusted<br/>built-in connector"]
    C --> D["Five-clock<br/>observations"]
    D --> E["Cutoff and<br/>evidence closure"]
    E --> F["Frozen research<br/>snapshot"]
    G["Physically separate<br/>reveal bundle"] --> H["Post-resolution<br/>scoring"]
    F --> H
```

OpenMacroState is not another chart terminal and does not claim to predict
markets. Its first three official-source pre-alpha vertical slices are the New
York Fed SOFR connector, `frbny-sofr`, the U.S. Treasury Debt to the Penny
connector, `treasury-debt-to-penny`, and the Federal Reserve Board dated H.4.1
connector, `fed-h41-release`. All are deliberately conservative:
historical values retrieved today do not become evidence that the system had
captured them in the past. Replaying a recording with an old `retrieved_at`
claim does not restore past availability either: without an authenticated proof,
the core uses the current replay time for eligibility. See the
[connector contract](docs/connectors.md).

## Project status

OpenMacroState is in **pre-alpha development**. Interfaces, schemas, and bundled
cases may change before the first stable release. Today the repository provides
a public research contract, versioned interchange schemas, public plugin
protocols, an executable offline validator/demo, and three pre-alpha
official-source capture paths. It also includes one fixed experimental H.4.1
accounting audit and a read-only trace from derived values back to their accepted
observations and preserved artifact. This is not yet a general or stable
state-graph interface.
These connectors are not stable historical evidence packs. The repository still
does **not** ship a production model adapter or a reviewed real historical replay,
and it is not a production trading or policy system.

The current public pre-release is [v0.1.0a6](https://github.com/alainresearch/OpenMacroState/releases/tag/v0.1.0a6).
Its wheel and source archive are available from GitHub Releases only;
OpenMacroState has not been published to PyPI. To help shape the next milestone,
review the Draft [2023 banking-stress replay RFC](https://github.com/alainresearch/OpenMacroState/pull/18)
or claim the scoped [`inspect-recording` good first issue](https://github.com/alainresearch/OpenMacroState/issues/14).

## Five-minute synthetic demo

Python 3.10 or newer is recommended.

```bash
git clone https://github.com/alainresearch/openmacrostate.git
cd openmacrostate
python -m pip install -e '.[dev]'

openmacrostate validate cases/2023-banks
openmacrostate demo cases/2023-banks --reveal reveals/2023-banks --evaluation-at 2023-03-13T22:00:00Z --output build/demo
```

A wheel built from the repository also carries this small fixture, so its
shortest smoke test is:

```bash
openmacrostate example 2023-banks --output build/example
```

`cases/2023-banks` is a **synthetic teaching fixture**: every value is invented,
and its date-shaped scenario is not evidence about any real bank or historical
event. It exists to test cutoff enforcement, transitive evidence rejection, and
reveal-gated scoring without a network connection, AI provider, or API key.

The prediction-time research bundle under `cases/` and the post-resolution
reveal bundle under `reveals/` are physically separate and have independent
integrity manifests. `validate` reads only the research bundle; it neither needs
nor reads a reveal. `demo` requires both paths and an explicit evaluation time.
Existing output paths are refused by default; use `--force` only to replace an
empty directory or a marked prior output for the same case.

Run lint and the full test suite with:

```bash
python -m ruff check .
pytest
```

See the [quickstart](docs/quickstart.md) for the expected artifacts and common
troubleshooting steps.

## Official-source captures

The built-in `frbny-sofr` connector exercises the full acquisition boundary
without making network access implicit:

```bash
mkdir -p build
openmacrostate connector capture frbny-sofr \
  --start 2023-03-22 --end 2023-03-22 \
  --recording tests/fixtures/connectors/frbny_sofr/recording.json \
  --output build/frbny-sofr
openmacrostate validate build/frbny-sofr
```

This offline fixture produces six normalized observations and a case bundle
with eight checksummed research files. Its bytes and manifest are reproducible,
but its source and receipt time remain explicitly unverified. Use `--online`
instead of `--recording` only when you intentionally want the core to make one
allowlisted HTTPS request. Live capture is labeled `core_observed_https`; that
is a local acquisition record, not a signed historical timestamp or a causal
claim. See the [connector contract](docs/connectors.md).

The second built-in connector captures total U.S. public debt outstanding from
Treasury Fiscal Data's Debt to the Penny endpoint:

```bash
openmacrostate connector capture treasury-debt-to-penny \
  --start 2026-08-05 --end 2026-08-06 \
  --recording tests/fixtures/connectors/treasury_debt_to_penny/recording.json \
  --output build/treasury-debt-to-penny
openmacrostate validate build/treasury-debt-to-penny
```

This reserialized `test_only_excerpt` contains real Treasury values and produces
two normalized `treasury.debt.total_public_outstanding` observations. It is an
offline parser and provenance fixture, not exact original wire bytes and not an
authenticated 2026 historical vintage. The live connector fixes the official
host, selected fields, encoded date filter, ascending sort, JSON format, and a
single bounded page; it rejects empty, truncated, same-day, future, malformed,
or out-of-order results.

The third connector captures one dated Federal Reserve Board H.4.1 balance-sheet
release. Equal start and end values identify the release artifact:

```bash
openmacrostate connector capture fed-h41-release \
  --start 2023-03-16 --end 2023-03-16 \
  --recording tests/fixtures/connectors/fed_h41_release/recording.json \
  --output build/fed-h41-release
openmacrostate validate build/fed-h41-release
```

The fixture produces seven `USD_million` Wednesday observations: total assets,
total liabilities, total capital, securities held outright, primary credit, the
Treasury General Account, and reserve balances. It is a small
`test_only_excerpt`, not the full official page or an authenticated 2023 vintage.
The parser selects exact semantic rows and the Wednesday stock column rather than
a table position, and it rejects date, unit, column, row, number, and DOM drift.

The first experimental accounting rule then checks the three Table 5 totals at
the same source, artifact, unit, and observation time:

```bash
oms audit accounting build/fed-h41-release \
  --rule fed-h41-balance-sheet-v1 \
  --observed-at 2023-03-15T00:00:00Z
```

It tests `assets = liabilities + capital` with a fixed tolerance of exactly
1 `USD_million` for reported whole-million rounding. It reads values only from
accepted observations, re-hashes and re-normalizes the preserved local artifact,
and requires all seven regenerated records to match exactly. This proves local
derivation, not source acquisition or historical availability, and it does not
create a stable public accounting schema. See the
[accounting audit guide](docs/accounting-audit.md) and dedicated
[H.4.1 source contract](docs/fed-h41-source-contract.md).

The experimental state trace can then explain one derived value's exact
arithmetic lineage:

```bash
oms trace state build/fed-h41-release \
  --rule fed-h41-balance-sheet-v1 \
  --observed-at 2023-03-15T00:00:00Z \
  --target balance_sheet_residual
```

`--target all --json` emits the full fixed graph: seven reported facts, six
derived facts, and twelve explicitly non-causal dependency edges. It inherits
the audit, snapshot, artifact, parser, time, and authentication hashes, but
remains a retrospective reconstruction rather than proof of 2023 availability
or causality. See the [state-trace guide](docs/state-trace.md).

## The problem it addresses

Macro research is unusually vulnerable to hindsight:

- economic series are revised after their original release;
- policy documents, market prices, and balance sheets arrive on different clocks;
- narrative explanations are often detached from reproducible calculations;
- failed predictions can quietly disappear or be rewritten; and
- AI systems can produce fluent conclusions without respecting the historical
  information boundary.

OpenMacroState makes the information boundary explicit. A replay should answer:

1. What information was actually public at the cutoff?
2. Which balance sheets or state variables changed?
3. Through which mechanism could the change propagate?
4. What competing explanations remain plausible?
5. Which future observation would weaken or falsify each claim?
6. What happened, and how should the recorded claim be scored?

## Research contract

Every publishable result should be:

- **point-in-time** — later releases and revisions cannot leak into a replay;
- **auditable** — claims resolve to immutable source artifacts and calculations;
- **reproducible** — a documented command rebuilds the result;
- **explicit about uncertainty** — observations, inferences, and forecasts are
  distinguishable;
- **mechanism-first** — accounting boundaries and transmission paths are named;
- **falsifiable** — forward-looking claims include a horizon and evaluation rule.

The core time model keeps five concepts separate: when a value was observed,
released, vintaged, ingested, and the research information cutoff. Cases also
declare either `prospective_capture` or `retrospective_authenticated` availability;
the latter may accept later ingestion only with a verified, pre-cutoff version
proof bound to the exact source, digest, and publication time. The current
pre-alpha verifier accepts only the explicitly synthetic fixture proof; real
late-ingested evidence fails closed. See the
[research contract](docs/research-contract.md).

## AI is optional

The currently implemented deterministic core—checksum verification, cutoff
filtering, evidence-closure checks, snapshots, and reveal-gated scoring—works
without an AI service. AI-assisted components may propose claims, compare
explanations, or draft prose, but they do not get to:

- bypass the replay cutoff;
- invent or silently replace evidence;
- modify frozen artifacts;
- turn an inference into an observation; or
- publish an unsupported claim as fact.

The analysis snapshot contains only eligible plaintext. Quarantined values,
rejected claims, and their future artifact metadata stay in separate validator
diagnostics and are never part of the view supplied to an AI.

AI-generated contributions are welcome when they meet the same review, licensing,
testing, and attribution standards as human-written work.

## Project map

```text
src/openmacrostate/
  api/v1/         public value types, errors, and connector/model protocols
  connectors/     fixed registry of review-trusted built-in connectors
  runtime/        case loading, cutoff filtering, accounting, state tracing, and scoring
  cli.py          validation, captures, demos, audits, and experimental trace commands
schemas/v1/       JSON Schema interchange contracts
cases/2023-banks/ synthetic offline teaching fixture (not historical evidence)
reveals/2023-banks/ separate synthetic post-resolution outcome bundle
contrib/templates/ starter skeletons for future connectors, models, and cases
tests/            runtime, CLI, and public-schema contract tests
docs/             research, contribution, and governance documentation
```

The connector and model directories under `contrib/templates/` are extension
templates, not bundled live integrations. Connector execution is fail-closed:
offline recordings are the reproducible default workflow, live network access
must be selected explicitly, and arbitrary third-party Python plugins are not
loaded in this pre-alpha. See [docs/connectors.md](docs/connectors.md).

## Ways to contribute

You do not need to be both an economist and a software engineer. The main
contribution lanes are:

- add or repair a public-data connector;
- build or audit a historical replay case;
- document a mechanism, accounting boundary, or competing explanation;
- adapt a model behind the common interface;
- improve tests, documentation, translations, or accessibility; and
- reproduce an issue, review evidence, or answer a community question.

Start with [CONTRIBUTING.md](CONTRIBUTING.md). Small fixes may go directly to a
pull request; substantial changes to the core protocol begin with an RFC. Project
priorities are described in the [roadmap](ROADMAP.md). Contributors working on
official sources should also read the [connector contract](docs/connectors.md)
and [data-license policy](docs/data-licensing.md).

## Community and governance

GitHub Discussions is the canonical, searchable home for questions, ideas, and
design conversations. GitHub Issues tracks accepted work and defects. Decisions
made in synchronous chats or meetings must be summarized back to GitHub.

OpenMacroState uses a public contributor ladder:

```text
Contributor -> Reviewer -> Module Maintainer -> Steering Council
```

Responsibilities, promotion criteria, decision rules, and succession are defined
in [GOVERNANCE.md](GOVERNANCE.md). Current ownership is recorded in
[MAINTAINERS.toml](MAINTAINERS.toml).

## Releases, security, and citation

- Release policy: [docs/releasing.md](docs/releasing.md)
- Security reporting: [SECURITY.md](SECURITY.md)
- Project citation: [CITATION.cff](CITATION.cff)
- Project charter: [PROJECT_CHARTER.md](PROJECT_CHARTER.md)

## Licensing

Project code and repository-authored documentation are licensed under the
[Apache License 2.0](LICENSE), unless a file states otherwise.

**That license does not automatically apply to downloaded or bundled data.** Each
connector, research case, and reveal bundle must identify source terms,
redistribution status, and required attribution. Data without clear
redistribution permission must be fetched from its source or represented by a
small synthetic fixture. See
[docs/data-licensing.md](docs/data-licensing.md) and [NOTICE](NOTICE).

OpenMacroState provides research infrastructure, not investment, legal, or policy
advice. Source data can be incomplete, revised, delayed, or wrong.

---

## 中文快速介绍

**OpenMacroState 是一个可审计、可回到历史当时的全球宏观研究操作系统。**

它不是另一个行情终端，也不承诺“AI 预测市场”。它首先解决一个更基础的
问题：在某个历史时点，研究者当时究竟能够知道什么？项目把证据的观测时间、
发布时间、版本时间、采集时间和研究截止时间分开，并把结论连接到来源与可证伪
条件。

当前内置的 `2023-banks` 只是**合成教学夹具**：所有数值均为虚构，用来检验
时间截止、证据传递拒绝和事后评分，不构成任何真实银行或历史事件的证据。
它不依赖 AI 或 API Key；AI 只能作为可选分析层，不能越过时间边界，也不能
替代证据。研究包位于 `cases/`，事后揭晓包位于 `reveals/`，二者各自拥有完整性
清单；`validate` 完全不读取揭晓包。代码采用 Apache-2.0，外部数据仍遵守各自
许可证。

首批三个官方数据纵向切片已经落地：纽约联储 SOFR 连接器 `frbny-sofr`、
美国财政部总公共债务连接器 `treasury-debt-to-penny`，以及美联储 H.4.1
带日期发布页连接器 `fed-h41-release`。三者都采用保守时间规则：今天抓取到的
历史值，不会被倒填成系统在当年已经捕获的证据。H.4.1 还提供首个实验性会计
校验，用固定 100 万美元容差核对“总资产 = 总负债 + 总资本”，但尚未形成稳定
会计 schema 或通用状态图。新的实验性 state trace 可以把会计派生值逐步追溯到
七条合格观测、原始材料哈希和解析规则；所有边都明确标为非因果，也不会把今天
的重算冒充成 2023 年已经知道的结论。详见 [Connector 契约](docs/connectors.md)、
[会计校验说明](docs/accounting-audit.md)与[状态追溯说明](docs/state-trace.md)。

快速运行：

```bash
python -m pip install -e '.[dev]'
openmacrostate validate cases/2023-banks
openmacrostate demo cases/2023-banks --reveal reveals/2023-banks --evaluation-at 2023-03-13T22:00:00Z --output build/demo
```

欢迎贡献数据连接器、历史案例、宏观机制、模型适配器、测试、文档和中文内容。
详细说明见[中文项目介绍](docs/zh-CN/README.md)与
[贡献指南](CONTRIBUTING.md)。
