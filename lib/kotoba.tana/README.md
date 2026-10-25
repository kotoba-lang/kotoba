# tana

**棚 — the shelf that says which box, so you open one.**

`tana` is the table plane between a set of columnar objects and a query: a
content-addressed root that carries what every object's footer said **and
where every column chunk is**, so a predicate becomes byte ranges without
opening anything.

```clojure
(require '[tana.member :as member] '[tana.table :as table] '[tana.plan :as plan])

;; Build once, at publish time: a footer, as data.
(def m (member/from-parquet-footer {:object cid :size n} (parquet.footer/parse bytes)))

(def root (table/table {:table "prices" :columns ["price"]
                        :bounds-authority :from-footers :members [m ...]}))

;; Query time: no object is opened.
(plan/plan root {:columns ["price"] :predicates [[:= "price" 104]]
                 :trust :from-footers})
;; => {:fetch [{:object "obj:mid" :range [51 98] :covers [...]}]
;;     :rounds 2 :bytes 47
;;     :chunks {:total 9 :pruned 8 :read 1 :undecidable 0}
;;     :pruning :enabled}
```

## What it is for

CARv2 answers *where a block is*. Parquet and Arrow answer *how a table is
encoded*. Neither answers the question a lake query actually asks:

> which of these thousand objects do I have to read?

Today that answer lives in a thousand footers, and reading them is the cost.
`net-kotobase/lake` measures four round trips for **one** 2.4 KB object —
leading magic, the 8-byte tail, the footer, then the column chunk — and three
of those four are metadata. Multiply by the objects a partitioned table has
and the metadata dominates the answer.

A table root is those footers, already read, in one addressable value.

## Measured

`npm run bench:rounds` — a table of N objects × 300 rows × 3 row groups with
disjoint ranges, `price = k`, both paths computing the answer and the answers
compared. Requests, because on a Worker or a browser a request is a round
trip and bytes are cheap by comparison.

| objects | baseline requests | sharded requests | baseline bytes | sharded bytes |
|---:|---:|---:|---:|---:|
| 1 | 4 | 3 | 1,108 | 1,789 |
| 10 | 31 | 3 | 3,637 | 7,971 |
| 50 | 151 | 3 | 14,877 | 23,325 |
| 200 | 601 | 3 | 57,027 | 24,143 |
| **1,000** | **3,001** | **3** | **281,827** | **26,891** |

Requests go flat. **Bytes do not, and the flat root is a trap:** it is
O(members × chunks × columns), about 700 bytes per member here, so at 1,000
objects a single root is 699 KB — worse than reading every footer. That is
what `tana.shard` is for, and the crossover is why it exists rather than
being an optimisation for later. Below ~30 objects the root costs more bytes
than it saves; the table above prints both numbers so the crossover is
visible rather than argued.

## Aggregates cost one request and read nothing

```clojure
(require '[tana.aggregate :as agg])
(agg/aggregate root {:agg :max :column "price" :trust :from-footers})
;; => {:value 999299 :from :statistics :read 0 :requests 1}
```

Parquet already answers `max` from a footer with `:read 0`, so the baseline
reads no column data either — what it cannot avoid is **opening every object
to reach those footers**. Measured, same bench:

| objects | baseline requests | tana requests |
|---:|---:|---:|
| 200 | 600 | **1** |
| 1,000 | 3,000 | **1** |

Every guard `columnar.aggregate` documents applies one level up, plus one
that only exists here: **`:location-only` trust refuses.** When pruning, a
wrong bound costs a read; in an aggregate the bound **is** the answer. A
refusal returns `{:from :refused :reason ...}` and never a value with a quiet
caveat — "could not" and "the answer is nothing" must not share a shape.

## Arrow is the second format, and it plugs in by reporting less

`member/from-arrow` takes what `arrow.ipc` returned, as data. **Arrow records
no column bounds**, so a root over Arrow gives location and prunes nothing:

```clojure
(plan/plan root {:columns ["price"] :predicates [[:= "price" 104]] :trust :from-footers})
;; {:chunks {:total 3 :pruned 0 :read 3 :undecidable 3}}
(agg/aggregate root {:agg :count :trust :from-footers})        ; {:value 9 :read 0}
(agg/aggregate root {:agg :max :column "price" :trust :from-footers})
;; {:from :refused :reason :bounds-not-recorded}
```

`count` still answers from metadata, because row counts are not bounds. `max`
is refused **by name** rather than invented. A mixed table prunes its Parquet
members and reads its Arrow ones — absence in one member does not disable
pruning for the others, and there is a test that requires exactly that.

This is the same question `columnar` asked itself when it acquired a second
format: a seam with a sample size of one is an untested claim.

## Three things it records, and dropping any one loses the saving

| recorded | without it |
|---|---|
| statistics (`:min` `:max` `:rows`) | nothing prunes; every object is opened |
| byte range `[start end)` | you know *which* object, not *which bytes* — the footer fetch comes back |
| `:type` `:codec` `:def-level` `:data-at` | the chunk's bytes are not decodable alone — the footer fetch comes back |

The third row is the one that is easy to miss. `tana.chunk-only-test` decodes
a planned range with `parquet.decode` directly and no footer at any point,
because a plan that still needs a footer saved one request and spent three.

## A fetched root must be signed before its bounds are believed

`table/sign` puts one signature over the canonical bytes, which covers the
statistics, the byte ranges and the member list transitively; for a sharded
table the top's signature covers every manifest, because the top names them
by digest.

**Why a root needs this when a pack's tip does not.**
`kotobase-storage-pack` leaves its tip unsigned and is right to: every block
leaving a pack is rehashed against the CID that was asked for, so a planted
tip costs a lookup that *fails*. Statistics have no such backstop — a bound
that is too narrow means the reader **never fetches the bytes that would
disprove it**, and the rows are simply absent, with no error and nothing to
re-hash.

So `plan` refuses to fold bounds from a root that is not marked verified:

| `:trust` | means |
|---|---|
| `:local` | I produced this root in this process |
| `:from-footers` / `:declared` | …and it carries a signature this caller verified |
| `:location-only` | use it to find bytes, prune nothing |

An unverified root reports `:pruning :disabled-unverified-root` and every
chunk is read — slower, and correct. Tampering with a bound, a byte range or
the member list all fail verification, and each is a test.

## `:bounds-authority` and `:trust` have no defaults

Statistics read out of an object at query time are as trustworthy as the
object. Statistics read out of a root are as trustworthy as **whoever wrote
the root**, and the failure is not symmetric:

- bounds **too wide** → an unnecessary read. A cost.
- bounds **too narrow** → rows are deleted from the answer. Silent, with no
  error, and indistinguishable from a table that simply had no such rows.

So a root declares `:from-footers` or `:declared`, a plan declares what it
will trust, and neither has a default. `:location-only` is the honest third
option: use the root to find bytes, prune nothing. `kotobase-storage` refuses
a backend that declares no ref profile for the same reason — **guessing is
silent, and an ignored precondition returns success.**

## The pruning rule is borrowed, never copied

`columnar.stats/skip?` decides, at both levels — chunks in `tana.plan`, and
manifests in `tana.shard`, which presents manifest bounds in the same shape.
A second copy of a pruning rule drifts in the worst direction: under-fetching
throws (loud), while pruning by a stale copy reads chunks the real planner
would have skipped and **still returns the correct answer**. The bug is
invisible in every result and visible only in the bill.

Two rules are inherited with it and are load-bearing here:

- **Absent statistics never permit a skip.** A chunk with no bounds is read,
  and counted as `:undecidable` — never as `:pruned`. A planner reporting
  `0 read` because it could not decide anything looks exactly like one that
  pruned everything.
- **Pruning decides what to read, never what matches.** Bounds may be wider
  than the data; every fetched chunk still has the predicate applied exactly.

`tana.shard` extends the first upward: a manifest reports bounds for a column
only when **every** chunk under it reported them. Deriving a bound from the
chunks that did report invents a claim the data never made.

## Sharding changes what a query costs, never what it fetches

That is a correctness claim, and cost arguments are where correctness quietly
goes: a two-level prune that rules out a manifest whose chunks the flat plan
would have read returns fewer rows and no error. So it is checked over
generated tables — overlapping ranges, unbounded chunks, 40 seeds × 4 shard
sizes × 4 predicates — rather than argued:

    plan(root)  ==  plan(merge(manifests the top could not rule out))

by the exact set of `(object, range)` pairs. A second test requires the shard
layer to actually rule things out (8 disjoint members, 1 manifest fetched),
because the invariant above would also hold for a layer that pruned nothing —
proving a tautology is the failure mode of an invariant test.

`aggregate-top` answers `count`, `min` and `max` from the top alone, and is
checked to agree with `aggregate` over the whole root on the same tables:
either both answer with the same value or **both refuse**. A top that
answered where the root refused would be folding bounds the data never
reported. It refuses `count-non-null` by name — the top does not carry null
counts, and answering with `count` would be wrong by exactly the nulls.

## Two levels, and why they are content-addressed

```text
top          one small object: per-manifest bounds
 └─ manifest per-member statistics and byte ranges
      └─ object   the Parquet / Arrow file itself
```

Iceberg's manifest-list/manifest split has this shape, from the same
pressure. What differs is that every level here is content-addressed, so a
reader pins one address and **cannot observe a half-published table** — there
is no catalog service holding a mutable pointer to the current snapshot, and
a snapshot names its members explicitly rather than being "whatever existed
at time T".

`tana.plan/select-manifests` is pure: it returns the addresses to fetch and
the caller fetches them. Keeping IO out is what lets the same planner run in
a Worker, a browser and a JVM test.

## What it is not

- **Not a file format.** Chunks stay Parquet or Arrow. Inventing a columnar
  encoding here would be re-inventing a small Parquet, badly.
- **Not a container.** Where an object lives — one object per CID, or a
  CARv2 pack with an offset — is `kotobase-storage`'s question. A range from
  this planner composes with a pack's range; it does not replace it.
- **Not a catalog.** `kotobase-lake` records what landed and who claimed
  what, on the datom plane, and answers that with Datalog. This answers one
  narrower question from one self-describing value, which is what a browser
  holding a bucket URL can use.
- **Not a query engine.** `columnar` decodes and filters. This hands it less
  to decode.

## Runtimes

`kbb -M:test` and `npm run test:nbb` — **39 tests, 1,105 assertions**,
both green, and green on a real fleet node (`test-tana-7394fea-murakumo-levi`,
receipt `76d8591167ea`). Portable `.cljc`, one runtime dependency.

The suite has been shown red on **eight** real defects and green again with
each reverted:

| broken | failures |
|---|---:|
| absent statistics permit a skip | 2 |
| `:trust` defaults instead of being required | 1 |
| a chunk range one byte too long | 1 |
| a predicate no longer disqualifies an aggregate fold | 1 |
| `:location-only` trust answers an aggregate anyway | 4 |
| the Arrow adapter invents wide-open bounds | 4 |
| manifest bounds derived from only the chunks that reported | **581** |
| the top answers `count-non-null` with `count` | 1 |

A gate that has only ever been green is a gate nobody has asked a question.

## The two runtimes now provably test the same versions

`npm run test:nbb` puts sibling **checkouts** on the classpath while
`deps.edn` pins **shas**, and those drift. Measured here on 2026-08-18: the
`columnar` checkout was 4 commits behind the pin and 13 days older, so "JVM
and nbb are both green" was a claim about two different columnars. The runner
now reads the pins out of `deps.edn`, compares them to the checkouts, and
**exits 2** — neither pass nor fail — with the table and the `west update`
line that fixes it. `TANA_ALLOW_PIN_DRIFT=1` runs anyway, for a deliberate
cross-version run.

Root ADR-2608180100 (git dep pin diamonds) is the same failure one level out,
and this closure has one: **three `columnar` shas are declared** — tana's
`5e165f0` (the tip), `org-apache-parquet`'s `d89813a`, `org-apache-arrow`'s
`16b336b`. `tools.deps` resolves them to one, which is why the JVM run is
green and why the duplication is invisible from inside. Named here because it
is upstream of this repo and not fixable from it.

## Known, and not papered over

- **The datom-plane manifest cannot produce a root on its own.**
  `kotobase.lake.table` records object, rows, partition values and per-column
  statistics — and **no byte ranges**. So a bridge from it still costs one
  footer read per member. Recorded here rather than filed as done: the two
  manifests overlap in statistics and differ in exactly the field that makes
  the round trip go away.
- **`aggregate-top` does not fall back to the manifests.** A column no
  manifest bounds is refused rather than resolved by fetching them; a caller
  that wants that fetches and calls `aggregate` on the merged root, which is
  one more request and its own decision.
- **Packs are orthogonal, deliberately.** ADR-2608160100 keeps columnar
  objects out of CARv2 packs (they are large objects with footer range reads,
  and wrapping a multi-MB column in a CAR frame doubles the indirection). A
  range from this planner composes with a pack's range; nothing here assumes
  either layout.
