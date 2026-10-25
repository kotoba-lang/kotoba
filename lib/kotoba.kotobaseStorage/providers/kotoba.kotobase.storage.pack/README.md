# kotobase-storage-pack

**An `IBlockStore` whose blocks live inside CARv2 packs on an object store.**

A decorator, not a transport. Give it any large-object store that implements
`IRangeRead` and it becomes a block store with the `:packed-blocks` profile —
the same S3, R2, B2 or in-memory provider serves both planes, and nothing new
has to be deployed.

```clojure
(require '[kotobase.storage.pack :as pack]
         '[kotobase.storage.core :as storage])

(def store (pack/pack-block-store objects (pack/memory-catalog)))

(storage/-put-blocks! store blocks)   ; one call seals exactly one pack
(storage/-get-blocks store cids)      ; one range request per coalesced run
(pack/stats store)                    ; {:requests n :bytes-fetched n :cache-hits n}
```

## The measurement it exists for

The cost of a read here is **requests, not bytes**. Production `kotobase.net`
spends 92 % of a query in hydration, and 97 % of hydration's *sequential* term
is the novelty cons chain — `{e, rest}`, width 1, and the next CID does not
exist until the previous block is decoded (root ADR-2608021000). Batching
cannot help: the caller genuinely cannot ask for the second block yet.

Walking a 100-link chain, one `-get-blocks` per link, exactly as a hydrate
loop must:

| 100-link chain, walked one link at a time | requests | bytes fetched |
|---|---|---|
| **all 100 written by ONE call** — no read-ahead | 100 | 8,730 |
| **all 100 written by ONE call** — 1 MiB window | **1** | 12,760 |
| **one commit per link** (what a transaction does) | **100** | — |

Identical numbers on JVM and nbb. The suite prints them on every run.

**Read the third row before believing the second.** The optimistic number is
about blocks that are *co-located*, and co-location is precisely what
packing buys. Production novelty is a cons chain where each transaction
appends one cell pointing at the previous, so under write-locality — one
commit, one pack — **each cell is in its own object and the walk costs one
request per link, exactly like block-per-object**. The window extends forward
inside one object; the predecessor is a different object entirely.

So the claim that survives is narrower than "packing fixes the cons chain",
which is how this was first motivated:

> **Packing buys commit-local reads.** Twelve blocks written by one commit —
> a transaction block, the prolly-tree pages it touched, its novelty cell —
> are one pack and therefore one request, with no read-ahead at all.

Flattening a *cross-commit* pointer chase needs something else: folding the
novelty (which removes the chain rather than co-locating it), or compaction
that repacks by read-locality. **Neither is designed here**, and the ADR
deliberately refuses to design compaction before measuring — this is the
measurement it was waiting for.

**Packing alone does not buy that.** A pack store that answers each call with
its own range request pays one round trip per link; the blocks merely happen
to be neighbours in one object. What buys it is that they *are* neighbours:
the first fetch takes a window rather than a frame, and the rest of the chain
is already in hand. The chain stays sequential in logic and stops being
sequential on the network.

That row of the table is a real test
(`without-a-window-the-chain-costs-one-request-per-link`), because the claim
is about the window and a suite that only showed the good number would be
evidence for packing in general, which is not what was measured.

**A window is a trade and both halves are reported.** 100 requests became 1 at
the cost of 46 % more bytes. `stats` returns `:requests` and `:bytes-fetched`
together for that reason — a round-trip claim that does not say what it
fetched is half a claim.

**And it reports a denominator.** `{:requests 0}` is what a perfectly
efficient read and a read that never happened both look like, and the second
is what a catalog lookup returning nothing produces. So `stats` also carries
`:blocks-served`, the derived `:requests-per-block`, and `:evidence`, which is
`:nothing-served` when no block was returned:

```clojure
{:requests 1 :bytes-fetched 12760 :cache-hits 99
 :blocks-served 100 :requests-per-block 1/100 :evidence :served}
```

A ratio with no denominator is `nil` rather than zero — there is no such
thing as a ratio of nothing.

## The honest limits

- **Packing helps only where the policy put the blocks together.** Two packs
  cost two requests however the caller batches
  (`separate-packs-cost-separate-requests`). This library does not decide
  what to pack: `-put-blocks!` seals one pack per call, which makes
  write-locality the caller's decision and one commit the natural unit.
- **A gap wider than `:max-gap-bytes` is not coalesced.** Dragging along the
  frames between two wanted ones is only free up to a point.
- **The window extends forward, never backward**, because the chain runs
  forward; extending backward would fetch what the caller has already passed.
- **Cached windows are never stale** — packs are immutable, so cache
  invalidation is not a problem this layer has.
- Every block is CID-verified on the way out. A flipped byte inside a
  well-formed frame is caught by nothing else, and the bytes came from a store
  the engine does not trust (`a-tampered-pack-fails-closed`).

## Where the catalog lives

Two questions, two owners:

| question | answered by |
|---|---|
| which **pack** holds this CID | the datom-plane catalog — it has to join with commits, tenants and lake objects |
| where **inside** that pack | the pack's own CARv2 `MultihashIndexSorted`, or the catalog's offsets |

The catalog arrives here as injected functions (`:lookup`, `:record!`, and
optionally `:record-pack!`), so this library never owns a store.
`memory-catalog` is the oracle and is enough for a single process.

`kotobase.storage.pack-catalog` is the datom-plane form: the attribute
vocabulary, the quads, and the queries — with nothing in it that talks to a
store, because composing over any datom engine is the same discipline as
composing over any object store.

```clojure
(pack-catalog/datom-catalog {:transact! ... :q ...})
```

A **subject is a content address**: there is no `:block/cid` attribute,
because the entity IS the CID. `bonsai` makes the same choice for git
objects, for the same reason — an entity id not derived from the bytes is a
second identity to keep in sync with the first.

The point of putting it here is that it joins. One query answers where a
block is *and* what the pack holding it is like:

```clojure
'{:find [?pack ?off ?size ?count]
  :in [?cid]
  :where [[?cid :block/pack ?pack]
          [?cid :block/file-offset ?off]
          [?pack :pack/size-bytes ?size]
          [?pack :pack/block-count ?count]]}
```

A catalog in its own store cannot answer that, and beyond this repository the
same join reaches the commit that wrote the pack and the tenant that owns it.
Join reach in kotobase is exactly one ref (ADR-260726), which is why the
catalog is not somewhere else.

`:block/pack` is indexed as a **reference**, so the reverse direction —
everything in a pack — is a direct lookup rather than a scan. That is what
compaction and a catalog rebuild both need.

The suite runs the whole read path against a real `kotoba-lang/datalog` db
rather than the atom, because a map agrees with anything and an argument
about joining cannot be checked by a test that never runs a query.

## Why it is not inside `kotobase-storage`

`kotobase-storage` is deliberately zero-dependency — it sits under every
provider including Worker builds. The CAR codec pulls `io-ipld` → `cbor` and
`multiformats` → `@noble/hashes`. That floor is worth keeping, so the
decorator lives one repo out.

## Two drivers, one plan

On a Worker every object read is a Promise, so a store that used the answer
directly could not run on the platform this was designed for.

| ns | fetch | runtime |
|---|---|---|
| `kotobase.storage.pack` | synchronous | JVM |
| `kotobase.storage.pack-async` | Promise-returning | Worker, R2 |
| `kotobase.storage.pack-plan` | — | the shared, pure half |

Coalescing, the read-ahead window, the held-window cache and frame
verification are all in `pack-plan`. Only the fetch differs, because two
copies of a coalescing rule is two coalescing rules.

The Promise path reports the same numbers as the synchronous one — 1 request
and 12,760 bytes for the 100-link chain — which is what you would expect
when it is the same code deciding.

`kotobase.storage.graphsync-replica` is the physical landing adapter for
GraphSync checkpoint replication. A successful receipt means that a block was
sealed into CARv2, catalogued, read back through the object/range plane with CID
verification, and only then signed by the replica. The signature covers the
block CID, replica identity, landing time, and pack CID. The integration test
qualifies two distinct replica identities backed by two independent CARv2
object stores; live multi-machine qualification remains a separate gate.

## End to end, on the deployment

`test/r2_run.cljk` packs real CARv2 bytes, PUTs them into a real R2Bucket
binding through [`kotobase-storage-s3`](https://github.com/kotoba-lang/kotobase-storage-s3),
and walks the 100-link chain back out **one link at a time**:

```
ok  - 100 links walked back out of R2
ok  - one ranged GET against the binding served all of them:
      {:requests 1, :bytes-fetched 12760, :cache-hits 99}
ok  - and the catalog rebuilds from the R2 object alone
```

Miniflare implements the R2 API, so the conversion this depends on — R2 takes
an offset and a length, the contract is half-open — is judged by something
that can disagree. The S3 adapter is a **test-only** dependency: this library
composes over any object store, and depending on one provider would make the
decorator a provider.

## The catalog is a projection, and that is checkable

A catalog that had to be consulted to locate the blocks it is stored in would
be circular. It is not, because a pack carries a CARv2 index of its own
contents: `rebuild-catalog!` recovers every entry — the same offsets the
writer recorded — from the pack object alone. Deleting the catalog costs a
scan, not the data.

## And it is checkable in the other direction too

`rebuild-catalog!` says what a pack holds. What it could not say, until the
drill went looking, is whether the walk that produced it *finished*.

Measured on 2026-08-17, with a three-pack chain and its middle object
deleted, `bootstrap-catalog!` returned the tip pack's three entries — which
is exactly what a healthy one-pack store returns. Delete the tip instead and
it returned `[]`, which is also what a zero budget returns, and also what an
empty store returns. Four states, two values, no way to tell them apart.

So the walk now reports how it ended, and there are five ways:

```clojure
(pack/bootstrap-report objects tip)
;; {:entries [...] :packs 3 :terminated :chain-start :complete? true}
;; {:entries [...] :packs 1 :terminated :missing-pack   :stopped-at "bafk…"}
;; {:entries [...] :packs 2 :terminated :unreadable-pack :problem {:error "car: uint64 in file exceeds…"}}
;; {:entries [...] :packs 4096 :terminated :budget-exhausted}
;; {:entries [...] :terminated :cycle}
```

`bootstrap-catalog!` is the entries-only form, and it now **throws** for the
three that are real failures rather than handing back a fragment shaped like
a catalog — the recovered entries ride along in the ex-data, so refusing to
return them as a catalog loses nothing. A budget the caller set still
returns normally: only the caller knows whether it meant to stop there.

A corrupt pack also no longer takes the walk down with it. It used to throw
from the middle, discarding every pack already recovered and naming none of
them; now the packs before it survive, and the report says which one failed
and what the codec said about it.

## The recovery drill

`test/kotobase/storage/pack_recovery_test.cljk` breaks the object store in
the four ways the design has to survive, on both drivers and against a real
R2 binding. Every one of them was quiet or misdirected before it was run:

| broken | before | now |
|---|---|---|
| pack missing mid-chain | 3 entries, no signal | `:terminated :missing-pack`, `:stopped-at` |
| pack missing on a read | `{:requests 1 :evidence :nothing-served}` | `:packs-missing 1`, `:evidence :degraded` |
| index will not parse | threw, losing 2 readable packs | `:unreadable-pack` + `:problem`, 2 packs kept |
| object ends early | frames omitted, counters healthy | `:frames-short 2`, `:evidence :degraded` |
| store ignores `Range` | `car: unsupported CID version {:version 13217}` | `:range-mismatch :range-ignored` |
| catalog points at another frame | that block returned under its own CID | `:frame-misplaced` |

The last two are the ones worth reading twice. A provider that answers HTTP
200 where 206 was asked for returns bytes that are perfectly good and simply
are not the bytes requested, so every offset computed from them is wrong —
and the error blamed the pack. The check is certain rather than clever: a
CARv2 data region starts at byte 51, so no frame is ever at offset 0, and a
response beginning with the pragma at a non-zero start *is* the whole object.

`:evidence :degraded` is the reading that had to exist next to `:served`. A
read that returned 99 of 100 blocks because one pack was truncated is not a
99-block success; its request count is not a measurement of anything.

**The line the drill draws**: bytes we did not get are omitted and counted;
bytes we did get that are wrong throw. That is why a tampered frame fails
closed while a truncated object degrades — the store does not trust the
object store, it trusts the hashes.

```bash
kbb -M:test        # 35 tests / 157 assertions, synchronous
npm run test:nbb       # the same cljc suite on nbb
npm run test:async     # the Promise driver, same numbers
npm run test:r2        # miniflare R2, end to end, including the drill
```

Design: root `90-docs/adr/2608160100-kotobase-physical-plane-ipld-carv2-pack.edn`.
Codec: [`kotoba-lang/io-ipld-car`](https://github.com/kotoba-lang/io-ipld-car).
