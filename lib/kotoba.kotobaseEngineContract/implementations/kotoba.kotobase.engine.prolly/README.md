# kotobase-engine-prolly

An independent `kotobase-engine-contract/IEngine` implementation backed by
`arrangement` Prolly snapshots. It does not depend on `kotobase-peer`.

Logical Datom values are encoded into canonical EDN strings at the Arrangement
boundary and decoded on reads. This preserves keywords, numbers, booleans,
vectors, sets and maps while keeping the generic Arrangement primitive's
string-only physical contract.

Transactions use Arrangement `commit-changes!`, which coalesces assertions and
retractions into one deterministic Prolly mutation per index. Retractions are
real key deletion rather than tombstones: a deleted boundary re-chunks its leaf
and successor, while mixed additions/removals rebuild internal levels once.
The result is CID-identical to a full rebuild of the same logical graph.

Manifest format v3 writes a bounded content-addressed node above each
Arrangement snapshot. Request receipts, history, epoch pointers and transaction
coordinates live in a persistent metadata Prolly index. Sensitive values cross
the injected `encrypt-fn`/`decrypt-fn` boundary; request and Datom coordinate
keys cross the keyed `blind-fn` boundary. Readers retain format-v1/v2
compatibility and migrate on the next transaction.

`kotobase.engine.prolly.provider` adapts any JVM `kotobase-storage` backend to
the engine and publishes a manifest only through `IRefStore` compare-and-set.
A losing writer leaves harmless immutable blocks but cannot overwrite the
winner. S3-compatible providers must still pass `kotobase-storage`'s own CAS,
content-verification and concurrency suites before qualification.

The ClojureScript coordinator batches synchronously generated immutable blocks,
awaits the provider upload, and then performs CAS. Reopen fetches the bounded
manifest and current-request metadata path; reads use a direct async,
range-pruned Prolly cursor with bounded
concurrency. The regression harness reads one entity from a 2,001-Datom,
40-block snapshot using 4 data-block requests total. Cold mutation now fetches the
internal summary path plus only the affected leaf windows rather than warming
the full tree. A fresh writer changes a persisted 2,001-Datom/48-block snapshot
with 11 block requests, and the same manifest-only reopen/mixed retract+assert/
CAS/second-reopen flow passes against a real Miniflare `R2Bucket` with 4,001
seed Datoms. Normal reads point-lookup `t/` coordinates only for returned rows;
only explicit history scans the `h/` range. The implemented index and migration
invariants are specified in
[`docs/metadata-coordinate-index-v1.md`](docs/metadata-coordinate-index-v1.md).

Dependencies are fixed to published Git commit SHAs. West registration should
advance only to reviewed revisions; generated manifests are not edited with
invented SHAs.

```sh
kbb -M:test
kbb -M:lint
```
