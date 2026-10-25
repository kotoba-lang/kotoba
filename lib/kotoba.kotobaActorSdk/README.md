# kotoba-actor-sdk

Shared SDK boundary for actors deployed through app-aozora.  This is not a
domain actor and has no DID or deployment entry of its own.

- `sdk/` — substrate SDK
- `auth/` — PDS session adapter for the SDK
- `mock/` — in-memory test double

Domain actors depend on these packages from their own `etzhayyim` repositories.
`app-aozora` must not retain source mirrors of them.

`storage-profile.edn` is the inherited persistence boundary for generated and
SDK-backed actors. Private state is editable/queryable locally and enters a
repository or remote only as Kagi-sealed chunks with a Kotobase head over
DataLad. Public facts need a separate explicit classification; repository
visibility alone is not one.
