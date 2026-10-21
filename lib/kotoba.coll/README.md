# kotoba-lang/coll

[![CI](https://github.com/kotoba-lang/coll/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/coll/actions/workflows/ci.yml)

**Layer 1 (data) of the kotoba foundational stdlib** — portable collection
helpers every kotoba actor otherwise re-rolls. Zero third-party runtime deps;
every namespace is `.cljc`, so it runs on JVM / SCI / ClojureScript / GraalVM /
kotoba-WASM. See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md)
for the layering decision.

This repo also covers `clojure.set` and `clojure.walk` — see
[`manifest/dependency-substitution.edn`](https://github.com/com-junkawasaki/root/blob/main/manifest/dependency-substitution.edn)
(`com-junkawasaki/root`) and
[`adr-2809061500-clojure-namespace-to-kotoba-stdlib`](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2809061500-clojure-namespace-to-kotoba-stdlib.edn)
for the program this is one piece of. Verified byte-for-byte identical
behavior on both JVM (`kbb -M:test`) and nbb (see **Verify** below).

## Current surface

`kotoba.lang.coll` — map/seq helpers complementary to `clojure.core`:

- `map-vals`, `map-keys` — transform a map's values / keys
- `filter-vals`, `filter-keys` — select map entries by predicate
- `deep-merge` — recursive map merge (maps nested, non-maps last-wins)
- `index-by` — build a lookup map from a key fn
- `assoc-some` — `assoc` only when the value is not `nil`

These are pure functions with no host capability — the data-layer foundation
that `langchain` / `langgraph` / `statechart` / `num` and the rest of the
vertical `*-clj` libs stand on.

### Set algebra — `clojure.set` coverage

Pure set/relation operations, no `#?()` branching (everything they're built
from — `merge`/`select-keys`/`disj`/`conj` — is already host-neutral):

- `set-union`, `set-intersection`, `set-difference` — variadic set algebra,
  mirroring `clojure.set/union|intersection|difference`
- `subset?`, `superset?` — `(subset? a b)` / `(superset? a b)`, mirroring
  `clojure.set/subset?|superset?`
- `select` — `(select pred xrel)`, the subset of relation `xrel` (a set of
  maps) for which `pred` is true
- `project` — `(project xrel ks)`, a relation with only the keys in `ks`
  kept on each map (mirrors `clojure.set/project`, including that
  projecting away a differentiating key collapses the now-duplicate maps,
  since the result is a set)
- `rename-keys` — `(rename-keys m kmap)`, renames the keys of **one** map
  per `kmap`; keys of `m` absent from `kmap` pass through unchanged
- `rename` — `(rename xrel kmap)`, applies `rename-keys` across every map
  in relation `xrel`
- `index` — `(index xrel ks)`, a map from the distinct values of `ks` (held
  as a map of just those keys) to the set of matching maps in `xrel`
- `join` — `(join xrel yrel)` natural join (on every key name the two
  relations share) or `(join xrel yrel km)` explicit-mapping join (`km` is
  `{xrel-key yrel-key}`); mirrors `clojure.set/join` exactly, including
  which side gets indexed (the smaller relation, by count — a performance
  detail that does not affect the result)

```clojure
(require '[kotoba.lang.coll :as coll])

(def people #{{:id 1 :name "Alice" :dept "eng"}
              {:id 2 :name "Bob"   :dept "eng"}
              {:id 3 :name "Cara"  :dept "sales"}})
(def depts  #{{:dept "eng"   :manager "Dana"}
              {:dept "sales" :manager "Erin"}})

(coll/select #(= "eng" (:dept %)) people)
;=> #{{:id 1 :name "Alice" :dept "eng"} {:id 2 :name "Bob" :dept "eng"}}

(coll/project people [:id :name])
;=> #{{:id 1 :name "Alice"} {:id 2 :name "Bob"} {:id 3 :name "Cara"}}

(coll/index people [:dept])
;=> {{:dept "eng"}   #{{:id 1 :name "Alice" :dept "eng"} {:id 2 :name "Bob" :dept "eng"}}
;    {:dept "sales"} #{{:id 3 :name "Cara" :dept "sales"}}}

(coll/join people depts)
;=> #{{:id 1 :name "Alice" :dept "eng"   :manager "Dana"}
;     {:id 2 :name "Bob"   :dept "eng"   :manager "Dana"}
;     {:id 3 :name "Cara"  :dept "sales" :manager "Erin"}}
```

`clojure.set/map-invert` is **not** part of this namespace's public surface
(it's used internally, unexported, only to implement 3-arg `join`) — it was
not in scope for this pass and is not claimed as covered.

### Tree walking — `clojure.walk` coverage: two intentional, permanent, parallel surfaces

⚠️ **`bounded-prewalk`/`bounded-postwalk` and `walk`/`prewalk`/`postwalk` are
NOT the same feature at two maturity levels. Do not "fix" one to match the
other.**

| | `bounded-prewalk` / `bounded-postwalk` | `walk` / `prewalk` / `postwalk` |
|---|---|---|
| Depth ceiling | **Yes** — explicit `max-depth` arg (default `default-max-walk-depth` = 1024); throws `ex-info` past it | **None** — no such argument exists in the signature |
| Matches | An intentional *divergence* from `clojure.walk` (a real safety property some callers depend on) | `clojure.walk/walk`, `/prewalk`, `/postwalk` exactly |
| Use when | The input could be adversarial/cyclical/unbounded and a controlled, catchable refusal is wanted instead of a raw stack overflow | The input's depth is trusted/known-bounded by the caller (e.g. a parsed document, an AST) and genuine `clojure.walk` semantics are needed |

The bounded pair exists because **~106 call sites in this workspace may
already depend on that ceiling as an actual safety property**
(`adr-2809061500-clojure-namespace-to-kotoba-stdlib`) — widening them to be
unbounded would silently remove a guarantee those callers added on purpose,
without them touching a line of their own code. The unbounded pair exists
because some callers genuinely need real `clojure.walk` semantics, which
this library must not silently approximate under a different name either.
**Both directions of "just make them consistent" are the wrong fix.** See
the `!!!! READ THIS BEFORE "FIXING" ... !!!!` comment directly above the
unbounded functions in `src/kotoba/lang/coll.cljk` for the same warning at
the point future edits are most likely to happen.

- `bounded-prewalk`, `bounded-postwalk` — depth/node-bounded, unchanged by
  this addition (see prior section of this README, or the source)
- `walk` — `(walk inner outer form)`, the general recursive dispatcher;
  mirrors `clojure.walk/walk`
- `prewalk` — `(prewalk f form)`, top-down (`f` runs on a node before its
  children); mirrors `clojure.walk/prewalk`
- `postwalk` — `(postwalk f form)`, bottom-up (`f` runs on a node's
  children before the node itself); mirrors `clojure.walk/postwalk`
- `prewalk-replace`, `postwalk-replace` — `(prewalk-replace replacements
  form)` / `(postwalk-replace replacements form)`, replace every node that
  is a key of `replacements`; mirror `clojure.walk/prewalk-replace|postwalk-replace`

```clojure
(coll/prewalk (fn [x] (if (number? x) (* x 2) x)) {:a 1 :b [2 3]})
;=> {:a 2 :b [4 6]}

(coll/prewalk-replace {:a :x} [:a :b :a])  ;=> [:x :b :x]
```

**One documented representational difference, not a behavior difference:**
a walked map-entry is reconstructed here as a plain 2-element vector rather
than the host's native map-entry object (`clojure.lang.MapEntry` on `:clj`,
a `MapEntry` type on `:cljs`). This is `=`-equal to the real thing in both
Clojure and ClojureScript — `(= (first {:a 1}) [:a 1])` is `true` on both
hosts, because a map entry is `Sequential` and compares by value against a
same-length vector — and a plain 2-element vector `conj`s onto a map
exactly like a real map-entry does. It is observable only via a type check
like `(instance? clojure.lang.MapEntry ...)`, which this library does not
attempt to reproduce.

### Persistent queue — `clojure.lang.PersistentQueue` coverage

- `empty-queue` — the host's empty queue itself (`clojure.lang.PersistentQueue/EMPTY`
  on the JVM, `cljs.core/PersistentQueue.EMPTY` on kbb / ClojureScript)
- `queue` — `(queue)` = `empty-queue`, `(queue coll)` = `(into empty-queue coll)`
- `queue?` — the host's instance check for its persistent queue

These exist so `.cljk` sources stop naming the JVM class: on the kbb engine
`clojure.lang.PersistentQueue/EMPTY` does not resolve at all (measured
2026-09-25), so sources carried `#?(:clj .. :cljs ..)` or failed to load
there. Target of `scripts/migrate-clojure-lang-persistentqueue-to-kotoba-coll.cljk`
(com-junkawasaki/root). The oracle test compares seq / peek / pop / count /
type / print / conj of `(queue s)` with the host-built queue for every seed,
and shows a vector traces differently (so the agreement is a measurement);
JVM (Clojure 1.12.1) agrees 7 / 7.

## Kotoba source authority

`src/kotoba/lang/bounded_coll.kotoba` is the sovereign, zero-capability kernel
for bounded string and keyword sets. It compiles to restricted browser JS and
typed browser Wasm. The CLJC namespace remains the general higher-order oracle
for map transforms, recursive merge, and indexing until the generic collection
and closure ABIs are sealed. See `migration/bounded-coll-v1.edn` for that
boundary.

## Install

```clojure
io.github.kotoba-lang/coll {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.coll :as coll])

(coll/map-vals inc {:a 1 :b 2})        ;=> {:a 2 :b 3}
(coll/deep-merge {:a {:x 1}} {:a {:y 2}}) ;=> {:a {:x 1 :y 2}}
(coll/index-by :id [{:id 1} {:id 2}])  ;=> {1 {:id 1} 2 {:id 2}}
```

## Verify

```sh
kbb -M:test                                  # JVM
kbb --backend sci --classpath src:test test/run_portable.cljk   # nbb / ClojureScript
```

Both run the **same** `.cljc` suite: `25 tests, 102 assertions, 0 failures`.
