(ns kotobase.server.sparql-protocol
  "`graph.sparql` answered by the SPARQL 1.1 Protocol implementation
  (`kotoba-lang/org-w3-sparql-protocol` + `kotoba-lang/sparql`'s algebra)
  over a `kotobase.server.pattern-source` — index reads, not a hydrate.

  This is the implementation `handler/do-sparql` calls after the snapshot
  equivalence suite proved the former hydrated subset and this index-backed
  path agreed across the supported grammar (ADR-2608039970,
  ADR-2608039975).

  ## Why two implementations answer differently unless you are careful

  The old subset compiles a query into the map-form Datalog `do-q` executes
  and runs it over a fully hydrated `hot-db`. This one parses the same text
  into `kotoba-lang/sparql`'s algebra and runs it over the quads the query's
  own patterns read. Three things have to line up, and each has already
  bitten once:

  - **IRI spelling.** `<:sp/name>` is what every existing caller writes; the
    protocol repo's own scheme is `urn:kotobase:`. Reconciled upstream
    (org-w3-sparql-protocol#8) — a bare `<:attr>` is shorthand now, so one
    attribute has one term whichever spelling was used.
  - **Value representation.** `pattern-source` decodes `v_edn` one level, so
    a quad's object is the value the write path STORED — and the write path
    stringifies, so `:sp/age 30` is the string `\"30\"`. Query literals are
    coerced with `str` to meet it, which is the same pre-coercion the old
    subset does at compile time, and projection returns the value as-is —
    that is what `{:rows [[\"e1\" \"30\"]]}` has always meant.
  - **`visible?` shape.** `pattern-source` takes the ROW-shaped predicate
    (`{:e :a :v_edn :added}`) that `hot-datoms` forwards; `source->quads`
    takes the `{:s :p :o}` one. Filtering happens once, at the row level,
    which is why `(constantly true)` is passed to the second — the rows a
    viewer may not see never became quads."
  (:require [kotobase.protocols.sparql.parser :as parser]
            [kotobase.protocols.sparql.quads :as quads]
            [kotobase.server.pattern-source :as ps]
            [kotobase.server.admission :as admission]
            [sparql.core :as sparql]))

(defn- then* [x f]
  #?(:clj (f x)
     :cljs (.then (js/Promise.resolve x) f)))

(defn term->row-value
  "One bound term -> the value an XRPC row carries.

  An entity or attribute comes back as its identity string (`urn:kotobase:e1`
  -> `\"e1\"`); a literal comes back as the stored `v_edn` it already is. An
  unbound variable (OPTIONAL with no match) is nil, which is what a row with
  a hole has to say."
  [term]
  (cond
    (nil? term) nil
    (= :iri (:rdf/type term)) (or (quads/iri-string->component (:value term))
                                  (:value term))
    ;; A literal's term value is `v_edn` — the EDN ENCODING of the stored
    ;; value. `graph.sparql` rows have always carried the value itself
    ;; (`{:rows [[\"e1\" \"30\"]]}`, not `[[\"e1\" \"\\\"30\\\"\"]]`), so one
    ;; level comes back off here. Measured: without it every projected
    ;; literal came back one quoting level too deep.
    ;; No decode: `pattern-source` already handed back stored VALUES, and an
    ;; aggregate's result is a real value too. This used to read-string here,
    ;; back when quads carried `v_edn`.
    :else (:value term)))

(defn- coerce-literal
  "A query literal -> the form the datom plane stores.

  Rows carry `v_edn`, so `quads/source->quads` builds object terms whose
  value is the STORED string: `30` is `\"30\"`, `\"alice\"` is the seven
  characters `\"alice\"` INCLUDING its quotes. The parser builds literals
  from query text as real values. BGP matching is plain `=` on terms, so
  without this every literal comparison silently answers nothing —
  measured: `SELECT ?e WHERE { ?e <:sp/name> \"alice\" }` returned 0 rows
  against the subset's 1.

  This is the same pre-coercion `kotobase.server.sparql` does at compile
  time (\"literals pre-coerced to the write path's stored-string
  representation\"). It belongs to the SOURCE, not the parser: the
  materialize-backed path stores real values and needs no coercion at all,
  which is why this lives here rather than upstream."
  [t]
  (if (and (map? t) (= :literal (:rdf/type t)))
    ;; `(str v)` before encoding, because the WRITE path stringifies first:
    ;; `:sp/age 30` is stored as the string \"30\", whose `v_edn` is
    ;; `\"\\\"30\\\"\"`. Encoding the number directly gives `\"30\"` and matches
    ;; nothing — measured on `{ ?e <:sp/age> 30 }`.
    (assoc t :value (str (:value t)))
    t))

(defn- coerce-algebra
  "`coerce-literal` over every triple pattern in an algebra tree. Walks the
  shapes `kotoba-lang/sparql` defines, same as
  `quads/algebra->scan-patterns`.

  FILTER predicates are compiled functions and are NOT rewritten — a FILTER
  comparing against a literal therefore compares against the stored form the
  caller wrote, which is a known edge this does not yet cover."
  [node]
  (if-not (map? node)
    node
    (cond-> node
      (:patterns node) (update :patterns (fn [ps] (mapv #(mapv coerce-literal %) ps)))
      (:pattern node) (update :pattern coerce-algebra)
      (:left node) (update :left coerce-algebra)
      (:right node) (update :right coerce-algebra))))

(defn- pattern-vars
  "Every variable an algebra tree could bind: the vars in its triple
  patterns, plus the output var of every aggregate (which the group
  produces rather than matches)."
  [node]
  (if-not (map? node)
    #{}
    (into (set (concat (mapcat (fn [p] (filter symbol? p)) (:patterns node))
                       (map :var (:aggregates node))))
          (mapcat pattern-vars [(:pattern node) (:left node) (:right node)]))))

(defn- unbound-projection
  "A SELECT var that nothing in the WHERE could ever bind, or nil.

  SPARQL says such a var is simply unbound, and the protocol path would
  answer `[[nil] [nil]]` — one useless row per solution. The subset this
  replaces refused it instead, and refusing is the kinder answer: nobody
  writes `SELECT ?x` meaning `give me a column of nothing`, so it is a typo
  every time. Kept on the swap deliberately."
  [output-vars algebra]
  (let [bindable (pattern-vars algebra)]
    (first (remove bindable output-vars))))

(defn- vars-of
  "`head.vars` order: the query's own projection, or — for `SELECT *` —
  every var seen across the rows in first-seen order. Same rule
  `kotobase.protocols.sparql.results/select->json` uses, so the JSON surface
  and this one never disagree about column order."
  [output-vars rows]
  (vec (or (seq output-vars)
           (distinct (mapcat keys rows)))))

(defn select-response
  "`sparql.core/select` bindings -> the `{:vars :rows}` shape `graph.sparql`
  has always returned. `:vars` are `\"?e\"`-style strings; `:rows` are
  positional."
  [graph output-vars bindings]
  (let [vars (vars-of output-vars bindings)]
    {:ok true :graph graph
     :vars (mapv str vars)
     :rows (mapv (fn [row] (mapv #(term->row-value (get row %)) vars)) bindings)}))

(defn do-sparql
  "`graph.sparql` via the protocol implementation. Same request body
  (`{:graph :sparql}`) and same response shape as `handler/do-sparql`.

  A parse failure answers `UnsupportedSparql` with the parser's own message,
  matching the subset's posture: loudly-rejected approximation, never a
  silently different query.

  Only SELECT answers a row table. ASK/CONSTRUCT/DESCRIBE are real SPARQL
  forms this transport has no shape for — `graph.sparql` returns
  `{:vars :rows}` and nothing else — so they are refused here rather than
  flattened into something that looks like a result set. The HTTP surface
  (`kotobase.protocols.sparql/handle`) is where those belong."
  [store {:keys [graph sparql]} visible?]
  (let [parsed (try (parser/parse sparql)
                    (catch #?(:clj Exception :cljs :default) e e))]
    (cond
      (instance? #?(:clj Exception :cljs js/Error) parsed)
      {:ok false :error "UnsupportedSparql"
       :message #?(:clj (.getMessage ^Exception parsed) :cljs (.-message parsed))}

      (not= :select (:form parsed))
      {:ok false :error "UnsupportedSparql"
       :message (str "graph.sparql answers SELECT only; " (name (:form parsed))
                     " returns a graph or a boolean, which this response shape "
                     "cannot carry — use the SPARQL 1.1 Protocol HTTP surface")}

      (unbound-projection (:output-vars parsed) (:algebra parsed))
      {:ok false :error "UnsupportedSparql"
       :message (str "SELECT names " (unbound-projection (:output-vars parsed)
                                                         (:algebra parsed))
                     ", which nothing in the WHERE can bind — it would answer a "
                     "column of unbound values")}

      :else
      ;; Coerce FIRST, then derive the patterns from the coerced algebra.
      ;; `of-quads`' scan filters by the pattern it is handed, so an
      ;; uncoerced literal there drops every quad before the algebra ever
      ;; runs — measured: `{ ?e <:sp/name> \"alice\" }` answered 0 rows with
      ;; the coercion applied to the algebra alone.
      (let [algebra (coerce-algebra (:algebra parsed))
            patterns (quads/algebra->scan-patterns algebra)
            chain ((:head-get store) graph)
            ;; This is the DEPLOYED SPARQL path -- `graph.sparql` reaches
            ;; here, not `run-indexed-compiled-graph-query` -- so the gate has
            ;; to be here too. It was not, on the first landing of
            ;; `kotobase.server.admission`, and nothing said so until
            ;; `verify-unbounded-query-paths` reported this file for requiring
            ;; `pattern-source` and never mentioning `admission`. A `SELECT *
            ;; WHERE { ?s ?p ?o }` is exactly the whole-graph read that gate
            ;; exists to refuse, and this surface takes it from the network.
            {:keys [admitted? refusals]} (admission/admit-patterns patterns)]
        (if-not admitted?
          (admission/refusal-response refusals)
          (then* (ps/source-for store chain patterns (or visible? (constantly true)))
               (fn [source]
                 ;; `(constantly true)` deliberately: the viewer filter already
                 ;; ran at the row level inside `hot-datoms`, and applying a
                 ;; ROW-shaped predicate to `{:s :p :o}` quads would filter
                 ;; nothing while looking like it did.
                 (if-let [over (admission/over-budget (or (ps/datom-count source) 0))]
                   (admission/refusal-response [over])
                   ;; No `:clause-cardinality` here, deliberately: this surface
                   ;; does not hand the algebra to `datalog.core` at all. It
                   ;; materialises the named ranges into a quad seq and runs
                   ;; `sparql.core`'s own BGP, which joins in memory already --
                   ;; there is no keyed-scan-per-binding path to replace. The
                   ;; hint belongs where the Datalog executor is, which is
                   ;; `handler`'s two doors.
                   (let [quad-seq (quads/source->quads source patterns (constantly true))]
                     (select-response graph (:output-vars parsed)
                                      (sparql/select algebra quad-seq)))))))))))
