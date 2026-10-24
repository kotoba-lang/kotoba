# block-cache

**A CID-keyed block cache, and the one property that makes it safe: there is
no invalidation, by construction.** Zero dependencies, pure `.cljc`.

A content-addressed block cannot change under its key. So this cache never
goes stale, never needs a TTL, and can be shared between readers, requests and
nodes without a coherence protocol. Every other cache in a database exists in
tension with writes; this one does not.

## Why

kotobase did not have one. Measured 2026-08-01 on a recursive Datalog query
(`reaches` over a chain, cursor source over a block store):

| chain length | block reads | with the repeats cached |
|---|---|---|
| 20 | 23 | **2** |
| 40 | 43 | **2** |
| 80 | 83 | **2** |

The fixpoint issued 22 scans of the *same* pattern. The saving grows with the
data, which is the shape of a missing cache rather than a slow one.

RisingWave's Hummock gets its speed the same way — its own docs put the hybrid
block/metadata cache first among the reasons — but it has to synthesize a cache
key. Content-addressed blocks **are** their keys, so a hit here is
content-verified for free, globally unique, and safe to share across colos.

## Use

```clojure
(require '[block.cache :as bc])

(def cache (bc/memory (* 32 1024 1024)))          ; bounded by BYTES
(def get-fn (bc/wrap-get-fn cache raw-get-fn
                            {:verify! verify-cid!}))
```

`wrap-get-fn` turns any `(fn [cid] bytes)` into a cached one, so `arrangement`,
`prolly-tree`, `chain` and `kotobase-peer` all benefit without changing a line.

`:verify!` runs on a **miss only**. That is the second saving and it is not the
small one: re-hashing a block on every read proves something that cannot have
changed.

| | |
|---|---|
| `memory` | in-process, bounded by **bytes** (not entries — blocks range 16–128 KB, so "1000 entries" is 16 MB or 128 MB) |
| `tiered` | fastest first, promote on a hit from below. A tier is itself a cache, so they nest |
| `null` | caches nothing, so caching is turned off by configuration rather than by an `if` |
| `segmented` | **the metadata cache.** Two byte-bounded segments split on entry SIZE, with independent budgets |
| `wrap-async-get-fn` / `async-tiered` | the Promise-based half, for a local tier |
| `block.cache.worker/cache-api` | Cloudflare Workers Cache API tier — the platform's local-SSD equivalent |
| `stats` / `hit-rate` / `segment-hit-rates` | the number that decides whether any of this helps is the MISS rate |

### Why `segmented` exists

Hummock keeps its metadata cache and its block cache separate, and the reason
is eviction, not bookkeeping: metadata is small and hot, data blocks are large
and cold, and **one wide scan through a shared LRU evicts every hot metadata
entry** to hold blocks it will never read again. LRU is a recency heuristic and
a wide scan is exactly the access pattern that defeats it.

kotobase cannot make that split at the obvious place — `get-fn` is
`(fn [cid] bytes)` and a CID does not say what it addresses. It does not have
to: the two kinds are separated by **size**. Snapshot nodes are small,
`kotobase-peer.block-sizing` keeps data blocks at 16–128 KB. Splitting on bytes
recovers the protection without asking the caller to know anything. There is a
test asserting that a shared cache of the same total size loses the metadata
and a segmented one does not.

A missing block is **not** cached: absence is the one thing about a CID that can
change later, when the block arrives.

## Run

```
kbb -M:test
```
