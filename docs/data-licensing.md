# Data and third-party material policy

## License boundary

Apache-2.0 covers repository-authored code and documentation unless a file says
otherwise. It does not relicense external datasets, API responses, charts,
articles, filings, publications, model files, logos, or trademarks.

Publicly accessible does not necessarily mean public domain or redistributable.

## Required source record

Every connector, research case, and reveal bundle must document, in its own
manifest or adjacent source note:

- publisher and canonical source URL;
- dataset, series, table, or document identifier;
- access or retrieval time;
- applicable terms or license URL and review date;
- permitted access, modification, caching, and redistribution;
- required attribution and notices;
- geographic, account, rate, or purpose restrictions;
- whether the repository stores source data, a synthetic fixture, or fetch
  instructions; and
- the responsible contributor and any unresolved license question.

Research and reveal bundles have separate integrity and license boundaries.
Permission to distribute prediction-time source material does not imply
permission to distribute later outcome material, or vice versa.

## Redistribution decision

Use one of these explicit outcomes:

- `bundled` — redistribution is clearly permitted and attribution is included;
- `fetch_only` — users retrieve the material from the official source;
- `reference_only` — the project stores identifiers, hashes, or citations only;
- `synthetic_fixture` — tests use invented values and no source records; or
- `blocked` — rights are unclear or incompatible, so the material is not used.

When in doubt, choose `blocked` or `fetch_only` and request license review.

## Fixtures and examples

Prefer small synthetic fixtures for deterministic tests. A fixture derived from
real data is not automatically synthetic; aggregation, truncation, or format
conversion may still reproduce protected content. Document the derivation or use
invented values.

Do not commit secrets, account-specific downloads, personal data, proprietary
research, material non-public information, or content obtained by bypassing an
access control. Do not make a public CI job depend on a contributor's private key.

## Source changes

Connector maintainers should monitor material changes to source terms. If rights
become uncertain, disable redistribution first, preserve only lawful metadata,
and open a public procedural Issue without reposting the disputed content.

## Attribution

Generated reports should carry source-level attribution close enough to the data
or claim to be useful. Repository-level acknowledgement in `NOTICE` does not
replace source-specific attribution.

This policy is operational guidance, not legal advice. Seek qualified review when
a source presents a material or ambiguous legal risk.
