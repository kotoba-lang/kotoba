# arrangement

`kotoba-lang/arrangement` is the shared CLJC home for **persisting** an
in-memory 4-covering-index Arrangement (`:eavt`/`:aevt`/`:avet`/`:vaet`, named
for their sort orders): CID-addressed commit snapshotting via
`kotoba-lang/prolly-tree`, blinded/encrypted leaves, incremental commits,
partitioned roots, and cursor reads over the persisted trees. ClojureScript
callers can hand `cursor-async` directly to `arrangement.datalog/q-async`;
multi-clause Datalog then remains Promise-native across persisted tree reads
without hydrating the snapshot.

### Two vocabularies, on purpose

The in-memory keys were renamed from `:spo`/`:pso`/`:pos`/`:ocp` on
2026-08-20. **A snapshot's `index-roots` still names its four roots spo, pso,
pos, ocp** — those strings are hashed into the commit CID, so renaming them
would rename every snapshot of every graph, and a fleet with writers on both
sides would produce two CIDs for one graph and diverge without erroring.

Changing them is a `current-schema-version` bump with a migration attached,
not a side effect of an in-memory rename. The pairing lives in one place
(`arrangement.core/index-names`), and
`snapshot-bytes-are-unchanged-by-the-in-memory-rename` pins the commit CID of
a fixed fixture to the literal measured on `d1ef17e`, the commit before the
rename.

## The query layer lives in `kotoba-lang/datalog`

The indexes, the pattern router and the Datalog engine are **not defined
here**. They are [`kotoba-lang/datalog`](https://github.com/kotoba-lang/datalog)
— `datalog.index`, `datalog.query`, `datalog.core` — and this repo depends
on it.

`arrangement.query` and `arrangement.datalog` still exist and still work:
they are **compatibility shims** that delegate to `datalog.query` /
`datalog.core`, and `arrangement.core` re-exports `datalog.index`'s four
indexes with the `ipld.core/link?` default for `ref?` that this repo owns.
No consumer had to change. Removing the shims is a follow-up, once callers
require `datalog.*` directly.

Why: both repos carried the same query layer, and two copies drift. They
already did — arrangement kept developing while the extracted library sat
20 commits stale, which cost a full re-extraction to discover. A shim over
one copy cannot go stale; a second copy is what can.

One thing does **not** re-point mechanically: `kotobase-peer`'s scan-count
bench reaches into the private `#'arrangement.datalog/scan*` with
`with-redefs`. A private var cannot be re-exported, and aliasing it would be
worse than omitting it (the redef would rebind the alias while the engine
kept calling the original, silently counting zero). That bench must point at
`#'datalog.core/scan*`.

Formerly two repos: `quad-store` (this one, renamed — it stores triples
`{:s :p :o}`, not RDF quads; `Arrangement` names the actual structure
instead of overloading `quad`, and aligns this substrate with Datomic
terminology throughout, per `kotoba : kotobase = Clojure : Datomic`,
ADR-2607032500) and `kqe` (Kotoba Query Engine, merged in here — and since
extracted again, into `datalog`, along with the rest of the query layer).
See `90-docs/adr/2607010930-clj-wgsl-migration.md` Phase 6 for the original
landing, and ADR-2607050700 for the rename/merge.

A triple is `{:s subject :p predicate :o object}`. For this landing s/p/o
are opaque strings — dag-cbor round-trips strings exactly but not e.g.
Clojure keywords, so string-only keeps `commit!`'s snapshot honest about
what actually survives `cbor.core` encode/decode (except an `ipld.core/
Link` value, which *is* recognized and preserved end to end — see
`link->edn`/`edn->link`). General typed values are a follow-up.

## Use

```clojure
(require '[arrangement.core :as arr]
         '[arrangement.query :as q])

(def db (-> (arr/empty-db)
            (arr/assert-quad {:s "alice" :p "role" :o "admin"})
            (arr/assert-quad {:s "alice" :p "name" :o "Alice"})))

(arr/entity-attrs db "alice")              ;=> {"role" #{"admin"}, "name" #{"Alice"}}
(arr/by-predicate-value db "role" "admin") ;=> #{"alice"}

;; ref? defaults to ipld.core/link? -- a Link-valued object is reverse-indexed
;; automatically; pass a different predicate to opt out or widen it.
(def db2 (arr/assert-quad db {:s "bob" :p "knows" :o (ipld.core/link "bafy...")}))
(arr/refs-to db2 (ipld.core/link "bafy...")) ;=> {"knows" #{"bob"}}

;; content-addressed commit (same db+prev+schema-version -> same CID).
;; schema-version is required -- pass arr/current-schema-version if you
;; have no other version in mind, but state it.
(def store (atom {}))
(def cid (arr/commit! (fn [c b] (swap! store assoc c b)) db nil arr/current-schema-version))

;; pattern query over the hot db -- visible? is required (Query is a
;; first-class effect, ADR-2607050500); pass (constantly true) to see
;; everything, as an explicit choice.
(q/query db ["alice" nil nil] (constantly true))
;=> #{{:s "alice" :p "role" :o "admin"} {:s "alice" :p "name" :o "Alice"}}
```

## Scope

- 4-index hot (in-memory) Arrangement: full CRUD via `assert-quad`/
  `retract-quad`, point/scan lookups via `entity-attrs`/`by-predicate`/
  `by-predicate-value`/`refs-to`, pattern query via `arrangement.query/
  query`, and `arrangement.datalog/q`. **All of these are shims over
  `kotoba-lang/datalog`** — see the section above. The behaviour they
  document is that library's; what this repo still owns is the
  `ipld.core/link?` default for `ref?`.
- `commit!` snapshots each index to a `prolly-tree` and CID-addresses the
  commit as `{schema-version index-roots prev}` — a real commit chain,
  content-addressed (verified by test: same db+prev+schema-version always
  yields the same commit CID). Index roots and `prev` are **real tag-42
  IPLD links** (via [`kotoba-lang/ipld`](https://github.com/kotoba-lang/ipld);
  empty index → null), so a generic IPLD tool — or `ipld.core/links` —
  walks from a commit block to every index tree with no schema knowledge
  of this repo.
- `ipld.core/Link` values round-trip correctly through the persisted
  index (`link->edn`/`edn->link`), and are auto reverse-indexed via
  `ref?`'s default (`ipld.core/link?`).

**Not in this landing** (tracked follow-ups, not silently omitted):
- Cold (post-commit, prolly-tree-backed) query — the 4 index roots are
  persisted but nothing here reconstructs a hot index from them yet (see
  `kotoba-lang/kotobase-peer`'s `cold-datoms` for a filtered cold read
  that doesn't need one).
- General typed values beyond string + `ipld.core/Link`.

Query-language gaps are no longer this repo's to state — negation,
aggregation, rules and the rest landed long ago and their current status
(including what is still missing, like `not-join` and `pull`) is documented
where the code is, in [`kotoba-lang/datalog`](https://github.com/kotoba-lang/datalog).

## Test

```bash
kbb -M:test        # JVM
npm run test:cljs       # real shadow-cljs (not nbb -- see this org's own
                        # verification discipline, ADR-2607022600 add.3)
```

## License

MIT


### `or` / `or-join` branches may be conjunctions

A branch used to be a single clause, so it could not both BIND a variable and
CONSTRAIN it — which is exactly what a comparison inside a disjunction needs.
`(and ...)` is the branch form that fixes it, spelled the way Datomic spells
it:

```clojure
(or-join [?e] (and [?e :age ?a] [(> ?a 18)]) [?e :vip true])
```

The safety check follows the branch's own order: a predicate may rely on a
clause earlier in the SAME branch, and on nothing else.

### String predicates, and no regex

`query-fns` gains `starts-with?`, `ends-with?`, `includes?`, `lower-case` and
`upper-case`. **Regex is deliberately absent**: a caller-supplied pattern is a
ReDoS vector, and a query is caller-supplied data here — the same reasoning
that makes the registry a whitelist at all. These five are linear in their
inputs and cannot backtrack.

An unknown function is now refused by the STATIC safety pass rather than only
by `eval-fn-call`, which never runs when no binding reaches the clause. A typo
in a query used to succeed silently whenever the result set was empty.
