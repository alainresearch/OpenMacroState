# Public wire schemas

Files under `schemas/v1/` are the versioned interchange contract between the
OpenMacroState core, connectors, model adapters, and case packs. They describe
portable records; they are not an invitation to import internal runtime code.

Research case packs and post-resolution reveal bundles are separate wire
objects. A `case` points only to prediction-time artifacts, observations,
claims, and predictions. A `reveal` independently identifies outcome records,
their source artifacts, its activation time, and its checksum manifest.

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
