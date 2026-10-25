# Kotoba (`.kotoba`) — what you need to know to write one file

Kotoba is a small, safe, statically typed Lisp. It is NOT Clojure. It compiles
ahead-of-time to wasm/js/native. A `.kotoba` file is one module.

## Module form

```clojure
(ns my-core
  (:schemas {:my/point [:record :my/point [[:x :i64] [:y :i64]]]})  ; optional
  (:export [f g h]))
```

Only exported names are visible outside. `:schemas` declares record/variant
types used in this namespace.

## Functions — types are inline and MANDATORY

```clojure
(defn add [a :i64 b :i64] :i64 (+ a b))
(defn label [] :string "hello")
(defn ok? [flag :bool] :bool flag)
```

The form is `(defn name [param :type ...] :result-type body)`. There is no
metadata form (`^:i64`), no docstring slot, no multi-arity, no destructuring,
no varargs, no `&`.

Types: `:i64` `:i32` `:f64` `:bool` `:string` `[:option T]` `[:result T E]`
`[:ref :schema/name]`.

`:bool` is a real type, not a number. `0` is not false.

## Records

```clojure
(defn dist [p [:ref :my/point]] :i64
  (+ (record-get p :x) (record-get p :y)))

(record-new [:ref :my/point] 3 4)   ; positional, in declared field order
```

A function takes at most 5 parameters; when you need more inputs, the record
IS the argument list.

## Expressions available

`let` `if` `if-some` `do` `when` — `+ - * quot rem` — `< <= > >= =` —
`and or not` — `string-concat` `string-substring` `string=?` `string-length` —
`record-get` `record-new` — self/mutual recursion.

`(= a b)` works on `:i64` and `:bool`. Compare strings with `string=?`.

## Not available — do not use

No `throw` / `try` / `catch` — a function that can fail returns
`[:result T E]`. (This is a permanent language decision, not a gap.)
No `atom`, no host interop, no `require` of anything, no `map`/`filter`/`reduce`
over host collections, no `str`, no regex, no `nil` punning, no `loop/recur`,
no `defn-`, no `def`. Constants are zero-arg functions.

## Worked example — a real, landed decision core

```clojure
(ns overlay-peer-core
  (:schemas {:peer/via [:record :peer/via
                        [[:direct [:option :string]]
                         [:health :string]
                         [:relay [:option :string]]]]})
  (:export [choose-via health-unknown health-seen health-down
            via-direct via-relay]))

(defn health-unknown [] :string "unknown")
(defn health-down [] :string "down")
(defn via-direct [] :string "direct")
(defn via-relay [] :string "relay")

(defn choose-via [x [:ref :peer/via]] :string
  (if-some [_ (record-get x :direct)]
    (if (string=? (record-get x :health) (health-down))
      (if-some [_ (record-get x :relay)] (via-relay) "")
      (via-direct))
    (if-some [_ (record-get x :relay)]
      (via-relay)
      "")))
```

## What a port is FOR

You are extracting the **decision core** of a Clojure namespace: the arithmetic
and the judgement. Map/collection assembly, I/O, hashing and string parsing
stay in Clojure and are NOT part of your output. Port only the exports you are
asked for, with exactly the names, parameter types and result types requested.
