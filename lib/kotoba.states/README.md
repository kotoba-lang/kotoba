# states-clj (ステートマシン)

[![CI](https://github.com/kotoba-lang/states/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/states/actions/workflows/ci.yml)

Handle **AWS Step Functions ASL (Amazon States Language) as EDN/Clojure data** in
portable Clojure — every namespace is `.cljc`, with **zero third-party runtime deps**,
so it runs on the JVM, ClojureScript, and Clojure-on-WASM hosts (SCI). A state machine
is plain data you can `assoc`, `diff`, store in Datomic, or generate; the library adds
structural validation, JSON I/O, and a pure state-machine interpreter around it.

Sibling of the other reusable `*-clj` kernels in this org
([bpmn-clj](https://github.com/com-junkawasaki/bpmn-clj),
[dmn-clj](https://github.com/com-junkawasaki/dmn-clj),
[koe-clj](https://github.com/com-junkawasaki/koe-clj)).

## Why a shared library (org placement)

Per the three-org rule, the **reusable** state-machine kernel lives in
**com-junkawasaki**; **public-benefit actor instances** that drive concrete workflows
live in **etzhayyim**; any **business/private deployment** lives in **gftdcojp**.
states-clj is the dep — it carries no domain logic and no engine bindings (those are
host-injected ports).

## The model: ASL as EDN (`states.model`)

States are name-keyed maps; topology comes from `:states/next` / `:states/choices`
references, never from document order:

```clojure
{:states/comment  "Order pipeline"
 :states/start-at "Validate"
 :states/states
 {"Validate" {:states/type     :task
              :states/resource "arn:aws:lambda:us-east-1:123:function:Validate"
              :states/next     "Route"}
  "Route"    {:states/type    :choice
               :states/choices [{:states/variable "$.status"
                                  :states/op       :string-equals
                                  :states/value    "ok"
                                  :states/next     "Ship"}]
               :states/default "Reject"}
  "Ship"     {:states/type :succeed}
  "Reject"   {:states/type :fail}}}
```

Helper queries: `state-ids`, `state`, `start-at`, `terminal?` (succeed/fail or
`:states/end true`).

Types: `:task` `:choice` `:pass` `:wait` `:succeed` `:fail` `:parallel` `:map`.

## JSON I/O (`states.json`)

```clojure
(require '[states.json :as j])

;; ASL JSON (string-keyed, already parsed by your host's JSON lib) → EDN
(def machine (j/from-data (clojure.data.json/read-str (slurp "machine.asl.json"))))

;; EDN → ASL JSON map (pass to your host's JSON serialiser)
(j/to-data machine)
```

Key mappings: `"StartAt"` ↔ `:states/start-at`, `"States"` ↔ `:states/states`,
`"Type"` ↔ `:states/type` (keyword, lowercase), `"Next"` ↔ `:states/next`,
`"Choices"` ↔ `:states/choices` (choice rules with `:states/op`/`:states/value` pairs
for `NumericEquals`/`NumericGreaterThan`/`NumericLessThan`/`StringEquals`/`BooleanEquals`,
and `:states/and`/`:states/or`/`:states/not` for compound conditions).

## Validation (`states.validate`)

`problems` returns a vector of `{:states/severity :states/code :states/id :states/msg}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[states.validate :as v])
(v/valid? machine)    ;=> true
(v/problems broken)   ;=> [{:states/severity :error :states/code :states/invalid-next …}]
```

Errors: missing/unknown `StartAt`, invalid `Next`/`Default`/choice-`Next` references,
no reachable terminal state. Warnings: choice without `Default`
(`:states/choice-no-default`), unreachable states (`:states/unreachable`).

## Ports (`states.ports`)

```clojure
(defprotocol ITask
  (run [this state input-data] "state-map + input-data → output-data"))
```

Implement `ITask` to connect `:task` states to real Lambda invocations, HTTP calls,
or test stubs. The interpreter is pure over this interface — no I/O of its own.

## Execution (`states.execute`)

A **pure interpreter** for the state machine. Host injects an `ITask` implementation;
`default-ports` (identity) makes any machine runnable with no host:

```clojure
(require '[states.execute :as e])

;; With default (identity) ports:
(e/run machine {"x" 1})
;=> {:states/output {"x" 1} :states/path ["Route" "Y"] :states/status :succeeded}

;; With custom ITask:
(e/run machine input-data my-task-impl)
```

State semantics:
- `:task` — calls `ITask/run`, follows `:states/next` (or ends if `:states/end true`)
- `:pass` — merges `:states/result` into data, follows `:states/next`
- `:choice` — evaluates rules against data via `$.field` path getter; picks first
  matching `:states/next` else `:states/default`; compound `:and`/`:or`/`:not` supported
- `:wait` — no-op, follows `:states/next`
- `:succeed` — terminal, `:succeeded`
- `:fail` — terminal, `:failed`
- `:parallel` — runs each branch sub-machine, collects outputs into a vector
- `:map` — maps iterator sub-machine over items from `:states/items-path`

Returns `{:states/output <data> :states/path [state-names] :states/status :succeeded|:failed}`.

## Kotoba bounded profile

`src/states/bounded_model.kotoba` is a capability-free port of
`states.model`'s state-machine accessors, scoped to task states with a
single `:next` transition plus `:succeed`/`:fail` terminal states (the
shape `states.core-test`'s own `linear-machine` fixture uses).
`:choice`/`:parallel`/`:map` states and the full ASL interpreter
(`states.execute`) stay CLJC. Uses `kotoba-lang/compiler`'s canonical
bounded typed-map (`[:map :string ...]`, up to 31 entries, the same
primitive already production-qualified by `kotoba-lang/crdt`'s
CRDTs) to represent the state table. See
[migration/bounded-model-v1.edn](migration/bounded-model-v1.edn) for the
full record.

## Test

```
kbb -X:test
```
