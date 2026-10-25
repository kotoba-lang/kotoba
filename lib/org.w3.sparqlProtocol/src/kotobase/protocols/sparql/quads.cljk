(ns kotobase.protocols.sparql.quads
  "Turns an already-`kotobase.query.bridge/materialize`d `arrangement.core`
  db into a seq of `kotoba-lang/sparql`-shaped RDF quads (`{:subject
  :predicate :object}`, each position an `rdf.core`-style term map).

  ## Why we take the whole plane instead of calling `bridge/q`

  `kotoba-lang/sparql` (this protocol repo's query engine) has its own
  complete algebra -- BGP/join/filter/union/optional/project/distinct/
  order-by/slice -- and expects a plain in-memory seq of quads, not a
  `:find`/`:where` Datalog query. Routing every SPARQL query through
  `arrangement.datalog/q` first would mean translating SPARQL algebra INTO
  Datalog algebra and back, for no benefit.

  **This is the SUPPORTED path, not a deviation from one** (ADR-2608039970 in
  `com-junkawasaki/root`). What the query surfaces share is the datom plane
  -- `bridge/materialize` -- not Datalog: `q` is one frontend over that
  plane and this repo is another, and they are peers. The ADR was written
  from this repo's behaviour, which had been correct and undocumented since
  it landed; what was missing was anything saying so.

  So: `materialize` once, take every triple via `bridge/datoms`, hand
  `sparql.core` a plain seq.

  This namespace used to walk `(:spo db)` itself, because the bridge exposed
  no full-plane scan -- a raw index read, with nothing on the supported path
  to apply `visible?` for it. `bridge/datoms` is that scan
  (kotoba-lang/kotobase-query#7), and using it puts the predicate back where
  the plane is read rather than one layer above it.

  ## `visible?` -- required, not defaulted

  `visible?` is REQUIRED on every path into the plane (ADR-2607050500 --
  \"query as first-class effect\", no permissive default), and that now
  includes the scan itself: `bridge/datoms` refuses a missing or
  non-callable predicate before reading anything. `datoms->quads` keeps its
  own check as well -- it is this repo's error, with this repo's message, at
  this repo's boundary, and the two agree rather than one standing in for
  the other. `visible?` is `(fn [{:keys [s p o]}]) -> bool`, applied
  triple-by-triple BEFORE the term transform. Passing `(constantly true)` is
  a caller's explicit choice, never this namespace's default."
  (:require [kotoba.lang.text :as str]
            [datom.source :as src]
            [kotobase.query.bridge :as bridge]))

;; --------------------------------------------------------------- IRI terms

(defn kw->iri-string
  "A materialized entity or attribute keyword -> a `urn:kotobase:...` IRI
  string. `:users/u1` -> `\"urn:kotobase:users/u1\"`; a bare (no-namespace)
  keyword like `:role` -> `\"urn:kotobase:role\"`. Deterministic and
  collision-free across every materialized collection (mirrors
  `kotobase.query.bridge`'s own entity-id scheme: `(keyword coll k)`), so
  the same source keyword always round-trips to the same IRI term, which is
  what BGP-pattern equality (`sparql.core/term=` is plain `=`) depends on.

  Total over what a datom attribute can actually be, not just over what it
  should be. `kotobase.query.bridge` now normalises document keys to keywords,
  which is the real fix for the case that found this — but before it did, a
  JSON-authored document put a STRING here, ClojureScript's `namespace` threw
  `Doesn't support namespace: <x>`, and every SPARQL query against that graph
  failed with an internal error whatever the query said (production,
  2026-07-31). A query surface should degrade to a usable IRI rather than 500
  when it meets an identifier shape it did not expect, so a non-`INamed`
  attribute is stringified rather than thrown on.

  A string `\"v2\"` and the keyword `:v2` therefore produce the SAME IRI. That
  is a deliberate conflation of two things the store can distinguish, and it is
  the right trade here only because the bridge no longer emits the string form;
  if it ever does again, the two collapse instead of erroring, and this comment
  is the warning."
  [kw]
  (if (or (keyword? kw) (symbol? kw))
    (str "urn:kotobase:" (if-let [ns (namespace kw)] (str ns "/" (name kw)) (name kw)))
    (str "urn:kotobase:" kw)))

(defn iri-string->kw
  "Inverse of `kw->iri-string`, for callers that need to go back from a
  bound `?var`'s IRI value to the originating keyword (e.g. to look up
  `:kotobase/coll`/`:kotobase/key` for a matched entity). Only handles the
  `urn:kotobase:...` scheme this namespace emits -- returns nil for
  anything else."
  [s]
  (when (str/starts-with? s "urn:kotobase:")
    (let [rest' (subs s (count "urn:kotobase:"))]
      (if-let [i (str/index-of rest' "/")]
        (keyword (subs rest' 0 i) (subs rest' (inc i)))
        (keyword rest')))))

(def kotobase-iri-prefix "urn:kotobase:")

(defn canonical-iri
  "The one IRI form this surface compares on, given whatever a query wrote.

  `urn:kotobase:...` is the surface's own scheme (`kw->iri-string` emits it
  for every entity and attribute), so a term already in that form is left
  alone. **A bare `<:attr>` is accepted as shorthand for it** —
  `<:sp/name>` -> `urn:kotobase::sp/name` — because that is the form
  `kotobase-server`'s `graph.sparql` has always taken (`kotobase.server.
  sparql` reads `<X>` as the attribute string `X` directly), and every
  existing caller writes queries that way.

  Without this, swapping that surface's implementation would turn
  `?e <:sp/name> \"alice\"` into a pattern whose predicate matches nothing —
  or, worse, into a WILDCARD. Not an error: a wrong answer.

  Anything else (`http://example.org/x`) is left exactly as written. It then
  equals no term this surface emits and therefore matches nothing, which is
  the truth: there is no such datom. It is deliberately NOT coerced into the
  kotobase namespace, and deliberately NOT turned into a wildcard."
  [v]
  (if (and (string? v) (str/starts-with? v ":"))
    (str kotobase-iri-prefix v)
    v))

(defn iri
  "An IRI term. The value is canonicalized (see `canonical-iri`) so that one
  attribute has one term, whichever spelling the query used — BGP matching is
  plain `=` on terms, so two spellings of the same attribute would otherwise
  simply never join."
  [v] {:rdf/type :iri :value (canonical-iri v)})

(defn ->literal
  "Plain literal term for `v` -- `{:rdf/type :literal :value v}`, `v`
  UNCOERCED (kept as the real Clojure/js value: string/number/boolean).
  Deliberately just these two keys, no `:datatype`/`:lang` -- see the ns
  docstring's equality note: `kotobase.protocols.sparql.parser` parses
  query-text literals into this exact same two-key shape so a query-side
  `900000` and a materialized doc's `:budget 900000` compare `=` (the
  datatype/lang tag SPARQL results output wants is derived from `v`'s
  runtime type at output time by `kotobase.protocols.sparql.results`, not
  carried on the term)."
  [v] {:rdf/type :literal :value v})

(defn ->term
  "One materialized `:o` value -> a SPARQL term. `:kotobase/coll`/
  `:kotobase/key` synthetic attrs and doc-map keyword attrs alike become
  plain literals here EXCEPT the special case below: `kotobase.query.
  bridge` stores a document's own keyword-valued reference fields (e.g.
  `:dept-key \"d1\"`) as plain strings, not as entity keywords -- so a
  cross-collection join (see `kotobase-query`'s own worked example) is
  written in SPARQL the same way it's written in Datalog: joining a
  literal `?dk` against the target's `:kotobase/key` LITERAL, not against
  an IRI. `:o` is therefore always a literal here; entities only ever
  appear as `:s` (via `->subject-term`)."
  [o] (->literal o))

(defn ->subject-term
  "A materialized `:s` (always a keyword entity id, `kotobase.query.
  bridge/materialize`'s `entity-id`) -> an IRI term."
  [s] (iri (kw->iri-string s)))

(defn ->predicate-term
  "A materialized `:p` (a keyword attr, doc-native or one of the two
  `:kotobase/*` synthetic attrs) -> an IRI term."
  [p] (iri (kw->iri-string p)))

;; ------------------------------------------------- algebra -> scan patterns
;;
;; The pushdown half (superproject ADR-2608039970 / kotobase-client#19). A
;; `datom.source/IPatternSource` answers `[s p o]`; the algebra already says
;; which `[s p o]`s a query needs. Handing those to the source is the
;; difference between reading the patterns a query names and reading the
;; database.

(defn iri-string->component
  "`urn:kotobase:alice` -> `\"alice\"` -- the RAW suffix, as a source's `:s`/
  `:p` carries it.

  Deliberately not `iri-string->kw`, which returns a KEYWORD because
  `kotobase.query.bridge/materialize` mints keyword entities. A source over
  the Datomic API's index reads carries the entity/attribute strings the rows
  themselves carry (`{e a v_edn added}`), and a keyword would match none of
  them. Two backends, two identities, one IRI form."
  [s]
  (when (and (string? s) (str/starts-with? s "urn:kotobase:"))
    (subs s (count "urn:kotobase:"))))

(defn term->component
  "One SPARQL term (or a `?var` symbol) -> the value a source pattern binds
  in that position, or nil for a wildcard.

  A variable is a wildcard. An IRI is an entity/attribute identity. A literal
  binds its own value -- objects are stored as wire strings, and the parser
  produces the same two-key literal shape from query text, so the comparison
  is the one the source can actually make."
  [t]
  (cond
    (nil? t) nil
    (symbol? t) nil
    (and (map? t) (= :iri (:rdf/type t)))
    (or (iri-string->component (:value t))
        ;; A foreign IRI binds ITSELF, not nil. nil is a WILDCARD here, and a
        ;; wildcard reads every datom and answers rows the query never asked
        ;; for — strictly worse than an empty answer. This bound it to nil
        ;; before ADR-2608039970's follow-up; it was wrong.
        (:value t))
    (and (map? t) (= :literal (:rdf/type t))) (:value t)
    :else nil))

(defn triple-pattern->scan
  "A SPARQL triple pattern -> the `[s p o]` a source scans."
  [[s p o]]
  [(term->component s) (term->component p) (term->component o)])

(defn algebra->scan-patterns
  "Every `[s p o]` an algebra tree will need, deduplicated.

  Walks `:patterns` (BGP) and recurses through the shapes
  `kotoba-lang/sparql` defines: `:pattern` (filter/project/distinct/
  order-by/slice) and `:left`/`:right` (join/union/optional). An unknown node
  contributes nothing rather than throwing -- a missed pattern is a missing
  read, which surfaces as a wrong answer in a test, whereas a throw here
  would take out queries that are otherwise fine. Add the node shape when one
  appears; do not make this lenient by design."
  [algebra]
  (letfn [(walk [node]
            (when (map? node)
              (concat (map triple-pattern->scan (:patterns node))
                      (walk (:pattern node))
                      (walk (:left node))
                      (walk (:right node)))))]
    (vec (distinct (walk algebra)))))

(defn describe-scan-patterns
  "DESCRIBE has no algebra: it names terms and wants every triple they appear
  in. That is two scans per term -- as subject, and as object.

  The object-position scan has no index behind it (see
  `kotobase.datom-source`'s plan table: `:vaet` covers ref-valued attributes
  only), so a DESCRIBE costs a full scan per term. Stated here rather than
  discovered in production."
  [terms]
  (vec (distinct (mapcat (fn [t]
                           (let [c (term->component t)]
                             [[c nil nil] [nil nil c]]))
                         terms))))

;; ------------------------------------------------------------- db -> quads

(defn datoms->quads
  "`db` (the return of `kotobase.query.bridge/materialize`) -> a vector of
  `kotoba-lang/sparql`-shaped RDF quads (`{:subject :predicate :object}`
  term maps), ready to hand to `sparql.core/select`/`sparql.core/ask`.

  `visible?` is REQUIRED -- `(fn [{:keys [s p o]}]) -> bool`, the SAME
  triple-map shape `kotobase.query.bridge`'s access paths use, applied to
  every `{:s :p :o}` BEFORE the term transform. `bridge/datoms` applies it
  to the scan; the check below is this repo's own, at this repo's boundary,
  so a caller gets this repo's error rather than one from underneath it.
  Pass `(constantly true)` to see everything materialized; that is a
  caller's explicit choice, never this fn's default (there is no 3-arity
  that omits it)."
  [db visible?]
  (when-not (ifn? visible?)
    (throw (ex-info "datoms->quads: visible? is required (no permissive default, ADR-2607050500)"
                     {:type ::visible?-required})))
  (into []
        (map (fn [{:keys [s p o]}]
               {:subject (->subject-term s)
                :predicate (->predicate-term p)
                :object (->term o)}))
        (bridge/datoms db visible?)))

(defn source->quads
  "`patterns` scanned against a `datom.source/IPatternSource` -> the same RDF
  quads `datoms->quads` produces from a materialized db.

  The difference is what gets read. `datoms->quads` takes the whole plane and
  then runs an algebra over it; this takes the patterns the algebra names.
  For a query naming two predicates that is two index ranges, whatever the
  graph's size (superproject ADR-2608039970; the source itself is
  `kotobase.datom-source`).

  The union is a SET before the term transform: two patterns of a query
  routinely overlap (`[?s :knows ?o]` and `[?s ?p \"bob\"]` both return the
  same datom), and a bag here would make `sparql.core`'s DISTINCT and its
  solution counts wrong in a way no test of this fn alone would catch.

  `visible?` is REQUIRED, same discipline and same triple-map shape as
  `datoms->quads`, applied before the term transform."
  [source patterns visible?]
  (when-not (ifn? visible?)
    (throw (ex-info "source->quads: visible? is required (no permissive default, ADR-2607050500)"
                     {:type ::visible?-required})))
  (into []
        (comp (filter visible?)
              (map (fn [{:keys [s p o]}]
                     {:subject (->subject-term s)
                      :predicate (->predicate-term p)
                      :object (->term o)})))
        (reduce (fn [acc pattern] (into acc (src/scan source pattern)))
                #{}
                patterns)))
