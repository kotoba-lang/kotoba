(ns rdf.validate
  "Structural validation of RDF terms, triples, and quads against RDF 1.1
  Concepts and Abstract Syntax (W3C Recommendation, 25 February 2014):
  https://www.w3.org/TR/rdf11-concepts/

  Returns `kotoba.dsl.problem`-shaped problems, domain `:rdf`:
  `{:rdf/severity :error|:warn :rdf/code kw :rdf/id subject :rdf/msg string}`

  This checks *structure* only (Sec 3 terms/triples, Sec 4 named-graph
  names) — it does not implement RDF's model-theoretic semantics
  (entailment, equivalence beyond term-equality, inconsistency; Sec 1.7,
  which the spec itself defers to a separate RDF 1.1 Semantics document).
  RDFS/OWL entailment-level checking belongs in `kotoba-lang/org-w3-owl2`,
  not here — this namespace never asks 'is this graph internally consistent
  under some vocabulary,' only 'is this term/triple/quad well-formed RDF.'"
  (:require [kotoba.lang.text :as str]
            [kotoba.dsl.problem :as problem]
            [rdf.core :as rdf]))

(defn- rdf-problem [severity code subject msg]
  (problem/problem :rdf severity code subject msg))

(defn- looks-absolute?
  "Heuristic only: does `s` start with an RFC 3987 `scheme:` prefix? This is
  not full RFC 3987 conformance checking (out of scope for a zero-dep
  library) — just enough to catch the common mistake of using a bare path
  or a CURIE where Sec 3.2 requires an absolute IRI."
  [s]
  (boolean (re-find #"^[a-zA-Z][a-zA-Z0-9+.\-]*:" s)))

(defn iri-problems
  "Sec 3.2: an IRI term must carry a non-empty string `:value`. Full RFC 3987
  syntax conformance is not checked; a `:warn` (not `:error`) is raised when
  the value has no scheme prefix, since a false positive here (e.g. an
  unusual-but-legal IRI scheme) shouldn't be treated as fatally malformed."
  [t]
  (let [v (:value t)]
    (cond
      (not (string? v))
      [(rdf-problem :error :iri/missing-value t "IRI term has no string :value")]

      (str/blank? v)
      [(rdf-problem :error :iri/blank-value t "IRI term :value is blank")]

      (not (looks-absolute? v))
      [(rdf-problem :warn :iri/looks-relative t
                    (str "IRI \"" v "\" has no scheme prefix — Sec 3.2 requires "
                         "IRIs in RDF's abstract syntax to be absolute"))]

      :else [])))

(defn blank-problems
  "Sec 3.4: a blank node term must carry an `:id` (RDF gives blank nodes no
  internal structure, but this library needs *some* identifier to tell two
  blank node terms apart, so a missing `:id` is malformed here)."
  [t]
  (if (nil? (:id t))
    [(rdf-problem :error :blank/missing-id t "blank node term has no :id")]
    []))

(defn literal-problems
  "Sec 3.3: a literal is a lexical form (string) + a datatype IRI, plus a
  language tag if and only if that datatype IRI is exactly
  `rdf.core/rdf-lang-string`. Checks both directions of that iff — either
  direction being violated makes the literal malformed:
  - a `:language` present together with a `:datatype` other than
    rdf:langString,
  - a rdf:langString `:datatype` with no `:language`,
  - no `:datatype` at all (whether or not `:language` is present) — every
    literal has one per the abstract syntax; `rdf.core/literal` defaults it
    correctly, but a hand-built literal map can still omit it.
  Also flags a present-but-blank `:language`."
  [t]
  (let [lex  (:value t)
        dt   (:datatype t)
        dt-iri? (and (map? dt) (= :iri (:rdf/type dt)) (string? (:value dt)))
        lang (:language t)]
    (cond-> []
      (not (string? lex))
      (conj (rdf-problem :error :literal/missing-value t
                         "literal has no string :value (lexical form)"))

      (not dt-iri?)
      (conj (rdf-problem :error :literal/missing-datatype t
                         "literal has no datatype IRI — Sec 3.3: every literal has one (build via rdf.core/literal so xsd:string/rdf:langString default correctly)"))

      (and lang (not (string? lang)))
      (conj (rdf-problem :error :literal/language-not-string t
                         "literal :language is present but not a string"))

      (and lang (string? lang) (str/blank? lang))
      (conj (rdf-problem :error :literal/blank-language t
                         "literal :language is present but blank"))

      (and lang dt-iri? (not= rdf/rdf-lang-string (:value dt)))
      (conj (rdf-problem :error :literal/language-datatype-mismatch t
                         (str "literal has :language \"" lang "\" but :datatype "
                              (:value dt) " — Sec 3.3 permits a language tag "
                              "only when the datatype is exactly rdf:langString")))

      (and (not lang) dt-iri? (= rdf/rdf-lang-string (:value dt)))
      (conj (rdf-problem :error :literal/langstring-missing-language t
                         "literal :datatype is rdf:langString but has no :language — Sec 3.3 requires a non-empty language tag in that case")))))

(defn term-problems
  "Dispatches to `iri-problems`/`blank-problems`/`literal-problems` by
  `:rdf/type`; a value that isn't a recognized term at all is one error."
  [t]
  (cond
    (not (rdf/term? t))
    [(rdf-problem :error :term/malformed t
                  "not a recognized RDF term ({:rdf/type :iri|:blank|:literal, ...})")]

    (= :iri (:rdf/type t)) (iri-problems t)
    (= :blank (:rdf/type t)) (blank-problems t)
    (= :literal (:rdf/type t)) (literal-problems t)))

(defn triple-problems
  "Sec 3.1: subject ∈ {IRI, blank node}; predicate = IRI; object ∈ {IRI,
  blank node, literal}. Only *standard* RDF triples are accepted here — Sec 7
  'Generalized RDF Triples' (literals-as-subject, blank-nodes-as-predicate,
  etc.) are explicitly non-standard extensions, so this flags them as errors
  rather than silently accepting them."
  [{:keys [subject predicate object] :as trip}]
  (vec
   (concat
    (term-problems subject)
    (when (and (rdf/term? subject) (= :literal (:rdf/type subject)))
      [(rdf-problem :error :triple/literal-subject trip
                    "subject is a literal — Sec 3.1 only allows an IRI or blank node subject (this is a \"generalized RDF triple\", Sec 7, a non-standard extension)")])

    (term-problems predicate)
    (when (and (rdf/term? predicate) (not= :iri (:rdf/type predicate)))
      [(rdf-problem :error :triple/predicate-not-iri trip
                    "predicate must be an IRI — Sec 3.1 (this is a \"generalized RDF triple\", Sec 7, a non-standard extension)")])

    (term-problems object))))

(defn quad-problems
  "`triple-problems` plus, when a `:graph` key is present, Sec 4's
  constraint that a named graph's name is an IRI or a blank node (never a
  literal)."
  [{:keys [graph] :as q}]
  (vec
   (concat
    (triple-problems q)
    (when (contains? q :graph)
      (concat
       (term-problems graph)
       (when (and (rdf/term? graph) (= :literal (:rdf/type graph)))
         [(rdf-problem :error :quad/literal-graph-name q
                       "graph name is a literal — Sec 4 requires an IRI or a blank node")]))))))

(defn problems
  "All structural problems across `quads` (a seq of triple/quad maps — e.g.
  `(rdf.core/quads dataset-or-quads)` or `(rdf.dataset/all-quads dataset)`)."
  [quads]
  (vec (mapcat quad-problems quads)))

(defn errors
  "Problems of `:error` severity only, across `quads`."
  [quads]
  (problem/errors :rdf (problems quads)))

(defn warnings
  "Problems of `:warn` severity only, across `quads`."
  [quads]
  (problem/warnings :rdf (problems quads)))

(defn valid?
  "True iff `quads` has no `:error`-level structural problems (warnings are
  advisory)."
  [quads]
  (problem/valid? :rdf (problems quads)))
