(ns kotobase.gremlin.traversal
  "gremlin.kotobase.net -- a v0.1 Apache TinkerPop (tinkerpop.apache.org)
  Gremlin traversal subset over kotobase, via the shared
  `kotobase.query.bridge` (ADR-2607172300 in `com-junkawasaki/root`,
  ADR-2607172500 scoping this repo).

  Pure `.cljc` -- **zero socket/GraphSON-framing concepts in this
  namespace**, same separation-of-concerns discipline `org-ietf-sftp`
  (`kotobase.sftp.fs` vs `kotobase.sftp.transport.*`) and
  `org-postgresql-wire` use between core query-translation logic and
  transport. The `.cljs`-only WebSocket + GraphSON wire layer that calls
  into `execute` below lives in `kotobase.gremlin.wire`.

  ## Bytecode-shaped input, not raw Gremlin script text (deliberate v0.1
  scope reduction, ADR-2607172500)

  This namespace does **not** parse Groovy-shaped Gremlin script strings
  (`g.V().hasLabel('users').values('name')` as source text) -- it accepts a
  small EDN vector-of-steps \"bytecode\" that is structurally close to how
  real TinkerPop Bytecode is shaped (a flat list of `[step-name & args]`
  instructions), just simplified to plain EDN instead of TinkerPop's
  GraphSON-typed Bytecode object graph:

  ```clojure
  [[:V] [:hasLabel \"users\"] [:has \"role\" \"admin\"] [:values \"name\"]]
  ```

  is the bytecode-shaped equivalent of the Gremlin traversal
  `g.V().hasLabel('users').has('role', 'admin').values('name')`. Avoiding a
  Groovy-subset parser on top of everything else this repo already does
  (translation + a real WebSocket transport) is an honest, deliberate v0.1
  scope boundary -- see the References section below and this repo's
  README for exactly what is and is not supported.

  ## v0.1 traversal-step subset (hard scope boundary)

  | Step | Bytecode shape | Meaning |
  |---|---|---|
  | `g.V()` | `[:V]` | scan a materialized vertex collection -- MUST be the first step |
  | `.hasLabel(label)` | `[:hasLabel label]` | filter: current vertex's `:kotobase/coll` (materialized collection name) equals `label` |
  | `.has(prop, value)` | `[:has prop value]` | filter: current vertex's `prop` attribute equals `value` (equality only) |
  | `.out(edgeLabel)` | `[:out edgeLabel]` | outgoing edge traversal -- see \"Edge convention\" below |
  | `.in(edgeLabel)` | `[:in edgeLabel]` | incoming edge traversal -- see \"Edge convention\" below |
  | `.values(prop)` | `[:values prop]` | projection, TERMINAL step -- MUST be the last step, produces the result list |

  **Explicitly OUT OF SCOPE for v0.1** (rejected with a clear error by
  `execute`/`translate`, never silently ignored or partially executed):
  full Gremlin script `eval` (arbitrary Groovy-shaped expressions --
  n/a here since input is already bytecode-shaped, not script text, but
  worth stating for anyone porting a real GraphSON `\"op\": \"eval\"`
  request into this namespace: it is not supported, only `\"op\":
  \"bytecode\"` is, see `kotobase.gremlin.wire`), `.repeat()`/variable-length
  paths, lambda/closure steps, mutation steps (`addV`/`addE`/`drop`/`property`
  writes), transactions, `.hasLabel`/`.values` with more than one argument
  (real Gremlin's multi-key `.values(k1, k2)` has flat multi-key fan-out
  stream semantics that would change this translator's single-`?var`-per-
  step shape -- out of scope, rejected explicitly), `.hasLabel`/`.has` OR
  semantics (`.hasLabel(l1, l2)`), any step name not in the table above.

  ## Vertex collections MUST be declared explicitly by the caller

  Unlike `org-opencypher-cypher`'s Cypher translator (where every node
  pattern is labeled on both ends of a relationship,
  `(a:LabelA)-[:REL]->(b:LabelB)`, so the set of collections to materialize
  is mechanically derivable from the parsed statement), a Gremlin
  `.out(edgeLabel)`/`.in(edgeLabel)` step does NOT self-declare the target
  vertex's label -- `g.V().hasLabel('users').out('worksAt').values('name')`
  never names the `departments` collection in the traversal at all. This
  namespace therefore requires the CALLER to declare, up front, every
  `kotobase.store` collection that should be materialized as vertices --
  the `:vertex-colls` key in `execute`'s `ctx` map, a seq of collection
  identifiers exactly like `kotobase.query.bridge/materialize`'s own
  `coll-keys` argument (which this namespace passes it straight through to).
  This is this repo's own, deliberate v0.1 convention (documented here, not
  silently assumed) -- the deploy shell / test fixtures that own the graph
  schema are expected to supply the full vertex-collection set, the same
  \"deploy shell provides the schema\" discipline ADR-2607172500 uses for
  `org-graphql-http`'s SDL.

  ## Edge convention: reference-valued attribute -> target `:kotobase/key`

  There is no first-class \"edge\" concept in kotobase's flat document
  model (`kotobase.store` is get/put/list per collection, nothing else) --
  same starting point `org-opencypher-cypher`'s relationship-pattern bonus
  scope documents for itself. This repo's own convention, applied
  mechanically: a materialized vertex represents an outgoing edge labeled
  `edgeLabel` by carrying an attribute named `(keyword edgeLabel)` whose
  value equals the TARGET vertex's `:kotobase/key` (a STRING, per
  `kotobase.query.bridge`'s own doc->datoms mapping -- materialized keys are
  always strings). Concretely, for `.out(\"worksAt\")` starting from a
  `users` vertex to reach a `departments` vertex, the `users` document must
  carry `{:worksAt \"d1\" ...}` where `\"d1\"` is the target department's
  key. `.in(\"worksAt\")` is the exact reverse traversal (find every vertex
  whose `:worksAt` attribute equals the CURRENT vertex's `:kotobase/key`) --
  it does not require a separately-stored 'incoming edge' list, it is a
  Datalog join run in the opposite direction over the SAME stored
  attribute. This is exactly the `fk-attr` convention
  `kotobase.protocols.cypher`'s relationship-pattern bonus scope uses,
  applied via `edgeLabel` directly (Gremlin edge labels have no
  Cypher-style `SNAKE_CASE` -> lower-case folding rule to mirror -- the
  label string is used verbatim as the attribute name, via `keyword`).

  ## Result semantics -- deduplicated set, not a Gremlin bag

  Real Gremlin traversals have *bag* (multiset) semantics -- `.values()`
  can and does emit duplicate values for duplicate matching paths.
  `kotobase.query.bridge/q` (and the `arrangement.datalog` engine
  underneath it) returns a mathematical SET of result tuples -- this
  namespace inherits that dedup behavior unchanged rather than
  reimplementing bag semantics on top, and documents it here as an honest
  v0.1 simplification (same simplification `org-opencypher-cypher`
  documents for its own `execute`, which also delegates straight to the
  bridge). `execute` sorts the (already-deduplicated) results by
  stringified value for deterministic output across runs -- there is no
  `.order()` step in v0.1, this is an implementation convenience only, not
  a Gremlin ordering guarantee.

  ## `visible?` -- required, injectable, never defaulted

  `ctx` passed to `execute` MUST include `:visible?`, a predicate over
  materialized datoms (`(fn [{:keys [s p o]}] boolean?)`) -- the same
  discipline `kotobase.query.bridge`/`arrangement.datalog`/
  `kotobase.protocols.cypher` enforce (ADR-2607050500, \"Query as
  first-class effect\"). `execute` throws immediately (a ctx-construction
  bug, not a traversal error) if `:visible?` is missing -- there is no
  silent `(constantly true)` fallback anywhere in this namespace.

  ## References

  - ADR-2607172500 (`com-junkawasaki/root`) -- the ADR that scoped this repo
  - ADR-2607172300 -- the four-surface `kotobase-query` precedent this ADR
    extends, and the source of the required, non-defaulted `visible?`
    discipline
  - `kotobase.protocols.cypher` (`kotoba-lang/org-opencypher-cypher`) -- the
    sibling translator this namespace's join convention and
    execute/translate split are modeled on"
  (:require [kotobase.query.bridge :as bridge]))

;; ------------------------------------------------------------------ errors

(defn- gremlin-err
  "An `ex-info` for any traversal-translation failure -- out-of-scope step,
  malformed bytecode, missing/duplicate terminal step, wrong arity. `code`
  is a short machine-readable keyword (mirrors `kotobase.protocols.cypher`'s
  `:cypher/code` convention, this repo's own naming); `msg` is the
  human-readable message callers (including `kotobase.gremlin.wire`) should
  surface."
  [code msg]
  (ex-info msg {:gremlin/code code :gremlin/message msg}))

(def ^:private known-steps
  "The full v0.1 step vocabulary -- anything else is rejected by `translate`
  with a clear, explicit error naming both what WAS given and the
  out-of-scope list this repo does not implement (ADR-2607172500)."
  #{:V :hasLabel :has :hasNot :out :in :values :dedup :order :limit :count})

(def ^:private post-steps
  "Steps that operate on the PROJECTED RESULTS rather than on the traversal.

  They come after `.values(prop)` and are applied by `execute` to the result
  vector, because that is what they mean: `.limit(2)` bounds the answer, not
  the join. Pushing them into the Datalog `:where` would require the bridge
  to have a notion of order and of a row window, which it does not.

  `.order()` is bare — TinkerPop's `.by()` modulators (`.order().by('age',
  desc)`) are out of scope, and `.order()` with no `.by()` is natural
  ascending in TinkerPop too, so the bare form means what it means there.

  `.dedup()` is accepted and is a NO-OP on this backend: the bridge's Datalog
  `q` already has set semantics, so results arrive distinct. It is kept
  because a Gremlin user writes it habitually and erroring would be hostile,
  and it is documented as a no-op because claiming it collapses something
  would misplace where the collapse happens."
  #{:dedup :order :limit :count})

(def ^:private out-of-scope-note
  "Explicitly OUT OF SCOPE for v0.1 (ADR-2607172500): full Gremlin script eval, .repeat()/variable-length paths, lambda/closure steps, mutation steps (addV/addE/drop/property), transactions, GraphBinary serialization, multi-key .values(k1,k2,...) fan-out, .hasLabel/.has OR-semantics.")

;; --------------------------------------------------------------- translate

(defn- step-arity-err [step-name n args]
  (throw (gremlin-err :gremlin/bad-arity
                       (str "step " (name step-name) " expects exactly " n
                            " argument" (when (not= n 1) "s") ", got "
                            (count args) ": " (pr-str args)))))

(defn- unknown-step-err [tup]
  (throw (gremlin-err :gremlin/unsupported-step
                       (str "unsupported traversal step " (pr-str tup)
                            " -- v0.1 only supports " (pr-str (vec (sort known-steps)))
                            ". " out-of-scope-note))))

(defn- var-sym [n] (symbol (str "?v" n)))

(defn- step-name [tup]
  (when-not (and (vector? tup) (seq tup) (keyword? (first tup)))
    (throw (gremlin-err :gremlin/malformed-step
                         (str "each bytecode step must be a vector starting with a keyword"
                              " step name, e.g. [:hasLabel \"users\"] -- got " (pr-str tup)))))
  (first tup))

(defn translate
  "`bytecode` (a vector of `[step-name & args]` tuples, see ns docstring) ->
  a `kotobase.query.bridge`-shaped query descriptor:
  `{:query {:find [...] :where [...]} :terminal-prop \"...\"}`.

  Throws `ex-info` (`(:gremlin/code (ex-data e))`, `(:gremlin/message
  (ex-data e))`) for anything outside the v0.1 subset -- see ns docstring's
  step table. Never silently accepts or partially executes out-of-scope
  syntax.

  `bytecode` MUST start with `[:V]` and end with exactly one `[:values
  prop]` step (the terminal/projection step) -- both requirements are this
  repo's own v0.1 convention (documented in the ns docstring), not
  something TinkerPop itself mandates for every traversal."
  [bytecode]
  (when-not (and (sequential? bytecode) (seq bytecode))
    (throw (gremlin-err :gremlin/empty-bytecode
                         "bytecode must be a non-empty vector of [step-name & args] tuples")))
  (when-not (= :V (step-name (first bytecode)))
    (throw (gremlin-err :gremlin/missing-V
                         (str "bytecode must start with [:V] (g.V()) -- got "
                              (pr-str (first bytecode))))))
  ;; Split the traversal from the post-projection steps. `.values(prop)` is
  ;; still the pivot: everything before it walks the graph, everything after
  ;; it reshapes the answer.
  (let [vidx (first (keep-indexed (fn [i t] (when (= :values (step-name t)) i)) bytecode))]
    (when-not vidx
      (throw (gremlin-err :gremlin/missing-terminal-values
                          (str "bytecode must contain exactly one [:values prop] step"
                               " (the projection step) -- got " (pr-str (last bytecode))))))
    (when (some #(= :values (step-name %)) (drop (inc vidx) bytecode))
      (throw (gremlin-err :gremlin/values-not-terminal
                          ".values(prop) is only supported ONCE, as the projection step")))
    (let [post (vec (drop (inc vidx) bytecode))]
      (doseq [t post]
        (when-not (contains? post-steps (step-name t))
          (throw (gremlin-err :gremlin/step-after-values
                              (str "only " (pr-str (sort post-steps)) " may follow"
                                   " .values(prop) -- got " (pr-str t))))))
      (doseq [t (butlast post)]
        (when (= :count (step-name t))
          (throw (gremlin-err :gremlin/count-not-last
                              ".count() reduces the traversal to a number, so nothing may follow it"))))
      (doseq [t post]
        (let [[op & args] t
              want (if (= :limit op) 1 0)]
          (when (not= want (count args)) (step-arity-err op want args))))
      (when-let [[_ n] (first (filter #(= :limit (step-name %)) post))]
        (when-not (and (integer? n) (not (neg? n)))
          (throw (gremlin-err :gremlin/bad-limit
                              (str ".limit(n) expects a non-negative integer -- got " (pr-str n))))))))
  (loop [steps (take-while #(not= :values (step-name %)) (rest bytecode))
         cur-var (var-sym 0)
         next-id 1
         where []]
    (let [tup (first steps)
          [op & args] tup]
      (cond
        ;; The traversal steps are exhausted; project with .values(prop) and
        ;; hand the post-projection steps to `execute`.
        (nil? tup)
        (let [vidx (first (keep-indexed (fn [i t] (when (= :values (step-name t)) i)) bytecode))
              [_ prop] (nth bytecode vidx)
              result-var (symbol (str "?r" next-id))]
          (when (not= 2 (count (nth bytecode vidx))) (step-arity-err :values 1 (rest (nth bytecode vidx))))
          {:query {:find [result-var]
                   :where (conj where [cur-var (keyword (str prop)) result-var])}
           :vertex-var cur-var
           :post (vec (drop (inc vidx) bytecode))})

        (= :V op)
        (throw (gremlin-err :gremlin/duplicate-V
                             "[:V] (g.V()) is only supported as the FIRST step in v0.1"))

        (= :hasLabel op)
        (do (when (not= 1 (count args)) (step-arity-err op 1 args))
            (recur (rest steps) cur-var next-id
                   (conj where [cur-var :kotobase/coll (str (first args))])))

        (= :has op)
        (do (when (not= 2 (count args)) (step-arity-err op 2 args))
            (let [[prop v] args]
              (recur (rest steps) cur-var next-id
                     (conj where [cur-var (keyword (str prop)) v]))))

        ;; `.hasNot(key)` -- the vertex must NOT carry the property at all.
        ;; datalog's `not` clause is the primitive: it drops a binding iff the
        ;; fully-substituted pattern has any visible match, so a wildcard value
        ;; asks exactly "is this attribute present". Distinct from
        ;; `.has(key, nil)`, which would ask for a stored nil.
        (= :hasNot op)
        (do (when (not= 1 (count args)) (step-arity-err op 1 args))
            (recur (rest steps) cur-var next-id
                   (conj where (list 'not [cur-var (keyword (str (first args))) '_]))))

        (= :out op)
        (do (when (not= 1 (count args)) (step-arity-err op 1 args))
            (let [edge-label (str (first args))
                  fk-var (symbol (str "?fk" next-id))
                  new-var (var-sym next-id)]
              (recur (rest steps) new-var (inc next-id)
                     (-> where
                         (conj [cur-var (keyword edge-label) fk-var])
                         (conj [new-var :kotobase/key fk-var])))))

        (= :in op)
        (do (when (not= 1 (count args)) (step-arity-err op 1 args))
            (let [edge-label (str (first args))
                  fk-var (symbol (str "?fk" next-id))
                  new-var (var-sym next-id)]
              (recur (rest steps) new-var (inc next-id)
                     (-> where
                         (conj [new-var (keyword edge-label) fk-var])
                         (conj [cur-var :kotobase/key fk-var])))))

        :else (unknown-step-err tup)))))

;; ----------------------------------------------------------------- execute

(defn execute
  "Run bytecode-shaped `bytecode` (see ns docstring) against `ctx`:
  `{:store IStore :vertex-colls [coll-key ...] :visible? (fn [datom] bool)}`.

  Translates `bytecode` (via `translate`) into a `kotobase.query.bridge`
  query, materializes `:vertex-colls` from `:store`, runs the query filtered
  by the REQUIRED `:visible?` predicate, and returns a SORTED vector of
  projected `.values(prop)` results (see ns docstring's \"Result semantics\"
  section).

  Post-projection steps -- `.dedup()`, `.order()`, `.limit(n)`, `.count()` --
  are applied here, in the order they were written, because that is what they
  mean: `.limit(2)` bounds the answer, not the join. `.count()` reduces to a
  one-element vector holding the number.

  Throws immediately (a ctx-construction bug, not a traversal error) if
  `:visible?` is missing, or if `:vertex-colls` is missing/empty (ADR-
  2607050500 discipline, same as `kotobase.query.bridge`/
  `kotobase.protocols.cypher`)."
  [{:keys [store vertex-colls visible?] :as ctx} bytecode]
  (when-not (fn? visible?)
    (throw (gremlin-err :gremlin/missing-visible
                         (str "kotobase.gremlin.traversal/execute requires ctx :visible? -- a"
                              " REQUIRED predicate fn over materialized datoms, no permissive"
                              " default (ADR-2607050500). Pass (constantly true) to see"
                              " everything materialized."))))
  (when-not (and (sequential? vertex-colls) (seq vertex-colls))
    (throw (gremlin-err :gremlin/missing-vertex-colls
                         (str "kotobase.gremlin.traversal/execute requires ctx :vertex-colls --"
                              " a REQUIRED, non-empty seq of kotobase.store collection"
                              " identifiers to materialize as the graph's vertices (see ns"
                              " docstring's \"Vertex collections MUST be declared explicitly\""
                              " section). Got: " (pr-str vertex-colls)))))
  (let [{:keys [query post]} (translate bytecode)
        ;; db-for memoises when ctx carries a content address (ADR-2607310900 L1).
        rows (bridge/q (bridge/db-for ctx store vertex-colls) query visible?)
        ;; Default order is by stringified value, as it always has been: the
        ;; bridge promises none, and an unstable answer is worse than an
        ;; arbitrary but repeatable one. An explicit .order() asks for the
        ;; same thing, so it is a no-op rather than a second sort.
        vals (vec (sort-by str (map first rows)))]
    (reduce (fn [acc tup]
              (case (step-name tup)
                :dedup (vec (distinct acc))
                :order (vec (sort-by str acc))
                :limit (vec (take (second tup) acc))
                :count [(count acc)]
                acc))
            vals
            post)))
