# merkle-lsm

A **write-optimised, log-structured merge store over content-addressed blocks.**

Datoms are batched into **sorted runs**; runs are IPLD DAG-CBOR blocks addressed
by CID; runs are described by a **range directory**; the directory and per-index
run set are named by a **manifest**, and a database is one CID pointing at that
manifest. Writing is an append of new runs plus a manifest swap. Compaction
merges runs in the background, and because every output is content-addressed,
re-running a compaction task is a *cache hit* rather than recomputation.

Portable `.cljc` — Clojure and ClojureScript, both verified in CI (see
[Portability](#portability)).

```clojure
io.github.kotoba-lang/merkle-lsm {:git/sha "..."}
```

## What is actually in here

Two namespaces, split mechanism vs. policy:

| ns | what it owns |
|---|---|
| `merkle-lsm.core` | the kernel: canonical keys, run/block encoding, range directories (flat and paged), manifests, publication & flush plans, visibility/MVCC row selection, and the compaction *primitives* (`compact-runs`, `compact-runs-partitioned`, `compact-run-readers-streaming`, `compact-chunk`/`compact-chunks`) |
| `merkle-lsm.compaction` | the *policy* above it: which runs to merge and when (`compaction-plan`, `scheduler-task`), L0 sub-levels, worker leases, reachability & mark-sweep GC, safe-epoch pinning |

**Everything is a value.** No namespace here performs I/O. Storage and head
mutation are returned as effect *descriptors* — `block-put`, `block-get`,
`head-read`, `head-cas`, `cache-get`, `cache-put` — which a host interprets
against whatever object store, KV, or cache it has. That is what makes the same
code run unmodified on a JVM and inside a Cloudflare Worker.

### Key ordering

Keys are framed and length-padded so that lexicographic byte order *is* logical
order: components are separated by an escaped delimiter (so `["a|b" "c"]` and
`["a" "b|c"]` cannot collide), integers are zero-padded to a fixed width with
negatives order-reversed, and the epoch is stored inverted so that **newer
versions sort first** within a logical key. Retention can therefore take the
first row per key and stop.

### Determinism

`build-run` is a pure function of its entries: the same rows in any input order
produce byte-identical output and the same CID. This is load-bearing rather than
cosmetic — it is what makes a retried compaction chunk deduplicate, and what
turns crash recovery into "which task CIDs already have outputs" instead of a
write-ahead log.

## Relationship to `prolly-tree`

[`prolly-tree`](https://github.com/kotoba-lang/prolly-tree) and `merkle-lsm` are
**two tiers of one storage system, not competing designs.** They make opposite
trades on purpose:

|  | `prolly-tree` | `merkle-lsm` |
|---|---|---|
| optimised for | **reads** — point lookup, prefix scan, structural diff | **writes** — batched append, background merge |
| shape | probabilistic B-tree, content-defined chunk boundaries | sorted runs in levels + range directory |
| a write costs | rewriting the path to the root | appending one run and swapping a manifest |
| a read costs | one descent | merging across the runs that overlap the key range |
| best at | a settled, widely-shared, incrementally-diffable snapshot | absorbing high-rate ingest without read-modify-write |

Both address blocks by CID and both are immutable, so a run compacted out of the
LSM can be published as a prolly-tree without changing the identity of anything —
LSM in front to absorb writes, prolly-tree behind for the cold, read-heavy,
diffable tier. Neither one subsumes the other; picking only one means paying that
one's worst case.

## Provenance

Extracted **additively** from
[`kotoba-lang/kotobase-peer`](https://github.com/kotoba-lang/kotobase-peer)
@ `780b2216a26664b20ce6dbbedabd36c9901c5914`, where these two files sat next to
an unrelated second product. `kotobase-peer` was **not modified** — it serves
live traffic and continues to carry its own copy. This repo gives the physical
store a name, a boundary, and a dependency footprint of exactly one thing.

The code is the upstream code. Changes were limited to namespace renames
(`kotobase-peer.merkle-lsm` → `merkle-lsm.core`, `kotobase-peer.compaction` →
`merkle-lsm.compaction`), docstrings, and one non-portable test assertion
(below). Design history lives in upstream ADR-2607201600 (M1/M4) and
ADR-2607244000 (chunked compaction).

**Why `compaction` came along.** It requires only `clojure.set`, `ipld.core`,
and this library, and it calls exactly two functions across the boundary
(`lsm/compact-runs-partitioned` and `lsm/linked-cids`). It is compaction *of*
this LSM and of nothing else — its vocabulary is runs, levels, manifests, and
epochs. Splitting it into a third repo would have produced a package whose only
possible consumer is this one.

**Why `datalog-materialization` did not.** It requires `kotobase-peer.core`,
`materialized-view`, and `statistics`, which pull the query engine
(`arrangement`, `prolly-tree`, `chain`) back in. It belongs to the read path and
stays upstream.

## Dependencies

Exactly one, on purpose:

```clojure
io.github.kotoba-lang/io-ipld {:git/sha "e08dc3b2ab705be292e388cd1ad136381544a041"}
```

`ipld.core` supplies DAG-CBOR encode/decode, CIDv1, and tag-42 links;
multiformats and CBOR arrive transitively. There is no query engine, no S3
client, and no cache implementation on this path — storage is a returned effect
descriptor, so the store does not get to pick your backend. If a change here
appears to need a second dependency, that is a signal the boundary is being
crossed rather than a missing coordinate.

## Portability

`.cljc` alone is a *claim*; CI is the check. Both jobs run on every push:

```bash
kbb -M:test     # JVM
kbb -M:lint     # clj-kondo, --fail-level error
npm run test:cljs   # real ClojureScript: shadow-cljs :node-test on Node
```

44 tests / 165 assertions, green on both runtimes.

The ClojureScript job resolves its `:source-paths` from `kbb -Spath`, so it
tests the **exact** git SHAs `deps.edn` pins rather than a hand-maintained,
driftable path list.

This immediately earned its keep. Upstream CI was **JVM-only**, and
`chunked-compaction-test` asserted byte equality with
`(= (seq (:bytes a)) (seq (:bytes b)))`. Under ClojureScript `:bytes` is a
`js/Uint8Array`, and `seq` over a JS typed array yields an `ES6IteratorSeq` —
which implements `ISeq` but **not** `IEquiv`, so `=` silently degrades to
reference identity and the assertion is false for byte-identical inputs. The
library was fine (the CID assertion on the line above passes, which proves the
bytes match); the *assertion* was not portable. Fixed to `vec`, which is what
`core-test` had always used for the same property.

## Known gaps

Real, and confirmed against the code in this repo rather than asserted:

- **The cache effects have no interpreter.** `cache-get`/`cache-put` construct
  `{:effect/type :cache/get ...}` descriptors and **nothing in this library ever
  calls them** (`grep` finds only the two definitions). Blocks are re-fetched and
  re-decoded on every access unless a host supplies caching on its own. Upstream
  has since added a `block-cache` dependency to fill this in; that host-side
  implementation is deliberately *not* vendored here.
- **No bloom filters and no prefetch.** Zero occurrences of either. Blocks *do*
  carry `logical-min`/`logical-max`, which gives a coarse per-block key-range
  index — enough for chunked compaction to skip whole blocks without fetching
  them — but there is no negative-lookup filter, so a point query that misses
  still pays to open candidate blocks.
- **Safe-epoch MVCC pinning is computed but not wired.** `safe-epoch-pin` and
  `minimum-safe-epoch` correctly fold legal holds, in-flight reader epochs, and
  replica lag into a retention floor — but upstream's production worker calls
  only `scheduler-task`, `bounded-batches`, `lease-node`, `lease-active?`, and
  `validate-lease-node`. Nothing feeds live reader epochs in. Treat the safe
  epoch as a parameter *you* must supply correctly; the machinery to derive it
  from actual readers is present but unconnected.
- **Streaming compaction is bounded only on the chunked path.**
  `compact-run-readers-streaming` (Stage A) streams outputs but, as its own
  docstring admits, "still holds each opened run's decoded rows until that run is
  exhausted" — so a k-way merge over overlapping ranges co-resides O(dataset),
  measured upstream at 6.93 GB for 1M datoms. `compact-chunk`/`compact-chunks`
  (Stage B) is the bounded one: one block at a time per reader, O(k × block-rows),
  resumable from a single-string cursor. **Use the chunk API for anything large**;
  Stage A remains only for callers that already know their fan-in is small.
- **GC is mark-sweep over a caller-supplied CID set.** `gc-candidates` takes
  `all-stored-cids` as an argument — enumerating the object store is the host's
  problem, and there is no incremental or generational path.

## License

See [LICENSE](LICENSE).
