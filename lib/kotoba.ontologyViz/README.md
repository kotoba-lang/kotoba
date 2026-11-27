# kotoba.ontologyViz

Portable, zero-dependency `.cljc` library for visualizing IPLD-backed Kotoba
ontologies across JVM Clojure, Babashka, nbb, and ClojureScript (Kotoba,
AwaiFS, Drive, and Yataverse).

## Design & Guarantees

- **`.cljc` only**: No `.cljk` sources; standard `#?(:clj ... :cljs ...)` reader
  conditionals throughout.
- **Zero external dependencies / offline-only**: No remote `@context` resolution,
  no external URL fetches, no external fonts or third-party CSS frameworks.
- **Fail-closed safety bounds**: Explicit default limits and hard ceilings on
  node count, edge count, label length, nesting depth, join count, and
  attributes per node. Malformed inputs and bound violations throw structured
  `ex-info` with an explicit `:reason`.
- **XSS-safe output**: Strict XML/HTML attribute & text escaping, control-char
  stripping, `<script type="application/json">` safe encoding, offline CSP, and
  `textContent`/`createElement`-only client-side DOM rendering.
- **Yataverse compatibility**: Emits the canonical `ontology.graph/v1` model
  (`nodes`, `edges`, `layers`, `joins`, `basis`, `layout`) and declares the
  Semantic UI `noun.verb` contract (`ontology.inspect`, `ontology.graph`,
  `ontology.view`, `ontology.query_sql`, `ontology.query_sparql`).

## Usage

```clojure
(require '[kotoba.ontology-viz :as ov])

(def root-cid "bafyreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku")

(def artifact
  (ov/build-artifact
   {:ontology {:kotoba.registry/id :kotoba/ontology
               :kotoba.registry/version 1
               :object-types
               [{:id :tender
                 :name "Procurement Tender / Opportunity"
                 :attributes {:status :keyword :jurisdiction/code :string}
                 :key [:status]
                 :cid (ov/ipld-link root-cid)}]}
    :connectors {:kotoba.registry/id :kotoba/ontology-connectors
                 :kotoba.registry/version 1
                 :connectors
                 [{:id :jp.kkj
                   :name "kkj.go.jp 官公需情報ポータル 検索API"
                   :object-type :tender
                   :repo "https://github.com/kotoba-lang/goyoukiki"
                   :status :implemented}]}
    :datoms [[:tender/t-1 :jurisdiction/code "JP" 1001]
             [:country/jpn :country/iso3 "JPN" 1001]]
    :joins [{:from-type :tender
             :from-attr :jurisdiction/code
             :to-type :country
             :to-attr :country/iso3
             :match-rule :mapping
             :mapping {"JP" "JPN"}
             :exclude #{"XX"}}]
    :basis {:root-cid root-cid
            :codec "dag-cbor"
            :source "kotoba.ontology"}}
   {:title "Procurement Ontology"}))

(:graph artifact)           ;; normalized ontology.graph/v1 map
(:svg artifact)             ;; standalone offline SVG string
(:html artifact)            ;; self-contained interactive HTML5 viewer
(:semantic-schema artifact) ;; Semantic UI noun.verb contract

;; Local Semantic UI dispatch:
(ov/invoke (:graph artifact) "ontology.inspect" {:node-id "type:tender"})
(ov/invoke (:graph artifact) "ontology.query_sql" {:sql "SELECT id, kind FROM nodes"})
(ov/invoke (:graph artifact) "ontology.query_sparql" {:sparql "SELECT ?s ?o WHERE { ?s rdf:type ?o }"})
```

## Public API (`kotoba.ontology-viz`)

- `project-graph` — normalize registries, Kotoba schemas, facts, EAVT datoms, RDF quads, joins, and IPLD nodes into `ontology.graph/v1`
- `evaluate-join` — pure external join coverage evaluator (`:exact`, `:exact-uppercase`, `:exact-lowercase`, `:prefix`, `:mapping`, `:exclude`)
- `layout-graph` — deterministic layered DAG layout (`:horizontal` / `:vertical`)
- `filter-graph` — pure layer / kind / substring filtering with re-layout
- `render-svg` — standalone zero-dependency SVG generator
- `render-html` — self-contained interactive HTML viewer generator
- `semantic-schema` / `operation-names` / `invoke` — Semantic UI `noun.verb` contract & local read-only dispatcher
- `build-artifact` — one-shot `{:graph :svg :html :semantic-schema}` builder
- `ipld-link`, `ipld-link?`, `extract-cid`, `valid-cid?`, `default-limits`, `hard-limits`, `resolve-limits`

## Running Tests

From `lib/kotoba.ontologyViz`:

```sh
# JVM Clojure
clojure -M:test -e '(load-file "test/run.cljc")'

# Babashka
bb test/run.cljc

# nbb (Node.js ClojureScript)
nbb test/run.cljc
```
