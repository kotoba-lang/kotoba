# 0257 — an i64 order that ClojureScript can compute

Status: accepted
Date: 2026-09-02

## What was measured

`kotoba.kir.value/compare-typed-values` is the language-owned total order.
Every ordered i64 collection goes through it: `[:set :i64]`, `[:map :i64 V]`,
and the payload inside `:option-i64` / `:result-i64`, plus every sequence-shaped
type that reaches `:i64` through `compare-sequences` (`:vector-i64`,
`:string-index`, `:disjoint-set-i64`, and the legacy `:map`, whose values are
i64).

It reached that order through `clojure.core/compare`. On ClojureScript an i64
read from `.kotoba` source is a JS BigInt, which is neither `number?` nor
`IComparable`, so `compare` falls through to its final arm and throws:

    Cannot compare 2 to 1

Measured 2026-09-02 under nbb, at `origin/main`:

| value | before | after |
|---|---|---|
| `(compare-typed-values :i64 1n 2n)` | throws | `-1` |
| `[:set :i64]` with two items | throws | sorted |
| `[:map :i64 :i64]` with two entries | throws | sorted |
| duplicate i64 key | throws `Cannot compare 1 to 1` | `typed map contains a duplicate key` |

The JVM was unaffected throughout, which is why nothing here had ever seen it:
every test that touched this order was `.clj`. Same class as ADR 0212's
`uleb`, and found the same way.

## Where it did the damage

Not in the KIR interpreter, where it looks like what it is. `amu compile
--target wasm32` evaluates the oracle through `lower`, and `lower` validates
every typed value, so a `[:map :i64 :i64]` carrying two entries exited **70**
with `internal compiler error` — which reads as a missing wasm lowering, and
was very nearly recorded as one.

Two facts identify it as a comparator rather than a backend:

- **one** entry compiled and **two** did not (a one-element sort never calls
  the comparator);
- `:bool`, `:string` and `:keyword` keys compiled at every entry count, and
  those are exactly the key types whose branch does not call `compare` on a
  bigint.

## The order

`<` and `>` are JS operators and do work on BigInt — `kotoba.kir.cljs-i64`
already relies on that — so `compare-i64` is spelled with those on `:cljs` and
stays `compare` on `:clj`. JavaScript compares a BigInt against a Number
numerically, which is required: the desugarer synthesizes plain numbers (`get`'s
default `0`, `when`'s trailing `0`) and the reader produces bigints, so the two
representations do meet inside one collection.

The order is **signed**. A comparator reading two's-complement bit patterns as
unsigned would sort `-1` above every positive value; `the-order-is-signed`
pins that.

## What is pinned

`test/kotoba/kir_i64_order_test.cljk`, in both lists of `run-tests.cljk`.
Before the fix it reports 13 errors on nbb and passes on the JVM; after, both
runtimes are green. The duplicate-key case asserts the MESSAGE rather than
merely that something was thrown — the old behaviour threw too, and a test that
only asserted a throw would have passed for the wrong reason.
