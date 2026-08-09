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

## Reviewed source decisions

These decisions are project policy based on the linked terms as reviewed on
2026-08-09. They are not a declaration that an entire institution's website has
one license. Recheck the terms and the specific source page before expanding a
connector.

### New York Fed Markets API and SOFR

The first official-source connector, `frbny-sofr`, uses the
[New York Fed Markets API](https://markets.newyorkfed.org/static/docs/markets-api.html)
and its date-bounded secured-rates endpoint. The New York Fed
[Terms of Use](https://www.newyorkfed.org/privacy/termsofuse.html) grant a
conditional license to access, download, store, use, copy, distribute, modify,
and create derivatives from content for personal or business purposes. The
conditions matter:

- retain copyright notices, source identifiers, and any author information;
- use the prescribed attribution when the source does not supply another form;
- label modifications clearly and do not attribute them to the New York Fed;
- distribute content with the same permissions, conditions, and restrictions;
- never state or imply New York Fed endorsement; and
- include the Terms' specific notice and disclaimer when presenting or
  distributing reference-rate data or related information.

The checked-in SOFR test excerpt has a `bundled` decision under these conditions;
connector license metadata records its redistribution as `restricted`. SOFR and
related material are **not** Apache-2.0 data. Every complete raw recording,
public extract, normalized dataset, chart, and report that presents the data
must carry an adjacent source note and the then-current reference-rate notice. A
test-only excerpt must be visibly labeled `test_only_excerpt`; it cannot be
described as a complete official response.

The authoritative economic and revision semantics remain in the New York Fed's
[SOFR documentation](https://www.newyorkfed.org/markets/reference-rates/sofr)
and
[publication and revision rules](https://www.newyorkfed.org/markets/reference-rates/additional-information-about-reference-rates).
The connector contract is documented in [connectors.md](connectors.md).

### FRED and ALFRED are excluded

Do not use the FRED or ALFRED API, scrape their services, or commit downloaded
FRED/ALFRED content as an OpenMacroState connector recording or fixture. The
current
[FRED Terms of Use](https://fred.stlouisfed.org/legal/terms/) expressly prohibit
using the services or content in connection with development or training of
software and AI systems. They also prohibit using the API to store, cache, or
archive content, provide stored content to third parties, or incorporate it into
a database, compilation, archive, or cache. Individual series can carry further
third-party rights.

Those restrictions conflict with this project's essential operation: software
freezes exact bytes, hashes them, archives them for replay, and may pass eligible
plaintext to an optional AI analysis layer. ALFRED's useful vintage semantics do
not supply permission to perform those operations. This source decision is
`blocked`, not `fetch_only`, unless the project obtains applicable written
permission or a future terms review documents a compatible grant.

Prefer the originating official publisher instead. For example, use a reviewed
Federal Reserve Board release or a New York Fed endpoint directly rather than a
FRED mirror. The Board's
[website disclaimer](https://www.federalreserve.gov/disclaimer.htm) says much of
its information is public domain, but each page must still be checked for
third-party material, trademarks, source attribution, and source-specific
conditions.

The planned H.4.1 connector will target dated official release material rather
than the Board's current-only Data Download Program or a FRED/ALFRED copy. The
Board's own
[Data Download Program help](https://www.federalreserve.gov/DataDownload/help/default.htm)
states that the program does not provide pre-revision or real-time data. The
[H.4.1 DDP page](https://www.federalreserve.gov/datadownload/Choose.aspx?rel=H41)
separately announces removal of the custom package builder in preparation for
the DDP's eventual retirement.

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
