# OpenMacroState documentation

Start with an H.4.1 brief: inspect seven Federal Reserve balance-sheet values,
compare two captures, and export a table with its source record.

## Use the current repository version

- [Quickstart: install and make your first offline brief](quickstart.md)
- [H.4.1 briefs: comparisons, exports, and checks](h41-brief.md)
- [Connector guide: H.4.1, SOFR, and Treasury captures](connectors.md)
- [Synthetic research demo](quickstart.md#synthetic-research-demo)

The brief command is part of the repository's development version and is not in
the latest GitHub pre-release, `v0.1.0a6`. Follow the source-install instructions
in the quickstart. No AI service is required.

## Inspect evidence and calculations

- [Federal Reserve H.4.1 source contract](fed-h41-source-contract.md)
- [Experimental H.4.1 accounting audit](accounting-audit.md)
- [Experimental H.4.1 state trace](state-trace.md)
- [Research contract and five-time model](research-contract.md)
- [Data licensing](data-licensing.md)

Official-source connectors preserve present-day captures conservatively; they
do not authenticate an old vintage from its date alone. The `2023-banks` research
and reveal bundles are synthetic teaching fixtures. The proposed
[unscored H.4.1 evidence canary](https://github.com/alainresearch/OpenMacroState/pull/18)
remains Draft and awaits independent review.

## Contribute and maintain

- [Contribution guide](../CONTRIBUTING.md)
- [Governance](../GOVERNANCE.md)
- [RFC process](rfcs/README.md)
- [Triage](triage.md)
- [Release process](releasing.md)
- [中文介绍](zh-CN/README.md)

The longer-term goal is an auditable macro research system. Research inputs and
post-resolution reveal material remain separate, and AI-assisted analysis is
subject to the same evidence and cutoff rules as any other analysis.
