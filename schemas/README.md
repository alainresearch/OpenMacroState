# Public wire schemas

Files under `schemas/v1/` are the versioned interchange contract between the
OpenMacroState core, connectors, model adapters, and case packs. They describe
portable records; they are not an invitation to import internal runtime code.

Research case packs and post-resolution reveal bundles are separate wire
objects. A `case` points only to prediction-time artifacts, observations,
claims, and predictions. A `reveal` independently identifies outcome records,
their source artifacts, its activation time, and its checksum manifest.

Connector capture adds three v1 wire objects:

- `connector.schema.json` describes the declared identifier, exact host
  allowlist, source IDs, API version, secret policy, and source-license metadata
  of a review-trusted built-in connector;
- `http-recording.schema.json` describes a secret-free recorded request,
  response receipt, body path, byte length, and SHA-256; and
- `collection.schema.json` records one core-mediated connector collection,
  including capture mode, effective eligibility time, transport time claim,
  core-observed versus unverified source status, frozen artifact, normalized
  observation IDs, and their content root.

Schema validity is not time authenticity. In particular, a valid HTTP recording
may contain a syntactically valid but self-reported `retrieved_at`. Its SHA-256
proves that the replayed bytes match the manifest; it does not prove when those
bytes were captured. The core records that receipt value as
`transport_retrieved_at_claim` and, unless an accepted proof authenticates it,
uses the current replay wall-clock for eligibility. Likewise, a valid connector
spec is not proof that arbitrary plugin code is sandboxed or trusted, and a
valid license object is not legal approval to redistribute source content.

Compatibility rules:

- published schema files are immutable;
- compatible additions belong in each record's `extensions` object;
- extension keys should use reverse-domain names, for example
  `org.example.liquidity_metric`;
- breaking changes create a new versioned directory and an explicit migration;
- semantic validation, including cutoff and lineage checks, remains the core
  runtime's responsibility.

Schema version, plugin API version, package version, and case content version
are deliberately independent.
