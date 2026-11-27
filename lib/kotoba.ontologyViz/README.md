# kotoba.ontologyViz

Portable, zero-dependency `.cljc` library for visualizing IPLD-backed Kotoba
ontologies across JVM Clojure, Babashka, nbb, and ClojureScript (Kotoba,
AwaiFS, Drive, and Yataverse).

## Design & Guarantees

- **`.cljc` only**: No `.cljk` sources; standard `#?(:clj ... :cljs ...)` reader
  conditionals throughout.
- **Zero external dependencies / offline-only**: No remote `@context` resolution,
  no external URL fetches, no external fonts or third-party CSS frameworks.
- **Byte-identical across runtimes**: Canonical number formatting (`fmt-num`)
  and sorted-key JSON ensure identical JSON, SVG, and HTML bytes across JVM
  Clojure, Babashka, and nbb.
- **Fail-closed safety bounds (enforced at every boundary)**:
  - Pre-count bounded checks (`bounded-count`) before realizing collections,
    plus explicit default limits and hard ceilings on nodes, edges, label length,
    scalar value length, nesting depth, collection width, joins, and attributes.
  - Caller-supplied normalized graphs are always re-validated (`validate-graph!`)
    by `render-svg`, `render-html`, `layout-graph`, `filter-graph`, `invoke`,
    and `->yataverse-graph` (strict `#RRGGBB` paint allowlist, finite positive
    layout dimensions, binary CIDv1 parsing).
  - Binary CIDv1 structure validation (`parse-cidv1`: canonical RFC4648 base32lower
    round-trip, shortest-form LEB128 varints, version=1, multicodec, recognized
    multihash + exact digest length). Because this library performs no block
    hashing on its own, `basis` explicitly records `:cid-verification :syntax-only`
    unless a caller passes an already digest-verified basis (`:verified`).
- **Semantic UI & Accessibility (G2)**:
  - Interactive HTML viewer exposes live machine-readable screen state via
    `data-screen-state` on `#kotoba-ontology-screen` and
    `window.__KOTOBA_ONTOLOGY_SCREEN__`, synchronized with browser controls and
    matching agent `filter-graph` / `inspect-node` semantics.
  - Full WAI-ARIA `tablist`/`tab`/`tabpanel` wiring (`aria-selected`,
    `aria-controls`, `aria-labelledby`, roving `tabindex`, and
    `ArrowLeft`/`ArrowRight`/`Home`/`End` navigation).
  - Standalone SVGs (`:interactive? false`, default) omit focusable
    `role="button"` on non-actionable graphics.

## Interoperability with Yataverse PR #83 (`yataverse.ontology.graph/v1`)

Kotoba's internal canonical model uses `ontology.graph/v1` (`:schema/version`,
`:schema/kind`, `:basis`, `:nodes`, `:edges` with `:source`/`:target`, `:layers`
with `:node-count`, `:joins`). Yataverse PR #83 uses the camelCase wire format
`yataverse.ontology.graph/v1` (`schema`, numeric `version`, `basisCid`, `layers`
with `nodeCount`, `nodes` with `meta`, `edges` with `from`/`to`/`meta`, `joins`,
`coverage`, `truncated`) and operation envelope `yataverse.ontology.operations/v1`.

Explicit bidirectional adapters bridge the two contracts without conflating them:

- `(ov/<-yataverse-graph yv-graph)` — validates and converts a Yataverse PR #83
  graph (keyword- or string-keyed) into a laid-out Kotoba `ontology.graph/v1`.
  `render-svg`, `render-html`, `invoke`, and `build-artifact` also accept a
  `yataverse.ontology.graph/v1` map directly via this adapter.
- `(ov/->yataverse-graph kotoba-graph)` — validates and converts a Kotoba
  `ontology.graph/v1` graph into Yataverse PR #83's exact `yataverse.ontology.graph/v1`
  wire format.
- `(ov/invoke-yataverse graph-or-yv op params)` — dispatches `ontology.graph`,
  `ontology.inspect`, `ontology.view` (`json|svg|html|all` -> `basisCid`,
  `semanticSchema`, `viewModel`, optional `svg`/`html`), `ontology.query_sql`
  (accepting `:query` or `:sql`), and `ontology.query_sparql` (accepting
  `:query` or `:sparql`) in the `yataverse.ontology.operations/v1` envelope.

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
    :datoms [[:tender/t-1 :jurisdiction/code "JP" 1001 true]
             [:country/jpn :country/iso3 "JPN" 1001 true]]
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

(:graph artifact)           ;; normalized ontology.graph/v1
(:yataverse-graph artifact) ;; Yataverse PR #83 yataverse.ontology.graph/v1
(:svg artifact)             ;; standalone offline SVG string
(:html artifact)            ;; self-contained interactive HTML5 viewer
(:screen-state artifact)    ;; initial Semantic UI screen state
(:semantic-schema artifact) ;; Semantic UI noun.verb contract
```

## Public API (`kotoba.ontology-viz`)

- `project-graph`, `evaluate-join`, `layout-graph`, `filter-graph`
- `yataverse-graph?`, `<-yataverse-graph`, `->yataverse-graph`, `invoke-yataverse`
- `render-svg`, `render-html`, `initial-screen-state`
- `semantic-schema`, `operation-names`, `invoke`, `build-artifact`
- `parse-cidv1`, `valid-cid?`, `ipld-link`, `ipld-link?`, `extract-cid`, `validate-graph!`
- `default-limits`, `hard-limits`, `resolve-limits`, `fmt-num`, `json-encode`, `json-for-script`

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
