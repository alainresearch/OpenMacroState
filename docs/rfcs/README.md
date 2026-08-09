# RFC process

RFCs are durable design records for changes that affect the research contract,
public schemas, compatibility, security boundaries, licensing policy, governance,
or another project-wide and difficult-to-reverse decision.

## Lifecycle

1. Discuss an early idea in GitHub Discussions when useful.
2. Copy `0000-template.md` to the next available four-digit number and a short
   slug, for example `0001-artifact-time-semantics.md`.
3. Open a pull request with the `rfc` label and name the responsible shepherd.
4. Revise the proposal during a public comment period of at least 14 days.
5. Record the decision under `Status` and merge the RFC as accepted, rejected,
   withdrawn, or superseded project memory.
6. Track implementation separately; accepting an RFC does not mean it is staffed.

The decision follows [GOVERNANCE.md](../../GOVERNANCE.md). Substantial new facts
may reopen an accepted or rejected decision through a superseding RFC.
