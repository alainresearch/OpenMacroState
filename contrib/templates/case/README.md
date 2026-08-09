# Case pack template

Case packs contain prediction-time research only. Post-resolution records belong
in an independent object conforming to `schemas/v1/reveal.schema.json`; they must
not appear anywhere in this directory. Research packs must include:

- an exact information cutoff;
- immutable input checksums;
- an artifact ledger plus content-addressed artifact files that close every
  observation `artifact_id`;
- evidence publication and vintage times;
- a declared availability mode; authenticated retrospective ingestion must carry
  a verified version-release proof on the artifact;
- at least one simple baseline;
- a resolution rule and scoring rule fixed before reveal;
- source and data-license notes;
- an explicit `synthetic` label whenever any input is invented.

Never place resolved event data or its checksum in the prediction-time bundle.
