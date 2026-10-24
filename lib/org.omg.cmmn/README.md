# kotoba-lang/cmmn

[![CI](https://github.com/kotoba-lang/cmmn/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/cmmn/actions/workflows/ci.yml)

Handle **CMMN 1.1 cases as EDN/Clojure data** in portable Clojure — every namespace
is `.cljc`, with **zero third-party runtime deps**, so it runs on the JVM,
ClojureScript, and Clojure-on-WASM hosts (SCI). A case is plain data you can
`assoc`, `diff`, store in Datomic, or generate; the library adds the plan-item model,
structural validation, and a pure sentry-driven interpreter around it.

Completes the **OMG process-standards trio** alongside
[`kotoba-lang/bpmn`](https://github.com/kotoba-lang/bpmn) (structured flow
processes) and [`kotoba-lang/dmn`](https://github.com/kotoba-lang/dmn)
(decision tables).

## Why a shared library

The reusable case model lives in `kotoba-lang/cmmn`. It carries no domain
process and no engine bindings; those remain host-injected ports.

## The model: CMMN as EDN (`cmmn.model`)

Plan items are id-keyed maps; entry/exit criteria (sentries) are vectors on each item:

```clojure
{:cmmn/id "case"
 :cmmn/items
 {"t1" {:cmmn/id "t1" :cmmn/type :human-task
        :cmmn/entry-criteria [{:cmmn/on "m1" :cmmn/event :occur}]
        :cmmn/exit-criteria []}
  "m1" {:cmmn/id "m1" :cmmn/type :milestone
        :cmmn/entry-criteria [{:cmmn/on "t0" :cmmn/event :complete}]}
  "s1" {:cmmn/id "s1" :cmmn/type :stage
        :cmmn/children ["t1"]}}}
```

A threading-friendly builder:

```clojure
(require '[cmmn.model :as m])

(def order-case
  (m/case-model "order"
    (m/item "review"   :human-task)
    (m/item "approved" :milestone  :entry [(m/entry "review" :complete)])
    (m/item "ship"     :human-task :entry [(m/entry "approved" :occur
                                                    :if-cond "can-ship")])))
```

Plan-item types: `:human-task` `:process-task` `:stage` `:milestone` `:event-listener`.
A criterion (sentry) = `{:cmmn/on <item-id> :cmmn/event :complete|:occur|:terminate :cmmn/if <cond?>}`.

## Validation (`cmmn.validate`)

`validate` returns a vector of `{:cmmn/severity :error|:warn :cmmn/code :cmmn/id :cmmn/msg}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[cmmn.validate :as v])
(v/valid? order-case)        ;=> true
(v/validate broken)          ;=> [{:cmmn/severity :error :cmmn/code :criterion/dangling-ref …}]
```

Errors: unknown plan-item type, criterion referencing a non-existent item id, stage child
not found. Warnings: criterion cycles (self-ref, pairwise A↔B).

## Ports (`cmmn.ports`)

The host injects two protocols (`cmmn.ports`):

```
ITask   run     [item ctx]         — execute a task plan-item → ctx'
IGuard  allow?  [cond-string ctx]  — evaluate a sentry :cmmn/if guard → boolean
```

`default-ports` makes any case runnable with no host: ITask is identity; IGuard reads
`(get ctx (keyword cond-string))` — absent key → true (open guard).

## Execution (`cmmn.execute` + `cmmn.ports`)

A **pure, sentry-driven interpreter**. State is plain data — inspectable, replayable,
testable offline. A case starts with `start`; external events are applied with `raise`.
After each `raise` the engine evaluates sentries to a fixpoint, automatically activating
items whose entry-criteria are all satisfied. Milestones auto-complete on activation.

```clojure
(require '[cmmn.execute :as e])

(def pts (e/default-ports))
(def st  (e/start pts order-case {:can-ship true}))
(get-in st [:cmmn/states "review"])    ;=> :active  (no entry-criteria)
(def st2 (e/raise pts order-case st {:cmmn/item "review" :cmmn/event :complete}))
(get-in st2 [:cmmn/states "approved"]) ;=> :completed (milestone occurred)
(get-in st2 [:cmmn/states "ship"])     ;=> :active   (guard passed, sentry fired)
(e/done? st2)                          ;=> false (ship still active)
```

## Test

```
kbb -M:test
```
