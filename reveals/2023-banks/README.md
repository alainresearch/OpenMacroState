# 2023 Banks synthetic reveal bundle

This directory is the independent post-resolution companion to case
`2023-banks-synthetic-v1`. It is a completely synthetic, offline software
fixture and is not historical evidence.

## Reveal contract

- `reveal.json` is the only entry point.
- Consumers must reject access before `not_before`.
- `outcomes.jsonl` contains the resolved synthetic event record.
- `artifacts.jsonl` closes each outcome `artifact_id` to an immutable local file
  under `artifacts/`.
- `checksums/sha256.json` covers every contract-bearing reveal file except
  itself and is independent of the research case manifest.
- `expected/assertions.json` contains post-resolution and scoring assertions.

The corresponding research bundle is separately distributed under
`cases/2023-banks`. Research validation must succeed without this directory.
