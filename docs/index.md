# OpenMacroState documentation

OpenMacroState is an auditable, point-in-time operating system for global macro
research. Start with:

- [Quickstart](quickstart.md)
- [Connector trust and capture contract](connectors.md)
- [Federal Reserve H.4.1 source contract](fed-h41-source-contract.md)
- [Research contract](research-contract.md)
- [Data licensing](data-licensing.md)
- [Contribution guide](../CONTRIBUTING.md)
- [Governance](../GOVERNANCE.md)
- [RFC process](rfcs/README.md)
- [Triage](triage.md)
- [Release process](releasing.md)
- [中文介绍](zh-CN/README.md)

The deterministic replay and evidence layers do not require AI. AI-assisted
analysis is optional and remains subject to the same cutoff, provenance, and
review requirements.

The current executable `cases/2023-banks` example is a wholly synthetic teaching
fixture, not historical evidence. The `fed-h41-release`, `frbny-sofr`, and
`treasury-debt-to-penny` official-source connectors are present as pre-alpha
conservative prospective-capture slices, not reviewed historical evidence
packs. Real historical replay remains roadmap work.

Prediction-time research under `cases/` and post-resolution material under
`reveals/` are independent bundles. The validator reads only the former; see the
[research contract](research-contract.md) for the five-time model and the
`prospective_capture` versus `retrospective_authenticated` assurance boundary.
