# kotoba-lang/dmn

[![CI](https://github.com/kotoba-lang/dmn/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/dmn/actions/workflows/ci.yml)

Handle **DMN 1.4 decision tables and DRGs as EDN/Clojure data** in portable Clojure
— every namespace is `.cljc`, with **zero third-party runtime deps**, so it runs on
the JVM, ClojureScript, and Clojure-on-WASM hosts (SCI). A decision requirements
graph is plain data you can `assoc`, `diff`, store in Datomic, or generate; the
library adds the graph queries, structural validation, and a pure evaluator around
it.

Natural delegation target for a BPMN `business-rule-task` — sibling of
[`kotoba-lang/bpmn`](https://github.com/kotoba-lang/bpmn).

## Why a shared library

The reusable decision model lives in `kotoba-lang/dmn`. It carries no domain
rules and no engine bindings; those remain host-injected ports.

## The model: DRG as EDN (`dmn.model`)

Decisions are id-keyed maps; topology comes from `:dmn/requires` edges, never
document order:

```clojure
{:dmn/id "loan"
 :dmn/decisions
 {"risk"    {:dmn/id "risk" :dmn/hit-policy :first
             :dmn/inputs  [{:dmn/id "i1" :dmn/label "age"   :dmn/expr "age"}
                           {:dmn/id "i2" :dmn/label "score" :dmn/expr "score"}]
             :dmn/outputs [{:dmn/id "o1" :dmn/label "risk"}]
             :dmn/rules   [{:dmn/id "r1" :dmn/when ["> 18" ">= 700"] :dmn/then ["low"]}
                           {:dmn/id "r2" :dmn/when ["> 18" "-"]      :dmn/then ["medium"]}
                           {:dmn/id "r3" :dmn/when ["-"    "-"]      :dmn/then ["high"]}]}
  "approve" {:dmn/id "approve" :dmn/hit-policy :unique
             :dmn/requires ["risk"]
             :dmn/inputs  [{:dmn/id "i3" :dmn/label "risk" :dmn/expr "risk"}]
             :dmn/outputs [{:dmn/id "o2" :dmn/label "approved"}]
             :dmn/rules   [{:dmn/id "r4" :dmn/when ["low"]    :dmn/then [true]}
                           {:dmn/id "r5" :dmn/when ["medium"] :dmn/then [true]}
                           {:dmn/id "r6" :dmn/when ["high"]   :dmn/then [false]}]}}}
```

A threading-friendly builder, plus topo-order queries (deterministic — sorted by id
at each step):

```clojure
(require '[dmn.model :as m])

(def loan
  (-> (m/drg "loan")
      (m/add-decision (m/decision "risk" {:name "Risk" :hit-policy :first}))
      (m/add-input  "risk" "i1" {:label "age"   :expr "age"})
      (m/add-input  "risk" "i2" {:label "score" :expr "score"})
      (m/add-output "risk" "o1" {:label "risk"})
      (m/add-rule   "risk" "r1" ["> 18" ">= 700"] ["low"])
      (m/add-rule   "risk" "r2" ["> 18" "-"]       ["medium"])
      (m/add-rule   "risk" "r3" ["-"    "-"]        ["high"])
      (m/add-decision (m/decision "approve" {:hit-policy :unique :requires ["risk"]}))
      (m/add-input  "approve" "i3" {:label "risk" :expr "risk"})
      (m/add-output "approve" "o2" {:label "approved"})
      (m/add-rule   "approve" "r4" ["low"]    [true])
      (m/add-rule   "approve" "r5" ["medium"] [true])
      (m/add-rule   "approve" "r6" ["high"]   [false])))

(m/topo-order loan "approve")   ;=> ["risk" "approve"]
```

## Validation (`dmn.validate`)

`problems` returns a vector of `{:dmn/severity :error|:warn :dmn/code :dmn/id :dmn/msg}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[dmn.validate :as v])
(v/valid? loan)            ;=> true
(v/problems broken)        ;=> [{:dmn/severity :error :dmn/code :rule/when-arity …}]
```

Errors: when/then arity mismatch, unknown hit-policy, unknown `:dmn/requires` id,
DRG cycle. Warnings: `:unique` policy with multiple fully-unconditioned rules.

## Ports (`dmn.ports`)

The host injects two protocols (`dmn.ports`):

```
IExpression  eval-input  [expr context]         — evaluate an input expression → value
IUnary       eval-cell   [cell-str input-value]  — test a when-cell string → boolean
```

## Execution (`dmn.execute` + `dmn.ports`)

A **pure evaluator** — no I/O, no side effects. Evaluates the DRG in topological
order, merging each dependency's output into the context before evaluating the target
decision. Hit policies: `:unique`, `:first`, `:any`, `:collect`, `:priority`,
`:rule-order`. `default-ports` make any DRG runnable with no host:

```clojure
(require '[dmn.execute :as e])

(e/evaluate (e/default-ports) loan "approve" {:age 25 :score 750})
;=> {:dmn/outputs {:approved true}
;    :dmn/matched ["r4"]
;    :dmn/context {:age 25 :score 750 :risk "low"}}
```

`default-ports` cell evaluator supports: `"-"` wildcard, `< <= > >= = !=` comparators,
`[a..b]` / `(a..b)` / `[a..b)` / `(a..b]` ranges, `a,b,c` comma-disjunction, bare
number/string/boolean equality. Replace with a FEEL engine for production use.

## Test

```
kbb -M:test
```
