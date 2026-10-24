(ns rdf.core
  "EDN-first RDF terms, triples, quads, and datasets, per RDF 1.1 Concepts and
  Abstract Syntax (W3C Recommendation, 25 February 2014):
  https://www.w3.org/TR/rdf11-concepts/

  This namespace covers the structural abstract syntax only (Sec 3 \"RDF
  Graphs\": terms and triples). It does not implement RDF's model-theoretic
  semantics (entailment, equivalence beyond term-equality, inconsistency —
  Sec 1.7, formally deferred by the spec itself to the separate RDF 1.1
  Semantics document) — see `kotoba-lang/org-w3-owl2` for entailment-level
  reasoning over RDF-shaped graphs. See `rdf.validate` for structural
  well-formedness checking and `rdf.dataset` for the RDF Dataset (Sec 4)
  default-graph-plus-named-graphs model.

  Terms are plain maps:
  - `{:rdf/type :iri :value \"...\"}`             — Sec 3.2 IRIs
  - `{:rdf/type :blank :id \"...\"}`               — Sec 3.4 Blank Nodes
  - `{:rdf/type :literal :value \"...\" :datatype ... :language ...}` — Sec 3.3

  Triples/quads are maps with `:subject`/`:predicate`/`:object` and an
  optional `:graph` (Sec 4 named-graph name).")

(def rdf-lang-string
  "Sec 3.3: the datatype IRI a literal MUST have if and only if it carries a
  language tag." "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString")

(def xsd-string
  "Sec 3.3: 'Simple literals... are syntactic sugar for abstract syntax
  literals with the datatype IRI xsd:string.' This is the RDF 1.1 default for
  a literal with no explicit datatype and no language tag — a semantic
  change from RDF 1.0, where an untyped/undecorated literal was a distinct
  'plain literal' notion rather than an xsd:string-typed one. Older RDF
  material written against RDF 1.0 that talks about 'plain literals' is
  describing what RDF 1.1 now calls an xsd:string-typed literal."
  "http://www.w3.org/2001/XMLSchema#string")

(defn iri
  "Sec 3.2: an IRI term. `value` should be an absolute IRI string (RDF's
  abstract syntax requires IRIs to be absolute; this constructor does not
  itself validate RFC 3987 syntax — see `rdf.validate/iri-problems`)."
  [value]
  {:rdf/type :iri :value value})

(defn bnode
  "Sec 3.4: a blank node term. `id` is a *locally-scoped* identifier: RDF's
  abstract syntax gives blank nodes no internal structure and no identifier
  that is portable across documents/graphs, so reusing the same `id` string
  in two unrelated datasets does not connect them in spec terms (it only
  produces two value-equal-but-conceptually-unrelated maps here). Reusing an
  `id` *within* one `rdf.dataset` Dataset to mean the same node in more than
  one of its graphs is fine and spec-sanctioned (Sec 4: 'blank nodes can be
  shared between graphs in an RDF dataset')."
  [id]
  {:rdf/type :blank :id id})

(defn literal
  "Sec 3.3: a literal is a lexical form + a datatype IRI, plus a language tag
  if and only if that datatype IRI is exactly `rdf-lang-string`. This
  constructor defaults the datatype so the *iff* holds even when the caller
  only supplies a `:language`:
  - `:language` given, no `:datatype` given  => datatype defaults to
    `rdf-lang-string` (NOT `xsd-string` — defaulting to `xsd-string` here
    would silently build a malformed literal, since it would carry a
    language tag with a non-langString datatype).
  - neither given                            => datatype defaults to
    `xsd-string` (RDF 1.1's 'simple literal' sugar, see `xsd-string` doc).
  - `:datatype` given explicitly             => used as given, even if it
    conflicts with `:language` (this constructor does not silently overwrite
    caller-supplied values); use `rdf.validate/literal-problems` to catch
    that conflict."
  ([value] (literal value {}))
  ([value {:keys [datatype language]}]
   (let [dt (cond
              datatype (if (map? datatype) datatype (iri datatype))
              language (iri rdf-lang-string)
              :else (iri xsd-string))]
     (cond-> {:rdf/type :literal :value value :datatype dt}
       language (assoc :language language)))))

(defn term?
  "True if `x` is a recognized RDF term map (Sec 3: IRI, blank node, or
  literal)."
  [x]
  (and (map? x)
       (contains? #{:iri :blank :literal} (:rdf/type x))))

(defn triple
  "Sec 3.1: subject ∈ {IRI, blank node}, predicate = IRI, object ∈ {IRI,
  blank node, literal}. Not checked here — see `rdf.validate/triple-problems`
  for the role constraints (this constructor just assembles the map)."
  [subject predicate object]
  {:subject subject :predicate predicate :object object})

(defn quad
  "A `triple` plus an optional `:graph` naming the named graph (Sec 4) it
  belongs to; a quad with no `:graph` key belongs to the dataset's default
  graph."
  ([subject predicate object] (triple subject predicate object))
  ([subject predicate object graph]
   {:subject subject :predicate predicate :object object :graph graph}))

(defn dataset
  "A flat, ungrouped bag of quads: `{:rdf/dataset [quad ...]}`. This is a
  convenience container only — it does not distinguish default vs. named
  graphs and does not dedup (a `:graph`-bearing quad here is just a quad with
  a `:graph` key, not grouped into a graph-name -> graph map). For the
  spec-faithful Sec 4 model (exactly one default graph, zero or more named
  graphs, each graph a *set* of triples) see `rdf.dataset/dataset`, which
  this function's output composes with via `quads`."
  [quads]
  {:rdf/dataset (vec quads)})

(defn quads
  "The seq of quads in `dataset-or-quads`, whether it's a `dataset` map or
  already a bare seq of quads."
  [dataset-or-quads]
  (if (map? dataset-or-quads)
    (:rdf/dataset dataset-or-quads)
    dataset-or-quads))

(defn errors
  "Legacy ad hoc structural check on a single quad `q` — plain
  `{:error kw :value term}` maps, pre-dating this repo's adoption of
  `kotoba-lang/dsl-core`'s `kotoba.dsl.problem` convention. Kept unchanged
  for backward compatibility. It only checks term-*presence* in each role
  (subject/predicate/object/graph); it does not check the Sec 3.3
  language-tag/datatype constraint or the Sec 3.1 subject/predicate role
  constraints. Prefer `rdf.validate` for full spec-fidelity checking."
  [q]
  (cond-> []
    (not (term? (:subject q))) (conj {:error :rdf/invalid-subject :value (:subject q)})
    (not= :iri (:rdf/type (:predicate q))) (conj {:error :rdf/predicate-must-be-iri :value (:predicate q)})
    (not (term? (:object q))) (conj {:error :rdf/invalid-object :value (:object q)})
    (and (contains? q :graph) (not (term? (:graph q)))) (conj {:error :rdf/invalid-graph :value (:graph q)})))

(defn validate-quad
  "Legacy wrapper around `errors` for a single quad. See `rdf.validate` for
  full spec-fidelity checking."
  [q]
  (let [es (errors q)]
    {:valid? (empty? es) :errors es}))

(defn validate
  "Legacy wrapper around `errors` for a `dataset` or bare seq of quads. See
  `rdf.validate` for full spec-fidelity checking."
  [dataset-or-quads]
  (let [es (mapcat errors (quads dataset-or-quads))]
    {:valid? (empty? es) :errors (vec es)}))
