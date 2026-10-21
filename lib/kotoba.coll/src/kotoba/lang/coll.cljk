(ns kotoba.lang.coll
  "Portable collection helpers for the kotoba foundational stdlib — the map/seq
  ops every actor otherwise re-rolls. Layer 1 (data): pure functions, no host
  capability, no third-party deps. Runs on JVM / SCI / ClojureScript / GraalVM /
  kotoba-WASM.

  These complement `clojure.core`: `clojure.core` already has `map`/`filter`/
  `reduce`/`merge`/`group-by`; this namespace adds the small map-shaping and
  recursive-merge helpers that are not in `clojure.core` but that every kotoba
  vertical lib re-implements."
  {:kotoba/export '[assoc-some difference intersection map-invert union bounded-postwalk bounded-prewalk deep-merge default-max-walk-depth empty-queue filter-keys filter-vals index index-by index-of join keywordize-keys map-keys map-vals postwalk postwalk-replace prewalk prewalk-replace project queue queue? rename rename-keys select set-difference set-intersection set-union stringify-keys subset? superset? walk]}
  (:refer-clojure :exclude [merge]))

(defn map-vals
  "Return a map with the same keys as `m` and `f` applied to each value.
  Preserves the key's identity (objects/keywords/strings)."
  [f m]
  (reduce-kv (fn [out k v] (assoc out k (f v))) {} m))

(defn map-keys
  "Return a map with `f` applied to each key and the same values. If `f`
  produces duplicate keys, later entries win."
  [f m]
  (reduce-kv (fn [out k v] (assoc out (f k) v)) {} m))

(defn filter-vals
  "Return a map containing only the entries of `m` whose value satisfies
  `pred`."
  [pred m]
  (reduce-kv (fn [out k v]
               (if (pred v) (assoc out k v) out))
             {} m))

(defn filter-keys
  "Return a map containing only the entries of `m` whose key satisfies `pred`."
  [pred m]
  (reduce-kv (fn [out k v]
               (if (pred k) (assoc out k v) out))
             {} m))

(defn deep-merge
  "Recursively merge maps: when both values at a key are maps, they are merged
  recursively; otherwise the rightmost value wins. Scalars and collections that
  are not both maps are replaced (not concatenated) — this is merge semantics,
  not conj semantics."
  ([a] a)
  ([a b]
   (if (and (map? a) (map? b))
     (merge-with deep-merge a b)
     b))
  ([a b & more]
   (reduce deep-merge (deep-merge a b) more)))

(defn index-by
  "Return a map from `(keyfn item)` to `item` for each `item` in `coll`. Later
  items win on key collision. Nil keys are dropped (a nil key would collapse
  entries)."
  [keyfn coll]
  (reduce (fn [out item]
            (let [k (keyfn item)]
              (if (nil? k) out (assoc out k item))))
          {} coll))

(defn index-of
  "The index of the first element of the sequential `coll` equal (`=`) to `x`,
  or -1 when none is -- what `java.util.List#indexOf` answers for a Clojure
  vector, list or seq on the JVM (APersistentVector / ASeq compare with
  `Util.equiv`, which is `=`), and what ClojureScript's `(.indexOf v x)`
  answers for its vectors and lists. `x` may be nil (the first nil's index).

  One deliberate difference: a nil `coll` answers -1 where
  `(.indexOf ^java.util.List nil x)` throws NullPointerException.

  For a string use kotoba.lang.text/index-of; a map or set is not sequential
  and has no index."
  [coll x]
  (loop [s (seq coll) i 0]
    (cond (nil? s) -1
          (= (first s) x) i
          :else (recur (next s) (inc i)))))

(defn assoc-some
  "Assoc `k` to `v` in `m` only when `v` is not nil. Useful for building option
  maps without (when ...) scaffolding at every call site."
  ([m k v]
   (if (nil? v) m (assoc m k v)))
  ([m k v & kvs]
   (let [m (assoc-some m k v)]
     (if (seq kvs)
       (recur m (first kvs) (second kvs) (nnext kvs))
       m))))

;; -- Set algebra ------------------------------------------------------------
;; Replaces clojure.set/union|intersection|difference in the frontier
;; (90-docs/migration/kotoba-cljc-common-lib-frontier.edn, :collection-walk-set).
;; General, unbounded-arity oracle form. The sovereign .kotoba kernel keeps
;; only the bounded 32-item typed-set primitives -- general set algebra stays
;; here because restricted-JS KIR rejects it (measured 2026-08-02, see
;; migration/bounded-coll-v1.edn :retained :set-algebra).

(defn set-union
  "Union of zero or more sets. Mirrors clojure.set/union without the
  clojure.set dependency."
  ([] #{})
  ([s1] (or s1 #{}))
  ([s1 s2] (into (or s1 #{}) (or s2 #{})))
  ([s1 s2 & sets] (reduce set-union (set-union s1 s2) sets)))

(defn set-intersection
  "Intersection of one or more sets. Mirrors clojure.set/intersection."
  ([s1] s1)
  ([s1 s2] (into (empty s1) (filter #(contains? s2 %)) s1))
  ([s1 s2 & sets] (reduce set-intersection (set-intersection s1 s2) sets)))

(defn set-difference
  "Elements of s1 not present in any of the other sets. Mirrors
  clojure.set/difference."
  ([s1] s1)
  ([s1 s2] (into (empty s1) (remove #(contains? s2 %)) s1))
  ([s1 s2 & sets] (reduce set-difference (set-difference s1 s2) sets)))

;; -- clojure.set's own names: union / intersection / difference / map-invert --
;;
;; set-union / set-intersection / set-difference above are NOT clojure.set:
;; they always build on s1 (into (or s1 #{}) ...), so `(set-union nil)` is #{}
;; where clojure.set says nil, `(set-union [1] [2 3])` is [1 2 3] where
;; clojure.set says [2 3 1], and a sorted or smaller-but-typed second set is
;; not the result's type. Those names keep that meaning (callers rely on it).
;;
;; Portions below (bubble-max-key, union, intersection, difference,
;; map-invert) are transcribed from ClojureScript's clojure/set.cljs:
;;   Copyright (c) Rich Hickey. All rights reserved. Eclipse Public License
;;   1.0 (http://opensource.org/licenses/eclipse-1.0.php); that license, not
;;   this repository's Apache-2.0, governs these five definitions.
;;
;; The four below are clojure.set -- transcribed from ClojureScript's
;; clojure/set.cljs (1.12.42), the implementation `clojure.set` resolves to on
;; the kbb engine, so a call site moved from clojure.set to this namespace
;; gets the same value, the same collection type, the same order and the same
;; nil handling (scripts/migrate-clojure-set-to-kotoba-coll.cljk in
;; com-junkawasaki/root rewrites only the namespace token). Semantics are
;; pinned against clojure.set in test/kotoba/lang/coll_test.cljk.

(defn- bubble-max-key
  "Move a maximal element of coll according to fn k (which returns a
  number) to the front of coll."
  [k coll]
  (let [max (apply max-key k coll)]
    (cons max (remove #(identical? max %) coll))))

(defn union
  "Return a set that is the union of the input sets. clojure.set/union."
  ([] #{})
  ([s1] s1)
  ([s1 s2]
   (if (< (count s1) (count s2))
     (reduce conj s2 s1)
     (reduce conj s1 s2)))
  ([s1 s2 & sets]
   (let [bubbled-sets (bubble-max-key count (conj sets s2 s1))]
     (reduce into (first bubbled-sets) (rest bubbled-sets)))))

(defn intersection
  "Return a set that is the intersection of the input sets.
  clojure.set/intersection."
  ([s1] s1)
  ([s1 s2]
   (if (< (count s2) (count s1))
     (recur s2 s1)
     (reduce (fn [result item]
               (if (contains? s2 item)
                 result
                 (disj result item)))
             s1 s1)))
  ([s1 s2 & sets]
   (let [bubbled-sets (bubble-max-key #(- (count %)) (conj sets s2 s1))]
     (reduce intersection (first bubbled-sets) (rest bubbled-sets)))))

(defn difference
  "Return a set that is the first set without elements of the remaining
  sets. clojure.set/difference."
  ([s1] s1)
  ([s1 s2]
   (if (< (count s1) (count s2))
     (reduce (fn [result item]
               (if (contains? s2 item)
                 (disj result item)
                 result))
             s1 s1)
     (reduce disj s1 s2)))
  ([s1 s2 & sets]
   (reduce difference s1 (conj sets s2))))

(defn map-invert
  "Returns the map with the vals mapped to the keys. clojure.set/map-invert."
  [m]
  (persistent!
   (reduce-kv (fn [m k v] (assoc! m v k))
              (transient {})
              m)))

;; -- Relational algebra (clojure.set gap-fill) -------------------------------
;; Completes clojure.set coverage in this namespace: set-union/intersection/
;; difference above already replace the pure set-algebra third of
;; clojure.set; these functions replace the "relation" (a set of maps) third
;; -- subset?/superset?, plus the select/project/rename/index/join family
;; that clojure.set itself documents as operating on relations, not on sets
;; of scalars. Semantics below are transcribed from clojure.set's own
;; documented behavior, not reinvented -- each docstring names the upstream
;; function it mirrors so a diff against real clojure.set is easy to check by
;; hand. Pure data-structure operations; no #?() branching needed here (the
;; `merge`/`select-keys`/`disj`/`conj` primitives they're built from are
;; already host-neutral clojure.core).

(defn subset?
  "True if every element of set1 is also in set2. Mirrors
  clojure.set/subset?. An empty set1 is a subset of any set2, including
  another empty set."
  [set1 set2]
  (and (<= (count set1) (count set2))
       (every? #(contains? set2 %) set1)))

(defn superset?
  "True if every element of set2 is also in set1. Mirrors
  clojure.set/superset?."
  [set1 set2]
  (and (>= (count set1) (count set2))
       (every? #(contains? set1 %) set2)))

(defn select
  "Return the subset of relation `xrel` (a set of maps) for which `pred` is
  true. Mirrors clojure.set/select. `xrel` need not be a relation -- select
  works over any set -- but is named `xrel` to match clojure.set's own
  parameter name, since that is its primary use."
  [pred xrel]
  (reduce (fn [s k] (if (pred k) s (disj s k))) xrel xrel))

(defn project
  "Return a relation (set of maps) built from `xrel` by keeping only the
  keys in `ks` of each map. Mirrors clojure.set/project. Maps that become
  identical after projecting (because the dropped keys were the only
  difference) collapse into one entry, since the result is a set."
  [xrel ks]
  (set (map #(select-keys % ks) xrel)))

(defn rename-keys
  "Return `m` with any key present in `kmap` renamed to that key's value in
  `kmap`; keys of `m` absent from `kmap` are left as-is. Mirrors
  clojure.set/rename-keys. Operates on a single map (not a relation) --
  `rename` below is the relation-wide form."
  [m kmap]
  (reduce
   (fn [out [old new]]
     (if (contains? m old)
       (assoc out new (get m old))
       out))
   (apply dissoc m (keys kmap))
   kmap))

(defn rename
  "Return a relation (set of maps) built from `xrel` by applying
  `rename-keys` with `kmap` to every map in it. Mirrors clojure.set/rename."
  [xrel kmap]
  (set (map #(rename-keys % kmap) xrel)))

(defn index
  "Return a map from the distinct values of `ks` (as a map holding just
  those keys) to the set of maps in relation `xrel` that have those values.
  Mirrors clojure.set/index."
  [xrel ks]
  (reduce
   (fn [m x]
     (let [ik (select-keys x ks)]
       (assoc m ik (conj (get m ik #{}) x))))
   {} xrel))

(defn- invert-map
  "Return `m` with each value mapped back to its key. Later entries win on a
  value collision. Private: mirrors clojure.set/map-invert but is not
  exported, since it is only needed here to implement the 3-arg `join`
  below and this namespace does not otherwise claim clojure.set/map-invert
  coverage."
  [m]
  (reduce (fn [out [k v]] (assoc out v k)) {} m))

(defn join
  "Join two relations (sets of maps).

  2-arg form -- natural join: joins `xrel` and `yrel` on every key name
  they have in common, keeping rows where the values at those keys match.
  Returns the empty set if either relation is empty (there is nothing to
  match against, not an error).

  3-arg form -- explicit-mapping join: `km` is a map of {xrel-key
  yrel-key}, naming which key of `xrel` corresponds to which key of `yrel`
  when the two relations don't share key names (or share a name that
  doesn't mean the same column).

  Mirrors clojure.set/join exactly, including which relation gets indexed
  (the smaller one, by count) -- an implementation-detail optimization that
  does not affect the result, only performance."
  ([xrel yrel]
   (if (and (seq xrel) (seq yrel))
     (let [ks (set-intersection (set (keys (first xrel))) (set (keys (first yrel))))
           [r s] (if (<= (count xrel) (count yrel)) [xrel yrel] [yrel xrel])
           idx (index r ks)]
       (reduce (fn [ret x]
                 (if-let [found (idx (select-keys x ks))]
                   (reduce #(conj %1 (clojure.core/merge %2 x)) ret found)
                   ret))
               #{} s))
     #{}))
  ([xrel yrel km]
   (let [[r s k] (if (<= (count xrel) (count yrel))
                   [xrel yrel (invert-map km)]
                   [yrel xrel km])
         idx (index r (vals k))]
     (reduce (fn [ret x]
               (if-let [found (idx (rename-keys (select-keys x (keys k)) k))]
                 (reduce #(conj %1 (clojure.core/merge %2 x)) ret found)
                 ret))
             #{} s))))

;; -- Bounded walk -------------------------------------------------------
;; Replaces clojure.walk/prewalk|postwalk in the frontier
;; (:collection-walk-set, forbidden [:unbounded-recursion]). Unlike
;; clojure.walk, both variants take an explicit depth ceiling and throw
;; instead of recursing without bound, so a cyclical or adversarial input
;; cannot exhaust the stack.

(def default-max-walk-depth
  "Depth ceiling used when bounded-prewalk/bounded-postwalk are called
  without an explicit max-depth."
  1024)

(defn- walk-depth-exceeded! [limit]
  (throw (ex-info "coll walk exceeds bounded depth limit"
                   {:kotoba.lang.coll/reason :walk/depth-exceeded :limit limit})))

(defn- walk-children [walk-one x depth]
  (cond
    (map? x) (into (empty x)
                    (map (fn [[k v]] [(walk-one k depth) (walk-one v depth)]))
                    x)
    (seq? x) (doall (map #(walk-one % depth) x))
    (coll? x) (into (empty x) (map #(walk-one % depth)) x)
    :else x))

(defn bounded-prewalk
  "Like clojure.walk/prewalk: apply f to form and then to its children,
  top-down. Bounded by max-depth (default default-max-walk-depth); throws
  ex-info rather than recursing without limit once the ceiling is crossed."
  ([f form] (bounded-prewalk f default-max-walk-depth form))
  ([f max-depth form]
   (letfn [(walk [x depth]
             (when (> depth max-depth) (walk-depth-exceeded! max-depth))
             (walk-children walk (f x) (inc depth)))]
     (walk form 0))))

(defn bounded-postwalk
  "Like clojure.walk/postwalk: apply f to form's children first, then to
  form itself, bottom-up. Bounded by max-depth (default
  default-max-walk-depth); throws ex-info rather than recursing without
  limit once the ceiling is crossed."
  ([f form] (bounded-postwalk f default-max-walk-depth form))
  ([f max-depth form]
   (letfn [(walk [x depth]
             (when (> depth max-depth) (walk-depth-exceeded! max-depth))
             (f (walk-children walk x (inc depth))))]
     (walk form 0))))

;; -- Unbounded walk (real clojure.walk) --------------------------------------
;;
;; !!!! READ THIS BEFORE "FIXING" bounded-prewalk/bounded-postwalk ABOVE !!!!
;;
;; bounded-prewalk/bounded-postwalk above are INTENTIONALLY depth-bounded --
;; that bound is a real, deliberate semantic divergence from clojure.walk
;; (see their docstrings and migration/bounded-coll-v1.edn), not a bug and
;; not a gap to be quietly closed. An estimated 106 existing call sites in
;; this workspace (adr-2809061500-clojure-namespace-to-kotoba-stdlib) may
;; depend on that bound as an actual safety property -- e.g. rejecting a
;; cyclical or adversarial input with a catchable ex-info instead of
;; exhausting the stack. Silently widening bounded-prewalk/bounded-postwalk
;; to be unbounded would change that safety property out from under every
;; caller that added the bound on purpose, without them touching a line of
;; their own code.
;;
;; walk/prewalk/postwalk/prewalk-replace/postwalk-replace below are a
;; SEPARATE, NEW set of functions that exist for callers who need genuine
;; clojure.walk-equivalent unbounded semantics (e.g. transforming a
;; document/AST of unknown, unbounded depth where no artificial ceiling is
;; correct). They are not a replacement for bounded-*, and bounded-* is not
;; a restricted version of them to be "corrected" back to matching. Both
;; pairs are permanent, parallel API surface:
;;
;;   bounded-prewalk / bounded-postwalk  -- depth-capped, throws past the cap
;;   walk / prewalk / postwalk           -- uncapped, matches real clojure.walk
;;
;; If you are reading this because you noticed the two pairs disagree and
;; are tempted to make bounded-* match walk/prewalk/postwalk (or vice
;; versa): don't. That disagreement is the entire point of this section
;; existing. Add a new function, or take the bound as an explicit argument
;; at the call site (bounded-prewalk/-postwalk already accept a max-depth
;; override) -- do not change what either name means.
;;
;; Semantics (walk's cond order, the map-entry/record special cases, prewalk
;; = top-down, postwalk = bottom-up) are transcribed from clojure.walk, not
;; reinvented. A walked map-entry is rebuilt as a real map entry --
;; `(first {k v})`, which is the host's own entry type on both runtimes
;; (clojure.lang.MapEntry / cljs MapEntry), as clojure.walk builds one --
;; so `(map-entry? x)`, `key` and `val` inside the walk function see what
;; they see under clojure.walk. (Until 2026-09-24 this built a plain 2-vector,
;; and the common `(postwalk #(if (map-entry? %) ... %) m)` idiom silently
;; skipped every entry.)

(defn walk
  "The most general tree walker: recursively applies `inner` to each
  element of `form`, then applies `outer` to the result. Mirrors
  clojure.walk/walk, unbounded (no depth ceiling -- see the section header
  above). `prewalk`/`postwalk` below are the usual entry points; use `walk`
  directly only when you need a different inner/outer split than either."
  [inner outer form]
  (cond
    (list? form) (outer (apply list (map inner form)))
    (map-entry? form) (outer (first {(inner (key form)) (inner (val form))}))
    (seq? form) (outer (doall (map inner form)))
    (record? form) (outer (reduce (fn [r x] (conj r (inner x))) form form))
    (coll? form) (outer (into (empty form) (map inner form)))
    :else (outer form)))

(defn prewalk
  "Like `walk`, but apply `f` to `form` and then to its children,
  recursively, top-down (f runs on a node before it runs on that node's
  children). Mirrors clojure.walk/prewalk, unbounded."
  [f form]
  (walk (partial prewalk f) identity (f form)))

(defn postwalk
  "Like `walk`, but apply `f` to `form`'s children first, then to `form`
  itself, recursively, bottom-up (f runs on a node's children before it
  runs on that node). Mirrors clojure.walk/postwalk, unbounded."
  [f form]
  (walk (partial postwalk f) f form))

(defn prewalk-replace
  "Recursively transform `form` by replacing every node that is a key in
  `replacements` with that key's value, top-down. Mirrors
  clojure.walk/prewalk-replace."
  [replacements form]
  (prewalk (fn [x] (if (contains? replacements x) (get replacements x) x)) form))

(defn postwalk-replace
  "Recursively transform `form` by replacing every node that is a key in
  `replacements` with that key's value, bottom-up. Mirrors
  clojure.walk/postwalk-replace."
  [replacements form]
  (postwalk (fn [x] (if (contains? replacements x) (get replacements x) x)) form))

;; -- Key coercion (clojure.walk's keywordize-keys / stringify-keys) ----------
;;
;; These are the two clojure.walk entry points that are NOT walk generics:
;; they are specific map-key coercions built on postwalk. They are here rather
;; than in a caller because every JSON/YAML/query-string boundary in this
;; workspace re-rolls them, and each hand-rolled copy tends to differ on the
;; two cases below.
;;
;; Two behaviours transcribed from clojure.walk that are easy to get wrong and
;; that the tests pin:
;;
;;   1. Only STRING keys are keywordized, and only KEYWORD keys are
;;      stringified. Every other key type (number, vector, symbol, nil) passes
;;      through untouched. A hand-rolled `(map-keys keyword m)` does not do
;;      this -- it would coerce a number key too.
;;
;;   2. `stringify-keys` uses `name`, so it DROPS a keyword's namespace:
;;      `:a/b` becomes `"b"`, not `"a/b"`. That is lossy and it is not
;;      round-trippable through `keywordize-keys` (`"b"` comes back as `:b`).
;;      This is clojure.walk's actual behaviour, so it is what a call site
;;      being migrated off clojure.walk depends on; do not "fix" it here.
;;      A caller who needs the namespace preserved wants
;;      `(map-keys #(if (keyword? %) (subs (str %) 1) %) m)`, not this.
;;
;; Both rebuild each map with `(into {} ...)`, like clojure.walk: a sorted-map
;; or a record in the input comes back as a plain map. Unbounded, matching the
;; walk/prewalk/postwalk pair above rather than the bounded-* pair.

(defn keywordize-keys
  "Recursively transform all string map keys in `form` into keywords, leaving
  keys of every other type untouched. Mirrors clojure.walk/keywordize-keys,
  unbounded.

  `(keywordize-keys {\"a\" {\"b\" 1} 2 3}) => {:a {:b 1} 2 3}`"
  [form]
  (let [coerce (fn [[k v]] (if (string? k) [(keyword k) v] [k v]))]
    (postwalk (fn [x] (if (map? x) (into {} (map coerce) x) x)) form)))

(defn stringify-keys
  "Recursively transform all keyword map keys in `form` into strings, leaving
  keys of every other type untouched. Mirrors clojure.walk/stringify-keys,
  unbounded.

  Uses `name`, so a namespaced keyword loses its namespace: `:a/b` => `\"b\"`.
  See the section comment above -- that loss is clojure.walk's behaviour and
  is deliberate here.

  `(stringify-keys {:a {:b 1} 2 3}) => {\"a\" {\"b\" 1} 2 3}`"
  [form]
  (let [coerce (fn [[k v]] (if (keyword? k) [(name k) v] [k v]))]
    (postwalk (fn [x] (if (map? x) (into {} (map coerce) x) x)) form)))

;; ---------------------------------------------------------------------------
;; persistent queue -- the host's, under a kotoba name
;; ---------------------------------------------------------------------------
;;
;; For scripts/migrate-clojure-lang-persistentqueue-to-kotoba-coll.cljk
;; (com-junkawasaki/root): `clojure.lang.PersistentQueue/EMPTY` is a JVM class
;; name, and on the kbb engine it does not resolve at all (`Unable to resolve
;; symbol: clojure.lang.PersistentQueue/EMPTY`, measured 2026-09-25), so
;; sources wrote a reader conditional or failed to load there. These are the
;; host's own queue (the object, not a copy): conj adds at the rear, peek/pop
;; work at the front, seq is front-to-rear, and it prints as the host prints
;; it (`#queue [..]` on kbb / ClojureScript, `#object[clojure.lang.PersistentQueue ..]`
;; from pr-str on the JVM, Clojure 1.12.1 -- measured).

(def empty-queue
  "The host's empty persistent queue: clojure.lang.PersistentQueue/EMPTY on
  the JVM, cljs.core/PersistentQueue.EMPTY on the kbb engine / ClojureScript."
  #?(:clj clojure.lang.PersistentQueue/EMPTY :cljs cljs.core/PersistentQueue.EMPTY))

(defn queue
  "A persistent queue holding the items of `coll` front-to-rear
  (`(into empty-queue coll)`); `(queue)` is `empty-queue`."
  ([] empty-queue)
  ([coll] (into empty-queue coll)))

(defn queue?
  "True when `x` is the host's persistent queue --
  `(instance? clojure.lang.PersistentQueue x)` on the JVM,
  `(instance? cljs.core/PersistentQueue x)` on the kbb engine / ClojureScript."
  [x]
  (instance? #?(:clj clojure.lang.PersistentQueue :cljs cljs.core/PersistentQueue) x))
