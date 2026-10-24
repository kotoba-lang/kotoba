# dot-clj (グラフ記述)

[![CI](https://github.com/kotoba-lang/dot/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/dot/actions/workflows/ci.yml)

Handle **Graphviz DOT language as EDN/Clojure data** in portable Clojure — every
namespace is `.cljc`, with **zero third-party runtime deps**, so it runs on the JVM,
ClojureScript, and Clojure-on-WASM hosts (SCI). A DOT graph is plain data you can
`assoc`, `diff`, store in Datomic, or generate; the library adds the graph model,
graph algorithms, structural validation, and DOT string I/O around it.

The EDN graph model is the data layer; the sibling
[svgraph](https://github.com/com-junkawasaki/svgraph) library renders it to SVG.
Other reusable kernels in this org:
([bpmn-clj](https://github.com/com-junkawasaki/bpmn-clj),
[koe-clj](https://github.com/com-junkawasaki/koe-clj)).

## Why a shared library (org placement)

Per the three-org rule, the **reusable** graph model lives in **com-junkawasaki**;
**public-benefit actor instances** that use graphs for visualisation or analysis live
in **etzhayyim**; any **business/private deployment** lives in **gftdcojp**. dot-clj
carries no domain logic — it is a format library plus graph algorithms (no renderer,
no interpreter).

## The model: DOT graph as EDN (`dot.model`)

Nodes are id-keyed for O(1) lookup; edges are an ordered vector (DOT order matters
for rendering); graph attrs are a string→string map:

```clojure
{:dot/id "G" :dot/strict false :dot/directed true
 :dot/graph-attrs {"rankdir" "LR"}
 :dot/nodes {"a" {:dot/id "a" :dot/attrs {"shape" "box"}}
             "b" {:dot/id "b" :dot/attrs {}}}
 :dot/edges [{:dot/from "a" :dot/to "b" :dot/attrs {"label" "x"}}]}
```

A threading-friendly builder plus graph algorithms:

```clojure
(require '[dot.model :as m])

(def pipeline
  (-> (m/digraph "pipeline" {:strict true})
      (m/node "source" {"shape" "box"})
      (m/edge "source" "transform" {"label" "raw"})
      (m/edge "transform" "sink"   {"label" "clean"})))

(m/successors pipeline "source")   ;=> #{"transform"}
(m/topo-order pipeline)            ;=> ["source" "transform" "sink"]
(m/roots pipeline)                 ;=> #{"source"}
(m/leaves pipeline)                ;=> #{"sink"}
(m/reachable pipeline "source")    ;=> #{"source" "transform" "sink"}
```

Graph algorithms: `neighbors`, `out-edges`, `in-edges`, `successors`,
`predecessors`, `roots`, `leaves`, `reachable`, `topo-order`
(Kahn's algorithm; returns `{:dot/cycle true}` for cyclic graphs — no throw).

## Validation (`dot.validate`)

`problems` returns a vector of `{:dot/severity :dot/code :dot/id :dot/msg}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[dot.validate :as v])
(v/valid? pipeline)     ;=> true
(v/problems g-with-wrong-op)
;=> [{:dot/severity :error :dot/code :edge/wrong-operator …}]
```

Errors: wrong edge operator (`--` in a digraph or `->` in an undirected graph).
Warnings: self-loop on a node.

## DOT I/O (`dot.dot`)

```clojure
(require '[dot.dot :as d])
(d/parse-str (slurp "pipeline.dot"))   ; DOT string → model
(d/emit-str pipeline)                  ; model → canonical DOT string  (round-trips)
```

Zero-dep and portable: a **minimal tokeniser/parser** covers the well-formed DOT
subset — `strict? (digraph|graph) id { stmts }`:

- node: `a [k=v, ...];`
- edge: `a -> b -> c [k=v];`  (`--` for undirected; chains produce one edge per hop)
- graph attr: `rankdir=LR;`
- default-attr block: `node [shape=box];` / `edge [color=red];` (apply to subsequently-declared nodes/edges)
- quoted ids `"a b"`, `//` and `/* */` comments, optional `;`

`emit-str` produces canonical DOT (graph attrs, then nodes sorted by id, then edges
in declaration order) that round-trips through `parse-str`.

**Limitations**: no subgraphs/clusters, no HTML labels (`<...>`), no ports (`:port`),
no compass points. Attribute values must be string scalars.

## Test

```
kbb -M:test
```
