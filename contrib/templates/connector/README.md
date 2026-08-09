# Connector template

Replace every `CHANGE_ME` value, then add:

- one recorded and redistributable HTTP fixture;
- golden normalized observations;
- pagination, revision, timezone, and missing-data tests;
- exact release-time semantics;
- data terms covering retrieval, storage, redistribution, and commercial use.

A connector must never write directly to the artifact store, create its own
trusted hash, log secrets, or access a host absent from `allowed_hosts`.
