(ns rdf.dataset
  "RDF Datasets, per Sec 4 of RDF 1.1 Concepts and Abstract Syntax (W3C
  Recommendation, 25 February 2014):
  https://www.w3.org/TR/rdf11-concepts/#section-dataset

  Sec 4: 'An RDF dataset is a collection of RDF graphs, and comprises:
  - Exactly one default graph... The default graph does not have a name...
  - Zero or more named graphs. Each named graph is a pair consisting of an
    IRI or a blank node (the graph name), and an RDF graph.'
  Sec 3: 'An RDF graph is a set of RDF triples' — sets, not lists, so
  duplicate triples collapse and order is not significant.

  A Dataset here is `{:default #{triple ...} :graphs {graph-name #{triple
  ...}}}`, distinct from `rdf.core/dataset` (a flat, ungrouped, non-deduped
  bag of quads that predates this namespace and is kept for backward
  compatibility). Build one from a seq of `rdf.core/triple`/`rdf.core/quad`
  maps with `dataset`; a quad with no `:graph` key contributes to the
  default graph, one with a `:graph` key contributes to the named graph
  keyed by that graph name term."
  (:require [rdf.core :as rdf]))

(def empty-dataset
  "An RDF dataset with an empty default graph and no named graphs."
  {:default #{} :graphs {}})

(defn- as-triple
  "Strips `:graph` (if any) so the stored triple is exactly
  `{:subject :predicate :object}` — a graph is a set of *triples*, not quads;
  the graph name lives in the dataset's `:graphs` map key, not on the triple
  itself."
  [q]
  (select-keys q [:subject :predicate :object]))

(defn add
  "Adds one triple/quad `q` to dataset `ds`, returning the updated dataset. A
  `q` with no `:graph` key (or `:graph nil`) goes into the default graph; one
  with a `:graph` key goes into the named graph keyed by that graph name
  term (creating it if it doesn't already exist)."
  [ds q]
  (let [t (as-triple q)]
    (if (contains? q :graph)
      (update-in ds [:graphs (:graph q)] (fnil conj #{}) t)
      (update ds :default (fnil conj #{}) t))))

(defn dataset
  "Builds a Dataset from a seq of triple/quad maps (see `add`)."
  [quads]
  (reduce add empty-dataset quads))

(defn default-graph
  "The dataset's default graph: a set of triples."
  [ds]
  (:default ds empty-dataset))

(defn graph-names
  "The set of named-graph-name terms present in `ds` (each an IRI or blank
  node term per Sec 4 — see `rdf.validate/quad-problems` to check that)."
  [ds]
  (set (keys (:graphs ds))))

(defn named-graph
  "The named graph in `ds` named by graph-name term `g` — a set of triples,
  or an empty set if `ds` has no graph named `g`."
  [ds g]
  (get-in ds [:graphs g] #{}))

(defn graph
  "Sec 4 graph lookup by name: the default graph when `g` is `nil`,
  otherwise the named graph for `g` (or an empty set if absent)."
  [ds g]
  (if (nil? g)
    (default-graph ds)
    (named-graph ds g)))

(defn all-triples
  "The set union of every triple in `ds` — the default graph's triples plus
  every named graph's triples, with duplicates across graphs collapsed
  (consistent with each graph itself being a *set*, Sec 3). This flattens
  away which graph each triple came from; use `named-graph`/`default-graph`
  when that distinction matters."
  [ds]
  (reduce into (default-graph ds) (vals (:graphs ds))))

(defn all-quads
  "Reconstructs a flat seq of quad maps from `ds`: default-graph triples as
  bare triples (no `:graph` key), plus each named graph's triples annotated
  with `:graph` = that graph's name term. Round-trips with `dataset`/`add`
  and is the shape `rdf.validate/problems` expects."
  [ds]
  (concat (seq (default-graph ds))
          (mapcat (fn [[g ts]] (map #(assoc % :graph g) ts)) (:graphs ds))))

(defn- term-seq
  "All term values at `k` (`:subject`/`:predicate`/`:object`) across every
  triple in `ds`, default graph and named graphs alike."
  [ds k]
  (into #{} (map k) (all-triples ds)))

(defn subjects
  "The set of distinct subject terms appearing anywhere in `ds`."
  [ds] (term-seq ds :subject))

(defn predicates
  "The set of distinct predicate terms appearing anywhere in `ds`."
  [ds] (term-seq ds :predicate))

(defn objects
  "The set of distinct object terms appearing anywhere in `ds`."
  [ds] (term-seq ds :object))
