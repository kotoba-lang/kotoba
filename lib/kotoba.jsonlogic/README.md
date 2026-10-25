# kotoba-lang/jsonlogic

[![CI](https://github.com/kotoba-lang/jsonlogic/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/jsonlogic/actions/workflows/ci.yml)

Evaluate **JSONLogic rules-as-data** in portable Clojure — every namespace is `.cljc`,
with **zero third-party runtime deps**, so it runs on the JVM, ClojureScript, and
Clojure-on-WASM hosts (SCI). A rule is a plain string-keyed map (as returned by any
JSON parser); it evaluates against a data map or vector. The library adds the operator
evaluator, structural validation, and a host-injectable custom-operator protocol.

Sibling of other reusable kotoba-lang contract kernels such as
[`kotoba-lang/bpmn`](https://github.com/kotoba-lang/bpmn) and
[`kotoba-lang/dmn`](https://github.com/kotoba-lang/dmn).

## Why a shared library

The reusable rule evaluator lives in `kotoba-lang/jsonlogic`. It carries no
domain rules and no engine bindings; custom operators remain host-injected
ports.

## The evaluator: rules as data (`jsonlogic.core`)

A rule is a string-keyed map with exactly one key (the operator) whose value is the
argument list. A non-map (string, number, boolean, `nil`, vector) evaluates to itself:

```clojure
(require '[jsonlogic.core :as logic])

;; literal
(logic/apply-logic 42 {})                                      ;=> 42

;; variable lookup — dotted path, integer index, optional default
(logic/apply-logic {"var" "user.age"} {"user" {"age" 25}})     ;=> 25
(logic/apply-logic {"var" ["missing" "default"]} {})           ;=> "default"
(logic/apply-logic {"var" 1} [10 20 30])                       ;=> 20

;; comparison (loose == numeric-coercion; strict === type+value)
(logic/apply-logic {"==" [1 "1"]}  {})    ;=> true
(logic/apply-logic {"===" [1 "1"]} {})    ;=> false

;; control flow — and/or return the deciding value, not a boolean
(logic/apply-logic {"and" [1 true "last"]} {})   ;=> "last"
(logic/apply-logic {"and" [1 0 "three"]}   {})   ;=> 0
(logic/apply-logic {"or"  [false 0 "yes"]} {})   ;=> "yes"

(logic/apply-logic {"if" [{">" [{"var" "age"} 18]} "adult" "minor"]}
                   {"age" 25})            ;=> "adult"

;; arithmetic
(logic/apply-logic {"+" [1 2 3]} {})      ;=> 6
(logic/apply-logic {"-" [5]}    {})       ;=> -5   (unary minus)
(logic/apply-logic {"%" [7 3]}  {})       ;=> 1
(logic/apply-logic {"min" [5 1 3]} {})    ;=> 1

;; 3-arg between (< and <=)
(logic/apply-logic {"<" [1 2 3]} {})      ;=> true   (1 < 2 < 3)

;; string / collection
(logic/apply-logic {"in" ["ring" "Springfield"]} {})          ;=> true   (substring)
(logic/apply-logic {"in" [2 [1 2 3]]} {})                     ;=> true   (membership)
(logic/apply-logic {"cat" ["Hello" " " "World"]} {})          ;=> "Hello World"

;; higher-order — map / filter / reduce / all / some / none
(logic/apply-logic {"map"    [{"var" "nums"} {"*" [{"var" ""} 2]}]}
                   {"nums" [1 2 3]})                          ;=> [2 4 6]
(logic/apply-logic {"filter" [{"var" "nums"} {">" [{"var" ""} 2]}]}
                   {"nums" [1 2 3 4]})                        ;=> [3 4]
(logic/apply-logic {"reduce" [{"var" "nums"}
                               {"+" [{"var" "accumulator"} {"var" "current"}]}
                               0]}
                   {"nums" [1 2 3 4]})                        ;=> 10

;; missing / missing_some
(logic/apply-logic {"missing" ["a" "b"]} {"a" 1})             ;=> ["b"]
(logic/apply-logic {"missing_some" [1 ["a" "b"]]} {"a" 1})    ;=> []
```

`apply-logic` uses built-in operators only and throws on unknown operators.
`run` accepts a custom-operator port:

```clojure
(logic/run my-ports {"double" [21]} {})   ; dispatches "double" to my-ports
```

## Validation (`jsonlogic.validate`)

`problems` returns a vector of
`{:jsonlogic/severity :error|:warn :jsonlogic/code :jsonlogic/id :jsonlogic/msg}`;
`valid?` is true iff there are no `:error`s (warnings are advisory):

```clojure
(require '[jsonlogic.validate :as v])
(v/valid?   {"==" [1 1]})           ;=> true
(v/problems {"weirdOp" [1 2]})
;=> [{:jsonlogic/severity :warn :jsonlogic/code :op/unknown …}]
(v/valid?   {"weirdOp" [1 2]})      ;=> true  (warn only — may be a custom op)
```

Unknown operators produce a `:warn` (they may be handled by custom ports). Obvious
arity violations (e.g. `"var"` with >2 args) produce a `:warn`. Validation is
recursive: nested sub-rules are checked.

## Ports (`jsonlogic.ports`)

The host injects one protocol:

```
IOp  custom-op?  [this name]            — true if this host handles operator name
     apply-op    [this name args data]  — apply custom op; args are pre-evaluated
```

`default-ports` handles no custom operators (built-ins only). Use it with `run`, or
call `apply-logic` which wires it in automatically:

```clojure
(require '[jsonlogic.ports :as p]
         '[jsonlogic.core  :as logic])

(def my-ports
  (reify p/IOp
    (custom-op? [_ name] (= name "double"))
    (apply-op   [_ _name args _data] (* 2 (first args)))))

(logic/run my-ports {"double" [21]} {})   ;=> 42
```

## Test

```
kbb -M:test
```
