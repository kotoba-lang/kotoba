(ns kotoba.ontology-viz
  "Portable, zero-dependency `.cljc` library for projecting IPLD-backed Kotoba
  ontologies into canonical `ontology.graph/v1` models, bidirectional Yataverse
  PR #83 `yataverse.ontology.graph/v1` wire adapters, standalone SVGs,
  self-contained interactive HTML viewers, and Semantic UI `noun.verb` contracts.

  Compatible with JVM Clojure, Babashka, nbb, and ClojureScript."
  (:require [kotoba.ontology-viz.dag-cbor :as dcbor]
            [kotoba.ontology-viz.escape :as esc]
            [kotoba.ontology-viz.graph :as g]
            [kotoba.ontology-viz.html :as html]
            [kotoba.ontology-viz.semantic :as sem]
            [kotoba.ontology-viz.svg :as svg]
            [kotoba.ontology-viz.validate :as v]
            [kotoba.ontology-viz.yataverse :as yv]))

;; ── Bounds, Validation & Binary CIDv1 / IPLD Link helpers ────────────────────

(def default-limits v/default-limits)
(def hard-limits v/hard-limits)
(def resolve-limits v/resolve-limits)
(def parse-cidv1 v/parse-cidv1)
(def valid-cid? v/valid-cid?)
(def ipld-link v/ipld-link)
(def ipld-link? v/ipld-link?)
(def extract-cid v/extract-cid)
(defn validate-graph!
  "Fail-closed validation of a normalized `ontology.graph/v1` map, including
  cryptographic canonical DAG-CBOR digest verification whenever
  `:graph-cid-verification :verified` is declared."
  [graph]
  (v/validate-graph! graph {:verify-graph-cid-fn yv/verify-normalized-graph-cid!}))

;; ── Escaping, Canonical Number Formatting & Deterministic JSON ───────────────

(def escape-xml esc/escape-xml)
(def escape-html esc/escape-html)
(def fmt-num esc/fmt-num)
(def json-encode esc/json-encode)
(def json-for-script esc/json-for-script)

;; ── Graph projection, join coverage, layout & filtering ──────────────────────

(def schema-version g/schema-version)
(def project-graph g/project-graph)
(def evaluate-join g/evaluate-join)
(defn layout-graph
  "Assign deterministic layered coordinates to a validated `ontology.graph/v1` graph."
  ([graph] (layout-graph graph {}))
  ([graph opts]
   (g/layout-graph graph opts {:verify-graph-cid-fn yv/verify-normalized-graph-cid!})))

(defn filter-graph
  "Validate and filter a normalized `ontology.graph/v1` graph by `:layers`, `:kinds`, and/or `:query`."
  [graph params]
  (g/filter-graph graph params {:verify-graph-cid-fn yv/verify-normalized-graph-cid!}))

;; ── Explicit Bidirectional Yataverse PR #83 Wire Adapters ────────────────────

(def yataverse-graph-schema yv/yataverse-graph-schema)
(def yataverse-operations-schema yv/yataverse-operations-schema)
(def yataverse-graph? yv/yataverse-graph?)
(def <-yataverse-graph yv/<-yataverse-graph)
(def ->yataverse-graph yv/->yataverse-graph)
(def encode-dag-cbor dcbor/encode-dag-cbor)
(def decode-dag-cbor dcbor/decode-dag-cbor)
(def validate-dag-cbor dcbor/validate-dag-cbor)
(def validate-dag-cbor! dcbor/validate-dag-cbor!)
(def encode-ontology-graph-dag-cbor dcbor/encode-ontology-graph-dag-cbor)
(def cidv1-dag-cbor dcbor/cidv1-dag-cbor)

;; ── Pure offline renderers & machine-readable screen state ───────────────────

(def render-svg svg/render-svg)
(def render-html html/render-html)
(def initial-screen-state html/initial-screen-state)

;; ── Semantic UI (`noun.verb`) contract & local dispatchers ───────────────────

(def semantic-schema sem/schema)
(def operation-names sem/operation-names)

(defn invoke
  "Invoke a Semantic UI operation (`ontology.inspect`, `ontology.graph`,
  `ontology.view`, `ontology.query_sql`, `ontology.query_sparql`) against a
  validated `ontology.graph/v1` or Yataverse `yataverse.ontology.graph/v1` graph."
  [graph-or-yv op params]
  (sem/invoke graph-or-yv op params {:render-html-fn html/render-html}))

(defn invoke-yataverse
  "Invoke a Yataverse PR #83-compatible `noun.verb` operation returning the
  `yataverse.ontology.operations/v1` envelope (`basisCid`, `viewModel`,
  `yataverse.ontology.graph/v1`, etc.)."
  [graph-or-yv op params]
  (sem/invoke-yataverse graph-or-yv op params {:render-html-fn html/render-html}))

(defn build-artifact
  "One-shot pure pipeline: project `input` (or adapt a Yataverse PR #83 graph)
  into a validated normalized graph, render standalone SVG and self-contained
  HTML viewer, attach the Semantic UI schema, initial screen state, and
  Yataverse wire projection."
  ([input] (build-artifact input {}))
  ([input opts]
   (let [graph (svg/normalize-and-validate-graph input)]
     {:graph graph
      :yataverse-graph (->yataverse-graph graph)
      :svg (render-svg graph opts)
      :html (render-html graph opts)
      :screen-state (initial-screen-state graph)
      :semantic-schema semantic-schema})))
