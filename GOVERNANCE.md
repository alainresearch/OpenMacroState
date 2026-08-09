# OpenMacroState Governance

This document defines how authority is earned, exercised, reviewed, and handed
on. The project favors public reasoning, scoped permissions, and a low-friction
path from first contribution to maintainership.

## 1. Decision venues

- **GitHub Discussions** is the canonical venue for questions, exploratory ideas,
  community announcements, and design conversations.
- **GitHub Issues** tracks reproducible defects and accepted, bounded work.
- **Pull requests** contain reviewable changes and the final implementation record.
- **RFCs** record project-wide or difficult-to-reverse decisions.
- **MAINTAINERS.toml** is the authoritative ownership and role registry.

Decisions made in calls or synchronous chat have no standing until their outcome
and rationale are summarized in one of these public venues, except confidential
security and conduct matters.

## 2. Contributor ladder

### Community member

Anyone who participates under the Code of Conduct. Community members may ask and
answer questions, propose work, reproduce issues, and review public material.

### Contributor

Anyone with a merged or otherwise accepted material contribution. Contributions
include code, documentation, data-license review, case reproduction, economic
review, issue triage, and sustained community support.

Contributors may be invited to triage Issues and mentor first contributions.

### Reviewer

A trusted contributor with demonstrated competence in a defined area. Reviewers
may provide an approval that counts toward merge requirements but do not receive
merge, release, or repository-administration permission by default.

Normal Reviewer criteria are:

- at least three material accepted contributions in or adjacent to the area;
- at least three substantive reviews, reproductions, or design contributions;
- a record of respectful, evidence-based participation;
- understanding of point-in-time and data-license rules; and
- endorsement by one Module Maintainer or two existing Reviewers.

A nomination remains public for at least seven days. A Module Maintainer records
the outcome in `MAINTAINERS.toml`.

### Module Maintainer

A Reviewer entrusted with merge responsibility for a bounded module, connector
family, case library, documentation area, or operational function.

Normal Module Maintainer criteria are:

- sustained participation for at least three months;
- at least five material accepted contributions;
- at least five substantive reviews;
- demonstrated judgment about compatibility, evidence, and source rights;
- willingness to triage, mentor, and participate in releases; and
- no unresolved pattern of violating project policy.

The Steering Council approves a nomination after a public comment period of at
least 14 days. During bootstrap, the interim Project Lead may approve a nomination
with support from two Reviewers, or one Reviewer if fewer than two exist.

Permissions are scoped. A connector maintainer does not automatically gain
authority over governance, releases, security, or unrelated research domains.

### Steering Council

The Steering Council is responsible for project-wide technical direction,
governance, charter changes, cross-module disputes, maintainer appointments,
release policy, and stewardship of shared infrastructure.

Council members normally must have served as a Module Maintainer for six months.
They serve renewable 12-month terms. The Council should contain three to seven
members and should seek institutional, geographic, and disciplinary diversity.
Active Module Maintainers elect members by a simple majority with a two-thirds
quorum. Election records are public.

## 3. Bootstrap period

Until three independent Module Maintainers are active, the repository owner
listed in `MAINTAINERS.toml` serves as interim Project Lead and Steering Council.
Bootstrap authority is temporary, not hereditary. The interim lead must:

- use the same public RFC and review process;
- seek independent review whenever available;
- avoid granting broad permissions where scoped permissions suffice;
- publish material project decisions; and
- initiate the first Council election within 60 days of reaching three eligible
  Module Maintainers.

The bootstrap exception may not waive license, security, provenance, or Code of
Conduct requirements.

## 4. Routine decisions and merges

The project uses lazy consensus for ordinary, reversible work: after adequate
review, a Module Maintainer may merge if no unresolved blocking objection remains.

Minimum review:

- ordinary scoped changes: one approval from the owning Reviewer or Maintainer;
- a new connector or replay case: software/provenance review plus domain or data
  review when the contribution makes material economic claims;
- public schema, security boundary, release automation, governance, or licensing:
  an accepted RFC and two Maintainer approvals;
- a maintainer's own high-risk change: approval from another qualified Maintainer.

If the project has too few qualified Maintainers to meet a numeric rule, the
interim process substitutes a public review window of at least 14 days and the
strongest available independent review. The exception must be stated in the pull
request and expires when staffing is sufficient.

An objection is blocking only when it identifies a concrete correctness,
security, evidence, compatibility, licensing, governance, or charter concern.
Preference alone is not a veto.

## 5. RFC decisions

RFCs follow the process in [docs/rfcs/README.md](docs/rfcs/README.md).

The owning Maintainers seek consensus after the public comment period. If
consensus is not possible, the Steering Council votes. Ordinary RFCs require a
simple majority with a two-thirds quorum. Charter, governance, and license-policy
changes require a two-thirds majority of the full Council.

The decision record must summarize the question, material evidence, alternatives,
conflicts, dissent, and conditions for revisiting the decision.

## 6. Conflicts of interest

Anyone participating in a decision should disclose a material financial,
employment, funding, authorship, vendor, or personal interest that a reasonable
observer could consider relevant.

A conflicted participant may provide factual context but should not be the sole
approver. Council members recuse themselves from votes involving their own role,
conduct, commercial interest, or employer-specific benefit. Recusals reduce the
denominator used for quorum when at least two unconflicted voters remain.

## 7. Inactivity, resignation, and removal

Roles are responsibilities, not lifetime honors.

- A Reviewer or Module Maintainer may resign at any time.
- After six months without review, triage, release, or project communication, the
  Council asks whether the person wishes to become Emeritus.
- Emeritus contributors retain credit and may be renominated through an expedited
  public review after returning.
- Permissions may be suspended immediately when necessary to protect users,
  credentials, releases, or evidence integrity. The action receives confidential
  review and a public procedural summary when safe.
- Removal for sustained nonperformance or misconduct requires a two-thirds vote
  of unconflicted Council members and a documented opportunity to respond, except
  where immediate safety requires temporary suspension.

No person votes on their own appointment, suspension, or removal.

## 8. Releases and security

Release Managers are Module Maintainers explicitly listed for the release area.
They follow [docs/releasing.md](docs/releasing.md), cannot weaken required checks
for convenience, and use least-privilege credentials.

The Security Team is listed in `MAINTAINERS.toml`. Confidential vulnerability
details are restricted to people needed for remediation. Security fixes receive
normal public review after disclosure when doing so no longer creates risk.

## 9. Response and transparency goals

The project aims to acknowledge new Issues and pull requests within three calendar
days, provide a substantive response within 14 days, and resolve or explicitly
defer accepted work within 90 days. Maintainers publish a brief queue-status note
when these goals cannot be met.

Council decisions, elections, active RFCs, releases, and changes to permissions
must remain discoverable in the repository or linked GitHub history.

## 10. Changing this document

Governance changes require an RFC, at least 14 days of public comment, and the
approval threshold for project-wide governance decisions. Emergency temporary
rules expire after 30 days unless ratified through that process.
