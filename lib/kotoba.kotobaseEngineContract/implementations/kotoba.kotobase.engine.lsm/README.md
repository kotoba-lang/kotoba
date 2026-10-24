# kotobase-engine-lsm

Independent Merkle-LSM implementation of `kotobase-engine-contract/IEngine`.
It depends on the pure `merkle-lsm` mechanism, not on `kotobase-peer`, Prolly,
Arrangement, S3 or a deployment runtime.

Each transaction appends immutable covering-index L0 runs and writes a bounded
engine manifest above the Merkle-LSM VersionManifest. Format v3 stores history,
idempotency records and epoch pointers in a persistent Prolly metadata index.
Sensitive values always cross the required `encrypt-fn`/`decrypt-fn` boundary,
and request keys cross the required keyed `metadata-key-fn` boundary. Cumulative
plaintext EDN maps are never copied into a root. Format-v1 and v2 readers remain
available for migration. Reads apply MVCC visibility
at the requested epoch. The transaction path deterministically compacts an L0
index when `:l0-compaction-threshold` (default 8) is reached. Hosts may inject
`:reader-pins-fn`; the engine computes a monotonic safe epoch from active query,
replica and legal-hold pins, persists it in both manifests, and rejects snapshot
opens below the retained boundary. With no pins the conservative default stays
at epoch zero and preserves every historical MVCC version.

With `{:lazy? true}`, restore leaves run blocks cold after reading the engine
manifest, Merkle-LSM VersionManifest and the current-request metadata path.
History remains cold until explicitly requested. Point scans
choose a covering index from the query
pattern and use each run ref's first-component range to load only candidates;
older refs without range metadata remain correctness-safe by being retained.
The JVM regression resolves one entity from 13 EAVT runs with three run GETs.

The ClojureScript coordinator keeps provider I/O asynchronous while the engine
mechanism stays deterministic. Restore fetches bounded roots plus logarithmic
metadata paths; point scans batch-fetch range-selected run nodes and children. Cold
writes hydrate existing runs asynchronously, upload every immutable block, and
only then expose the new manifest through linearizable CAS. A 32-epoch
regression keeps both cold restore and replay of the oldest request below ten
block reads; a full history query deliberately pays for a prefix scan.

```sh
kbb -M:test
kbb -M:lint
npm run test:cljs
```
