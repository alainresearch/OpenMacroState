# Connector template

Replace every example value in `connector.json`, including the placeholder
license decision and review date, then add:

- one recorded and redistributable HTTP fixture;
- golden normalized observations;
- pagination, revision, timezone, and missing-data tests;
- exact release-time semantics;
- data terms covering retrieval, storage, redistribution, and commercial use.

A connector must never write directly to the artifact store, create its own
trusted hash, log secrets, or access a host absent from `allowed_hosts`.

The pre-alpha command line does not dynamically load this template or arbitrary
third-party Python packages. A candidate becomes executable only after review
and explicit registration as a trusted built-in connector.

In addition to a schema-valid connector spec, built-in implementation code must
declare:

- a non-empty `ruleset_version` that changes when normalization semantics
  change; and
- `CaptureBundleMetadata(title, fixture_kind, source_notice)` with a concise
  case title, an accurate fixture classification, and reviewed source-rights or
  attribution text.

The core validates that metadata, binds it into capture identity, and writes it
to the case and source notice. The connector still never receives an output path
or controls file placement. Presentation metadata belongs in implementation
code, not in `connector.json`.
