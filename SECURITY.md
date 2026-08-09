# Security Policy

OpenMacroState processes external data, preserves research artifacts, and may run
source-specific connector code. A vulnerability can therefore affect more than
availability: it can corrupt provenance, leak credentials, or silently change a
historical replay.

## Supported versions

During pre-alpha development, security fixes are applied to:

| Version | Support |
| --- | --- |
| `main` | Supported on a best-effort basis |
| Latest tagged pre-release | Supported when a safe patch is practical |
| Older pre-releases | Not supported |

After stable releases begin, this table will be replaced with an explicit support
window.

## Report a vulnerability privately

Do **not** open a public Issue, Discussion, or pull request for an undisclosed
vulnerability.

Use GitHub's private vulnerability reporting for this repository:

<https://github.com/alainresearch/openmacrostate/security/advisories/new>

If that feature is unavailable, contact a security contact listed in
[`MAINTAINERS.toml`](MAINTAINERS.toml) through the private contact method on their
GitHub profile. Do not include secrets in an initial message sent over an
unencrypted public channel.

Include, when possible:

- affected version or commit;
- vulnerability type and affected component;
- minimal reproduction or proof of concept;
- realistic impact, including evidence-integrity impact;
- prerequisite access, configuration, or data;
- suggested mitigation; and
- whether you intend to coordinate public disclosure.

Never send production credentials, personal data, proprietary datasets, or
material non-public information as part of a report. Use synthetic examples.

## What counts as a security issue

Examples include:

- arbitrary code execution or unsafe deserialization;
- command, query, path, archive, or template injection;
- directory traversal or writes outside the selected output directory;
- credential exposure in logs, manifests, reports, caches, or CI artifacts;
- connectors that bypass configured TLS or source authentication boundaries;
- malicious source artifacts escaping validation;
- dependency or release-pipeline compromise;
- privilege escalation in hosted or multi-user use; and
- a way to bypass a declared cutoff or alter a frozen artifact without detection.

An ordinary data correction, disputed economic interpretation, or documented
model limitation is normally not a security vulnerability. Report those through
the appropriate Issue template. If exploitation could silently falsify provenance
or replay results, use the private security channel.

## Response goals

The Security Team aims to:

- acknowledge a complete report within three business days;
- provide an initial severity assessment within 14 days;
- send a status update at least every 14 days while remediation is active; and
- coordinate a fix and disclosure date proportionate to risk.

These are goals, not guarantees. Reports affecting an upstream dependency or data
provider may require coordination outside the project.

## Coordinated disclosure

The project prefers coordinated disclosure after a fix or effective mitigation is
available. A public advisory should credit the reporter unless they request
anonymity and should describe affected versions, impact, remediation, and evidence
integrity implications without exposing unnecessary exploit detail.

Maintainers will not ask a reporter to hide known harm indefinitely. If the team
and reporter disagree on timing, both parties should make a good-faith effort to
reduce user risk and document unresolved facts accurately.

## Research expectations

Good-faith security research must avoid privacy violations, data destruction,
service degradation, social engineering, credential theft, and access to systems
or data without authorization. Test against local fixtures or infrastructure you
control whenever possible.
