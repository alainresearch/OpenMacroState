# OpenMacroState Project Charter

## 1. Purpose

OpenMacroState exists to make global macro research inspectable, reproducible,
and accountable to the information that was available at the time. It provides
open protocols and software for collecting point-in-time evidence, representing
macro-financial state, testing mechanisms, recording claims, replaying historical
decisions, and evaluating subsequent outcomes.

The project is a public research infrastructure effort. Its success is measured
by the quality and reuse of its research contract—not by the volume or confidence
of its forecasts.

## 2. Scope

OpenMacroState may include:

- schemas for artifacts, observations, state variables, claims, and predictions;
- connectors to public or contributor-authorized data sources;
- immutable manifests and point-in-time snapshot tooling;
- accounting identities and balance-sheet representations;
- mechanism libraries and model adapters;
- executable historical replay cases;
- evaluation, scoring, and uncertainty-reporting tools;
- human-readable reports derived from auditable artifacts; and
- optional AI-assisted analysis constrained by the same evidence boundary.

## 3. Non-goals

OpenMacroState is not:

- a promise of profitable forecasts;
- a substitute for Bloomberg, Refinitiv, or another licensed data terminal;
- a repository for redistributing data without permission;
- a single canonical macroeconomic model;
- an authority that decides which economic school is correct;
- a vehicle for silently promoting a commercial product, political program, or
  investment position; or
- a system in which AI-generated prose is accepted as evidence.

## 4. Core principles

### Point-in-time integrity

A replay may use only information that satisfies its declared knowledge cutoff.
Release calendars, revisions, and availability constraints are first-class data.

### Evidence before narrative

Every material factual claim should resolve to a source artifact or a reproducible
calculation. The system distinguishes source facts, transformations, inferences,
assumptions, scenarios, and forecasts.

### Accounting before causal storytelling

Contributions identify the entities, instruments, units, and balance-sheet
boundaries involved. Accounting consistency does not prove causality, but a
causal explanation that violates accounting is rejected.

### Competing explanations

The project preserves credible alternatives and conditions under which they
would become more or less plausible. Minority views may not be removed merely
because a majority prefers another interpretation.

### Falsifiability and memory

Forecasts and directional claims state a horizon, observable outcome, and scoring
rule before the outcome is known. Corrections append to the record; they do not
silently rewrite it.

### Deterministic core, optional AI

The core workflow remains usable without a proprietary model or external AI
service. AI output is treated as a proposal subject to provenance, validation,
review, and reproducibility requirements.

### Open participation with bounded trust

Anyone may propose changes. Merge, release, and security permissions are earned
through sustained, reviewable work and are scoped to the smallest practical area.

## 5. Intended users

The project serves economists, market researchers, policy analysts, journalists,
students, data engineers, model developers, and AI researchers. No contributor is
expected to possess every relevant skill; cross-disciplinary review is a feature
of the project.

## 6. Public artifacts and privacy

The repository accepts public or properly licensed research material. It does not
accept personal data, credentials, confidential client material, material
non-public information, unlawfully obtained data, or content whose publication
would breach a contractual duty.

## 7. Independence and conflicts

Contributors disclose material financial, institutional, employment, or research
conflicts relevant to a proposal or review. A disclosed conflict does not
automatically disqualify participation, but conflicted maintainers should recuse
themselves when impartial review could reasonably be questioned.

Project decisions follow [GOVERNANCE.md](GOVERNANCE.md), not donor, employer, or
founder preference alone. Sponsorship does not buy technical approval.

## 8. Licensing boundary

Repository-authored code and documentation are Apache-2.0 unless explicitly
marked otherwise. External data, model inputs, publications, and source artifacts
retain their own rights and terms. A contribution must document those terms and
must not imply that the project license grants rights the contributor does not
hold.

## 9. Amendments

Material amendments to this charter require an RFC, a public comment period of at
least 14 days, and approval under the governance rules for project-wide decisions.
The change and rationale must be recorded in the repository history.
