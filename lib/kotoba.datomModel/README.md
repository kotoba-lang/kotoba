# datom-model

The Datomic-shaped model layer in portable `.cljc`: `transact`, schema-as-datoms,
`datoms`, `q`/`query`, `pull`, `entity`, `entid`/`ident` — over a
[`datalog.index`](https://github.com/kotoba-lang/datalog) db value.

Extracted from [`kotoba-lang/kotobase-peer`](https://github.com/kotoba-lang/kotobase-peer)'s
`kotobase-peer.core` (@ `ea4a8e8b0f757a5f15a28cc3a0ac42406b65ffde`), whose 2,862-line
`core.cljc` fused a pure Datomic model with a content-addressed persistence engine.
Only the model half is here: `empty-db` through `ident`, i.e. everything above that
file's own `;; ── persistence: content-addressed, chained, verifiable ──` divider
(line 890 at that commit).

### Staying in sync with `kotobase-peer`

The extraction base was originally `780b2216a26664b20ce6dbbedabd36c9901c5914` and was
re-synced to `ea4a8e8b` on 2026-08-02. Between those two commits `core.cljc` changed by
+121/−25 lines, but **the model half moved in exactly one place**: `datalog-query-plan`
now estimates a clause with `datalog.query/cardinality` instead of
`(count (datalog.query/query ...))`, and hands the resulting estimates to the executor as
`:clause-cardinality` (ADR-2608021000 §6-4-1). Everything else in that range was the
persistence half — the novelty cons-chain growing batched 16-entry segments — which by
construction is not in this repo.

That is the check to run when re-syncing: diff peer's `core.cljc` truncated at its own
divider, at the old and new base, and port only what that shows.

This is an **additive** extraction. `kotobase-peer` is untouched and still serves
production traffic through its own copy; re-pointing it at this library is a separate
step.

## Namespaces

| ns | what it is | requires |
| --- | --- | --- |
| `datom-model.core` | the model: transact / schema / datoms / q / query / pull / entity / entid / ident | `datalog.index`, `datalog.query`, `datalog.core`, `datom.core` |
| `datom-model.statistics` | scoped clause cardinalities + greedy join ordering, for `datalog-query-plan` | nothing (`clojure.set`) |

```clojure
(require '[datom-model.core :as m])

(defn ref? [x] false)                     ; this db has no reference values
(def db (m/transact (m/empty-db)
                    [{:s "alice" :p "role" :o "admin"}
                     [:db/add "alice" "name" "Alice"]
                     ["bob" "role" "user"]]
                    ref?))

(m/query db {:find '[?name]
             :where '[[?s "role" "admin"] [?s "name" ?name]]}
         (constantly true))
;; => #{["Alice"]}

(m/datoms db pr-str (constantly true))
;; => [{:e "alice" :a "role" :v_edn "\"admin\"" :added true} ...]
```

## What is deliberately NOT here

Everything from `snapshot!` onward in the source file, because none of it is the
model:

- **persistence** — `snapshot!`, `commit!`, `commit-with-report!`, the novelty
  cons-chain (`push-novelty!`, `take-oldest-novelty`, the tx-block put/read pair)
- **write ACID** — `commit-serialized!` and its batch/report/effective variants,
  CAS retries
- **chain** — `chain`, `head`, `latest-snapshot-cid`, `verify-chain`
- **fold / compaction** — `fold!`, `should-fold?`, `novelty-size`, materialized views
- **hydration** — `hydrate-db`, `hydrate-db-cached`, `hydrate-chain`,
  `hydrate-transaction-slice`
- **cold reads** — `cold-datoms` and its prolly-tree prefix machinery
- **time travel** — `as-of`, `since`, `history`, `history-datoms`, `tx-range`
- **`hot-datoms`** and its two private helpers `retraction-filters` /
  `remove-retracted`. These two sit *above* line 870 in the source file but every
  call site is below it — they are snapshot-vs-novelty cancellation, which is
  persistence. Their exclusion is why `arrangement.core/edn->link` does not appear
  anywhere in this repo: that was its only use in the model half.
- **`verified-node`** (lines 57–64), duplicated CID verification now subsumed by
  `kotobase-storage`'s `kotobase.storage.verify` decorator.

Consequently this library never puts, gets, hashes, addresses, chains, or encrypts
anything. Its whole transitive runtime closure is `datalog` (→ `datom-source`) and
`datom` (zero deps).

## The two injected parameters

`kotobase-peer`'s model half touched IPLD in exactly two places. Both are now caller
parameters, and both are **required** — there is no permissive-default arity.

### 1. `ref?`

The predicate deciding whether a value is a *reference*: whether it survives quad
coercion verbatim instead of being stringified, and whether it gets a
reverse-reference (`:vaet`) index entry. `kotobase-peer` defaulted it to
`ipld.core/link?`.

[`datalog.index`](https://github.com/kotoba-lang/datalog) already made `ref?` required
for exactly this reason (see its README's "The one cut"), and this follows. A wrong
default is not a compile error, it is a silently empty or silently over-full reverse
index.

One improvement over the source while doing this: `transact-with-schema`'s
`:db/valueType "ref"` check used a hardcoded `ipld/link?` *independently* of the
`ref?` the same call passed to `assert-quad`. Here both use the caller's one
predicate, so "declared a ref" and "indexed as a ref" cannot drift apart.

### 2. `render-value` — and why not `io-ipld`

`datoms` returns `{:e :a :v_edn :added}` rows, where `:v_edn` is a wire string.
`kotobase-peer` produced it with a private `v->edn` hardcoded to
`#(pr-str (arrangement.core/link->edn %))` — a Link renders as `["ipld/link" cid]`,
anything else `pr-str`s.

**The choice was: inject the encoder, or depend on `io-ipld`
(@ `e08dc3b2ab705be292e388cd1ad136381544a041`). I injected it.** Both options are
layering-legal — `io-ipld` is L0, so an L5→L0 edge points downward — so this is a
judgement about dependency weight, not about legality.

**Why inject.** `link->edn`/`edn->link` are four lines that call `ipld/link?`,
`ipld/link-cid`, and `ipld/link`. Pulling `io-ipld` in for them also pulls
`io-multiformats` and `org-ietf-cbor`: a CIDv1 assembler, a multihash implementation,
and a canonical CBOR codec — a full serialization stack, imposed on every consumer of
a library that does not serialize anything. That would directly undo what the previous
extraction step bought. The model also never *uses* a link: it never constructs,
dereferences, or structurally compares one. It only ever needs to know (a) is this a
reference and (b) how do I stringify it — both of which are caller knowledge, and (a)
is already injected.

**Why required rather than defaulted to `pr-str`.** `pr-str` is correct for every
value that is not a reference, which makes it a tempting default — but for a caller
who does hold references and forgets, `pr-str` of an `ipld.core/Link` emits
`#object[ipld.core.Link 0x...]` into `:v_edn`. That is silent wire corruption. An
arity error is strictly better.

**The cost, stated plainly.** `datoms` grows a parameter — `(datoms db render-value
visible?)` / `(datoms db opts render-value visible?)` — and every caller must supply
it. When `kotobase-peer` re-points at this library it will pass
`#(pr-str (arrangement.core/link->edn %))` and keep byte-identical output; the
`wire-encoding-matches-kotobase-peers-byte-for-byte` test pins that string shape here,
against a local stand-in record rather than a real `Link`. If those bytes ever need to
change, they now change in two repos instead of one. That is the trade.

`visible?` remains required everywhere it appears, unchanged from the source
(ADR-2607050500).

## Known gaps

Observed while porting; all but the last are inherited from `kotobase-peer` verbatim
and are listed because they are easy to misread as guarantees.

1. **Values are stringified on the way in.** `->quad-value` passes `ref?` values
   through and calls `str` on everything else. A `:db/valueType :long` / `:uuid` /
   `:instant` / `:tuple` is validated against the caller's *original* value and then
   stored as its `str` — schema checks the type at the API boundary, it does not
   preserve it. `(pull db "bob")` for an attribute transacted as `42` returns
   `#{"42"}`. (ADR-2607023200 §6-5 follow-up.)
2. **`transact-with-schema` does not accept retraction forms.** It routes through
   `raw-triple`, which knows `{:s :p :o}` maps, `[:db/add e a v]`, and bare `[e a v]`
   only — `[:db/retract …]` and `[:db/retractEntity e]` throw
   `unrecognized tx-data item` there, though plain `transact` handles both. Schema
   enforcement and retraction are, today, mutually exclusive.
3. **`transact-with-schema` returns a bare db, not effective deltas.** It does not go
   through `transact-effective`, so there is no schema-enforcing path that also yields
   `:effective-deltas` for statistics.
4. **Cardinality and uniqueness are enforced only by `transact-with-schema`.** Plain
   `transact` is cardinality-agnostic and ignores `:db/unique` entirely, even for
   attributes with schema installed.
5. **`:db/ident` uniqueness is unenforced.** If two entities assert the same ident,
   which one `entid` returns is unspecified (`q` returns a set).
6. **`datoms`' unfiltered branches reach into the raw index maps** (`(:eavt db)`,
   `(:aevt db)`, `(:vaet db)`) instead of going through `datalog.index` accessors,
   because `datalog.index` exposes no whole-index scan. The index representation
   leaks into this layer. Kept verbatim so behavior is identical; closing it needs an
   accessor added upstream.

   The 2026-08-20 rename of those keys (they were `:spo`/`:pso`/`:ocp`) is what
   this leak costs: an accessor would have made it a no-op here. It was not
   silent, though — bumping the `datalog` pin without re-pointing these three
   lines turns 69 green tests into 23 failures and 8 errors, because
   `datalog.query` now refuses a db carrying the old keys instead of scanning a
   `nil` index and reporting zero rows.
7. **`datalog-query-plan` costs a scan per clause when no statistics are supplied** —
   the `:visible-scan` fallback runs a real `datalog.query/query` for each clause just
   to count it. Fine for small graphs, not free.
8. **`entity` is a plain map, not lazy.** Identical to `pull`'s 2-arg form;
   `entity-attr` is the explicit navigation step. The source explains why (nbb/SCI
   cannot dispatch a custom `deftype`'s implementation of a built-in protocol), and
   that constraint still holds.
9. **Read shapes are asymmetric.** `datoms` returns wire-encoded `:v_edn` strings;
   `q`, `query`, `pull`, and `entity` return the raw stored values (so a reference
   comes back as whatever the caller put in). Inherited.
10. **`apply-quad` is now public.** It was private in `kotobase-peer.core`, where all
    five call sites were persistence-side (`hydrate-db`, `since`, `history`,
    `hot-datoms`, `fold!`). It is a model primitive with persistence-side callers, so
    it is exported here rather than dropped — a re-pointed `kotobase-peer` can delete
    its private copy.

## Tests

Every model-half test from `kotobase-peer.core-test` is ported, plus new coverage for
the two injections and for `apply-quad`. The persistence-half tests — and the entire
AES-256-GCM / HMAC-SHA256 test-crypto preamble they need — are not, because none of
that code is here.

```bash
kbb -M:test     # JVM
kbb -M:lint     # clj-kondo
npm install && npm run test:cljs   # real ClojureScript (shadow-cljs :node-test)
```

The ClojureScript job resolves its `:source-paths` from `kbb -Spath`, so it
compiles against the exact `deps.edn` git SHAs the JVM job uses — never a
hand-duplicated path list. Both runtimes run the same suite.

## License

MIT
