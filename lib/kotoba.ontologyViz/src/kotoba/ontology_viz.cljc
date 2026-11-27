(ns kotoba.ontology-viz
  "Portable, zero-dependency `.cljc` library for projecting IPLD-backed Kotoba
  ontologies into Yataverse-compatible `ontology.graph/v1` models, standalone
  SVGs, self-contained interactive HTML viewers, and Semantic UI `noun.verb`
  contracts.

  Compatible with JVM Clojure, Babashka, nbb, and ClojureScript."
  (:require [kotoba.ontology-viz.escape :as esc]
            [kotoba.ontology-viz.graph :as g]
            [kotoba.ontology-viz.html :as html]
            [kotoba.ontology-viz.semantic :as sem]
            [kotoba.ontology-viz.svg :as svg]
            [kotoba.ontology-viz.validate :as v]))

;; ── Bounds & IPLD Link helpers ───────────────────────────────────────────────

(def default-limits v/default-limits)
(def hard-limits v/hard-limits)
(def resolve-limits v/resolve-limits)
(def valid-cid? v/valid-cid?)
(def ipld-link v/ipld-link)
(def ipld-link? v/ipld-link?)
(def extract-cid v/extract-cid)

;; ── Escaping & deterministic JSON ────────────────────────────────────────────

(def escape-xml esc/escape-xml)
(def escape-html esc/escape-html)
(def json-encode esc/json-encode)
(def json-for-script esc/json-for-script)

;; ── Graph projection, join coverage, layout & filtering ──────────────────────

(def schema-version g/schema-version)
(def project-graph g/project-graph)
(def evaluate-join g/evaluate-join)
(def layout-graph g/layout-graph)
(def filter-graph g/filter-graph)

;; ── Pure offline renderers ───────────────────────────────────────────────────

(def render-svg svg/render-svg)
(def render-html html/render-html)

;; ── Semantic UI (`noun.verb`) contract & local dispatcher ────────────────────

(def semantic-schema sem/schema)
(def operation-names sem/operation-names)

(defn invoke
  "Invoke a Semantic UI operation (`ontology.inspect`, `ontology.graph`,
  `ontology.view`, `ontology.query_sql`, `ontology.query_sparql`) against a
  normalized `ontology.graph/v1`."
  [graph op params]
  (sem/invoke graph op params {:render-html-fn html/render-html}))

(defn build-artifact
  "One-shot pure pipeline: project `input` into a normalized graph, render both
  standalone SVG and self-contained HTML viewer, and attach the Semantic UI
  operation schema."
  ([input] (build-artifact input {}))
  ([input opts]
   (let [graph (project-graph input)]
     {:graph graph
      :svg (render-svg graph opts)
      :html (render-html graph opts)
      :semantic-schema semantic-schema})))
