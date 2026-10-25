(ns kotobase.protocols.sparql.results
  "`sparql.core/select`/`sparql.core/ask` results -> the SPARQL 1.1 Query
  Results JSON Format (https://www.w3.org/TR/sparql11-results-json/) --
  the one content-negotiated format v0.1 of this repo produces (see the
  main `kotobase.protocols.sparql` ns docstring for why XML/CSV are out of
  scope for v0.1).

  A `sparql.core/select` result row is a plain Clojure map from `'?var`
  symbol to a term map (`{:rdf/type :iri :value ...}` or `{:rdf/type
  :literal :value ...}`, see `kotobase.protocols.sparql.quads`). This ns
  turns that into the JSON-shaped EDN the spec's `results.bindings[i]`
  wants: `{\"s\" {\"type\" \"uri\" \"value\" \"...\"}, ...}`.")

(def ^:private xsd "http://www.w3.org/2001/XMLSchema#")

(defn- literal-datatype
  "Best-effort XSD datatype IRI for a literal's raw `:value`, derived from
  its runtime type (the term itself carries no datatype tag -- see
  `kotobase.protocols.sparql.quads` for why). `nil` for plain strings (the
  JSON Results spec's `literal` binding needs no `datatype` key at all for
  a plain string -- omitting it, not emitting `xsd:string`, is the
  spec-conformant default)."
  [v]
  (cond
    (true? v) (str xsd "boolean")
    (false? v) (str xsd "boolean")
    #?(:clj (integer? v) :cljs (and (number? v) (integer? v))) (str xsd "integer")
    (number? v) (str xsd "double")
    :else nil))

(defn term->binding
  "One `kotobase.protocols.sparql.quads` term map -> the JSON Results
  Format's per-variable binding object (still EDN here -- `encode` is a
  separate final step in the HTTP handler)."
  [{:keys [rdf/type value] :as term}]
  (case type
    :iri {"type" "uri" "value" (str value)}
    :literal (let [dt (literal-datatype value)]
               (cond-> {"type" "literal" "value" (str value)}
                 dt (assoc "datatype" dt)))
    (throw (ex-info "unrecognized RDF term" {:term term}))))

(defn- binding-row->json [row]
  (into {} (map (fn [[var-sym term]] [(subs (name var-sym) 1) (term->binding term)])) row))

(defn select->json
  "`output-vars` (a seq of `'?var` symbols, in `head.vars` order -- `nil`
  falls back to the union of every var seen across `rows`, first-seen
  order, for `SELECT *`) + `rows` (the seq/vec `sparql.core/select`
  returns) -> the full SPARQL JSON Results Format EDN structure (still
  needs `kotobase.protocols.sparql.json/encode` to become a JSON string)."
  [output-vars rows]
  (let [vars (or (seq (map #(subs (name %) 1) output-vars))
                 (distinct (mapcat (fn [row] (map #(subs (name %) 1) (keys row))) rows)))]
    {"head" {"vars" (vec vars)}
     "results" {"bindings" (mapv binding-row->json rows)}}))

(defn ask->json
  "`sparql.core/ask`'s boolean -> the SPARQL JSON Results Format's ASK
  shape: `{\"head\": {}, \"boolean\": <bool>}`."
  [bool-result]
  {"head" {} "boolean" (boolean bool-result)})
