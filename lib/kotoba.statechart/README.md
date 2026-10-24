# kotoba-lang/statechart

[![CI](https://github.com/kotoba-lang/statechart/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/statechart/actions/workflows/ci.yml)

Handle **Harel statecharts / SCXML-subset as EDN/Clojure data** in portable Clojure —
every namespace is `.cljc`, with **zero third-party runtime deps**, so it runs on the
JVM, ClojureScript, and Clojure-on-WASM hosts (SCI). A chart is plain data you can
`assoc`, `diff`, store in Datomic, or generate; the library adds the structural queries,
validation, and a pure interpreter around it.

Sibling of other reusable kotoba-lang contract kernels such as
[`kotoba-lang/bpmn`](https://github.com/kotoba-lang/bpmn).

## Why a shared library

The reusable statechart kernel lives in `kotoba-lang/statechart`. It carries no
domain logic and no engine bindings; those remain host-injected ports.

## The model: charts as EDN (`statechart.model`)

States are id-keyed maps; topology comes from transition `:sc/target` values, never
document order. State types: `:atomic` (leaf), `:compound` (has `:sc/initial` + nested
`:sc/states`), `:parallel` (all child regions simultaneously active), `:final` (terminal).

```clojure
{:sc/id "door" :sc/initial "closed"
 :sc/states {"closed" {:sc/id "closed" :sc/type :atomic
                        :sc/on {"OPEN" [{:sc/target "open" :sc/cond "unlocked"
                                          :sc/actions ["beep"]}]}
                        :sc/entry ["enterClosed"] :sc/exit []}
             "open"   {:sc/id "open" :sc/type :atomic
                        :sc/on {"CLOSE" [{:sc/target "closed"}]}}}}
```

A threading-friendly builder (all functions compose via `->` / `add-state`):

```clojure
(require '[statechart.model :as m])

(def door
  (-> (m/chart "door" "closed")
      (m/add-state (-> (m/state "closed" {:sc/entry ["enterClosed"]
                                           :sc/exit  ["exitClosed"]})
                       (m/on "OPEN" {:sc/target "open" :sc/cond "unlocked"})))
      (m/add-state (-> (m/state "open")
                       (m/on "CLOSE" {:sc/target "closed"})))))

;; Compound (hierarchical) and parallel states:
(def traffic-light
  (-> (m/chart "light" "green")
      (m/add-state (-> (m/compound "green" "go")
                       (m/add-state (-> (m/state "go")
                                        (m/on "TICK" {:sc/target "slow"})))))
      (m/add-state (m/state "slow"))
      (m/add-state (-> (m/state "done") (assoc :sc/type :final)))))

;; Queries
(m/lookup door "closed")     ;=> {:sc/id "closed" :sc/type :atomic …}
(m/ancestors door "closed")  ;=> []
(m/all-states door)          ;=> {"closed" {…} "open" {…}}
```

## Validation (`statechart.validate`)

`problems` returns a vector of `{:sc/severity :error|:warn :sc/code … :sc/id … :sc/msg …}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[statechart.validate :as v])
(v/valid? door)     ;=> true
(v/problems broken) ;=> [{:sc/severity :error :sc/code :transition/dangling-target …}]
```

Errors: unknown `:sc/initial` ref, compound without `:sc/initial`, dangling
transition target. Warnings: unreachable states.

## Ports (`statechart.ports`)

The host injects two protocols:

```clojure
IAction  run    [this action-name ctx]  → ctx'    ; side-effect of state entry/exit
IGuard   allow? [this cond-name ctx]   → boolean  ; guard condition on a transition
```

## Execution (`statechart.execute` + `statechart.ports`)

A **pure interpreter**. Configuration is a set of active state ids (atomic states +
their compound/parallel ancestors). State is plain data — inspectable, replayable,
testable offline with fixture ports:

```clojure
(require '[statechart.execute :as e])

(def ports (e/default-ports))   ; no-op IAction; IGuard reads ctx keys by name

;; start: enter initial config, run entry actions
(def ms (e/start ports door {:unlocked true}))
;; => {:sc/config #{"closed"} :sc/ctx {:unlocked true} :sc/done? false}

;; send: find transition (innermost first, bubble to ancestors), run exit→tx→entry
(e/send ports door ms "OPEN")
;; => {:sc/config #{"open"} :sc/ctx {:unlocked true} :sc/done? false}

;; done?: true when any :final state is active
(e/done? (e/send ports door ms "FINISH"))  ;=> true
```

Entry actions run parent-first; exit actions run child-first. In a `:parallel` state,
all orthogonal regions activate on entry, and each region independently processes events.

Replace `default-ports` for real work — inject a host that evaluates expressions and
calls services; the interpreter stays pure orchestration.

## Test

```
kbb -M:test
```
