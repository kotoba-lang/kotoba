# kotoba-lang/bpmn

[![CI](https://github.com/kotoba-lang/bpmn/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/bpmn/actions/workflows/ci.yml)

Handle **BPMN 2.0 as EDN/Clojure data** in portable Clojure — every namespace is
`.cljc`, with **zero third-party runtime deps**, so it runs on the JVM,
ClojureScript, and Clojure-on-WASM hosts (SCI). A BPMN process is plain data you can
`assoc`, `diff`, store in Datomic, or generate; the library adds the graph queries,
structural validation, XML I/O, and a pure token interpreter around it.

Sibling of other reusable kotoba-lang contract kernels.

## Why a shared library

The reusable process model lives in `kotoba-lang/bpmn`. It carries no domain
process and no engine bindings; those remain host-injected ports.

## The model: BPMN as EDN (`bpmn.model`)

Nodes and flows are id-keyed maps; topology comes from sequence-flow source/target,
never document order:

```clojure
{:bpmn/id "Order" :bpmn/type :process :bpmn/name "Order fulfilment" :bpmn/executable true
 :bpmn/nodes {"Start_received" {:bpmn/id "Start_received" :bpmn/type :start-event}
              "Gw_approved"    {:bpmn/id "Gw_approved" :bpmn/type :exclusive-gateway
                                :bpmn/default "Flow_reject"}
              "End_shipped"    {:bpmn/id "End_shipped" :bpmn/type :end-event} …}
 :bpmn/flows {"Flow_approve" {:bpmn/id "Flow_approve" :bpmn/type :sequence-flow
                              :bpmn/source "Gw_approved" :bpmn/target "Task_ship"
                              :bpmn/condition "${approved}"} …}}
```

A threading-friendly builder, plus graph queries (`outgoing`/`incoming` are ordered
by flow id, so runs are deterministic):

```clojure
(require '[bpmn.model :as m])

(def order
  (-> (m/process "Order" {:name "Order fulfilment"})
      (m/add :start-event "S" {:name "received"})
      (m/add :user-task "T" {:name "review"})
      (m/add :exclusive-gateway "G" {:default "Freject"})
      (m/add :end-event "Eok") (m/add :end-event "Eno")
      (m/connect "S" "T")
      (m/connect "T" "G")
      (m/connect "G" "Eok" {:id "Fapprove" :condition "${approved}"})
      (m/connect "G" "Eno" {:id "Freject"})))

(m/successors order "G")   ;=> ("Eok" "Eno")
```

## Validation (`bpmn.validate`)

`problems` returns a vector of `{:bpmn/severity :bpmn/code :bpmn/id :bpmn/msg}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[bpmn.validate :as v])
(v/valid? order)            ;=> true
(v/problems broken)         ;=> [{:bpmn/severity :error :bpmn/code :flow/dangling-target …}]
```

Errors: dangling flow refs, unknown node types, id/key mismatch. Warnings: no
start/end event, unconnected node, indeterminate exclusive gateway.

The safety-critical, closed structural subset is also implemented in
`bpmn.bounded-validate` as native `.kotoba`. It accepts a canonical integer graph
with at most four nodes and three flows, rejects malformed/non-canonical input,
and compiles directly to restricted JavaScript and Wasm without a JVM runtime.
Open BPMN concerns—string identifiers, the full node taxonomy, XML, messages, and
execution—remain in the portable `.cljc` model. The shared fixture matrix checks
that the bounded kernel produces the same error/warning counts as this validator.
The v1 ceiling is deliberately below the compiler's fixed, non-replenishable
512-call fuel limit and is exercised at the full 4/3 boundary in both targets.

## XML I/O (`bpmn.xml`)

```clojure
(require '[bpmn.xml :as xml])
(xml/parse-str (slurp "order.bpmn"))   ; BPMN 2.0 XML → model
(xml/emit-str order)                   ; model → BPMN 2.0 XML  (round-trips)
```

Zero-dep and portable: a **minimal reader/emitter** covers the well-formed BPMN
subset machine tools (bpmn.io, Camunda) emit — declaration, comments, attributes,
self-closing tags, text, the five entities; XML-namespace prefixes are stripped to
local names. It is **not** a general XML parser (no DTD/CDATA/PI). For exotic input,
inject your platform's parser output as *neutral elements*
(`{:tag "process" :attrs {…} :content […]}`) into `xml/from-elements` — e.g.
`clojure.data.xml` on the JVM or `DOMParser` on the web — and keep the rest.

## Execution (`bpmn.execute` + `bpmn.ports`)

A **pure, token-based interpreter**. State is plain data — inspectable, replayable,
testable offline. The host injects two ports (`bpmn.ports`):

```
IActivity   perform  [node vars] → vars'     — run a task / catch-throw event
ICondition  truthy?  [cond vars] → boolean   — evaluate a sequence-flow condition
```

Gateways: **exclusive** (first truthy condition → default → first flow), **parallel**
(AND-join + AND-split — waits for every incoming, then fires every outgoing),
**inclusive** (OR-split). `default-ports` make any model runnable with no host
(no-op activities; a condition reads the boolean process var it names):

```clojure
(require '[bpmn.execute :as e])
(-> (e/run (e/default-ports) order (e/start order {:approved true}))
    :bpmn/trace)        ; the per-step event log; ends at "Eok"
```

For real work, inject ports that call services and evaluate expressions; the
interpreter stays pure orchestration.

## Test

```
kbb -M:test
```
