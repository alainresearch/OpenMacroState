# Release process

OpenMacroState follows Semantic Versioning after the public API is defined. During
pre-alpha development, every release may contain breaking changes, which must be
called out explicitly.

## Cadence and channels

- Patch releases contain compatible fixes and data-source maintenance.
- Minor releases contain compatible features and documented deprecations.
- Major releases may remove deprecated interfaces or change stable contracts.
- Alpha, beta, and release-candidate tags describe increasing stability; they are
  not promises of fitness for trading or policy use.

The project aims for small, reviewable releases rather than waiting for a large
roadmap batch.

## Release checklist

The Release Manager:

1. confirms the version and intended compatibility level;
2. reviews merged changes for breaking behavior, migrations, and deprecations;
3. verifies new data sources have license and attribution records;
4. runs from a clean supported environment:

   ```bash
   python -m pip install -e '.[dev]'
   python -m ruff check .
   python -m ruff format --check .
   pytest
   openmacrostate demo cases/2023-banks \
     --reveal reveals/2023-banks \
     --evaluation-at 2023-03-13T22:00:00Z \
     --output build/demo
   openmacrostate connector capture frbny-sofr \
     --start 2023-03-22 --end 2023-03-22 \
     --recording tests/fixtures/connectors/frbny_sofr/recording.json \
     --output build/frbny-sofr
   openmacrostate validate build/frbny-sofr
   openmacrostate connector capture treasury-debt-to-penny \
     --start 2026-08-05 --end 2026-08-06 \
     --recording tests/fixtures/connectors/treasury_debt_to_penny/recording.json \
     --output build/treasury-debt-to-penny
   openmacrostate validate build/treasury-debt-to-penny
   openmacrostate connector capture fed-h41-release \
     --start 2023-03-16 --end 2023-03-16 \
     --recording tests/fixtures/connectors/fed_h41_release/recording.json \
     --output build/fed-h41-release
   openmacrostate validate build/fed-h41-release
   openmacrostate audit accounting build/fed-h41-release \
     --rule fed-h41-balance-sheet-v1 \
     --observed-at 2023-03-15T00:00:00Z \
     --json
   openmacrostate trace state build/fed-h41-release \
     --rule fed-h41-balance-sheet-v1 \
     --observed-at 2023-03-15T00:00:00Z \
     --target balance_sheet_residual \
     --json
   python -m build
   ```

5. installs the built wheel and source distribution into separate empty
   environments outside the checkout, runs the bundled example and connector
   recordings through the installed packages, then runs the Fed accounting
   audit and state trace against each installed H.4.1 capture;
6. confirms the source distribution contains `schemas/`, `cases/`, and
   `reveals/` rather than testing only an editable checkout;
7. inspects the demo manifest and distributions rather than relying only on a
   green CI badge;
8. drafts release notes with sections for breaking changes, new capabilities,
   connectors and cases, documentation, security, known limitations, and every
   material community contributor;
9. creates a signed or otherwise repository-verifiable tag where available;
10. runs the `Release checks` workflow and downloads its candidate artifacts;
11. publishes to package indexes only through a separately reviewed,
   least-privilege release environment; and
12. verifies installation and the demo from the published artifact.

The checked-in workflow deliberately does not publish automatically. Enabling
trusted publishing requires a separately reviewed RFC or release-infrastructure
change and a protected GitHub environment.

## Corrections and withdrawal

Do not overwrite a released artifact. Publish a new version and explain the
correction. If a release creates a security, licensing, or evidence-integrity
risk, mark it affected or withdraw it where the package host permits, preserve a
procedural record, and publish a safe replacement.
