# Treasury Debt to the Penny fixture notice

This is a machine-visible `test_only_excerpt` fixture for deterministic offline
connector tests. It contains real values returned by the official U.S. Treasury
Fiscal Data Debt to the Penny endpoint for 2026-08-05 and 2026-08-06, but the
JSON was reserialized for review. It is therefore not represented as the exact
wire bytes or a complete authenticated historical artifact.

Source: U.S. Department of the Treasury, Bureau of the Fiscal Service, Fiscal
Data, Debt to the Penny.

License classification: `US-Treasury-Fiscal-Data-Open-Data`

Terms and open-data policy:
<https://fiscaldata.treasury.gov/api-documentation/>

Treasury Fiscal Data states that its data is offered free, without restriction,
and may be copied, adapted, redistributed, or otherwise used for non-commercial
or commercial purposes. This decision applies only to the Treasury-generated data
records in this fixture; it does not grant rights in trademarks or third-party
material. Source attribution is retained for provenance and does not imply Treasury
endorsement.

The normalized observations produced by OpenMacroState are transformations of
this recorded fixture, not Treasury-authored or Treasury-endorsed records.
