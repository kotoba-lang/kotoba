(ns kotobase.protocols.sparql.ntriples
  "RDF 1.1 N-Triples serialization for CONSTRUCT and DESCRIBE results.

  CONSTRUCT and DESCRIBE return a GRAPH, not a solution table, so
  `application/sparql-results+json` does not apply to them — that format has no
  way to say \"these are triples\". N-Triples is the RDF format to reach for
  first: it is a REQUIRED serialization in the SPARQL 1.1 protocol, it is
  line-oriented so a large graph streams and diffs, and it needs no prefix
  bookkeeping, so there is nothing to get wrong between the writer and a
  reader.

  Turtle would be smaller and RDF/XML more traditional. Neither is implemented,
  and this namespace does not pretend to negotiate: the handler answers 406 for
  anything else rather than sending N-Triples under another content type."
  (:require [kotoba.lang.text :as str]))

(def content-type "application/n-triples")

(defn- escape
  "RDF 1.1 §7 ECHAR/UCHAR for a literal's lexical form. The five that MUST be
  escaped, and nothing else — a serializer that escapes more still parses, but
  a serializer that escapes less produces a document that does not."
  [v]
  (-> (str v)
      (str/replace "\\" "\\\\")
      (str/replace "\"" "\\\"")
      (str/replace "\n" "\\n")
      (str/replace "\r" "\\r")
      (str/replace "\t" "\\t")))

(defn- term->nt
  "One term. An IRI is angle-bracketed; anything else is written as a literal,
  with the numeric and boolean datatypes spelled out because an untyped `\"1\"`
  and an `xsd:integer` 1 are different terms and collapsing them would lose the
  distinction the store already made."
  [t]
  (let [v (:value t)]
    (if (= :iri (:rdf/type t))
      (str "<" (escape v) ">")
      (cond
        (boolean? v) (str "\"" v "\"^^<http://www.w3.org/2001/XMLSchema#boolean>")
        (integer? v) (str "\"" v "\"^^<http://www.w3.org/2001/XMLSchema#integer>")
        (number? v)  (str "\"" v "\"^^<http://www.w3.org/2001/XMLSchema#double>")
        :else (str "\"" (escape v) "\"")))))

(defn graph->ntriples
  "A set of quad maps -> an N-Triples document.

  Sorted, because the input is a SET and an unordered document would make two
  identical graphs serialize differently — which turns a diff or a cache key
  into noise. The order is not part of RDF's meaning; the determinism is for
  whoever has to read the output twice."
  [graph]
  (->> graph
       (map (fn [{:keys [subject predicate object]}]
              (str (term->nt subject) " " (term->nt predicate) " " (term->nt object) " .")))
       sort
       (str/join "\n")
       (#(if (str/blank? %) "" (str % "\n")))))
