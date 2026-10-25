# ADR-0001: increment 2 — keyed-blob entity pair, portable clock, ledger record

**Status**: accepted
**Date**: 2026-08-05
**Supersedes**: nothing. Extends the extraction decided in
com-junkawasaki/root `ADR-2607141600` (store-seam commonalization).
**Driven by**: com-junkawasaki/root `ADR-2608052000` (fleet maturity /
dependency system-dynamics), which measured this repo as one of the three
highest-leverage repos in the fleet.

## Context

`ADR-2608052000` scored all 1,720 `cloud-itonami` repos plus their
cross-org substrate dependencies and computed, by perturbation over the
real dependency graph, how much the fleet-wide score moves per unit of work
on each repo. This repo came out with the largest single fleet gain
(21.8 points of a ~530-point total) for one reason: it gates **322 repos
transitively** while sitting at a own-maturity of 0.22.

That number is a prompt to look, not a mandate to pad. The question this
ADR answers is what is *actually* missing here, measured the same way the
original extraction was: by counting duplication in the consumers.

## Measurement (2026-08-05, over the 316 repos depending on this lib)

| Shape | Consumers still hand-rolling it |
|---|---|
| read one EDN-blob payload by a unique id attr — `(ls/dec* (d/q …))` | **222** |
| the `#?(:clj System/currentTimeMillis :cljs (.getTime (js/Date.)))` branch | **85** |
| `:type` + `:timestamp` stamping around `append-blob!` at `(count (records s))` | 177 already call `append-blob!` and each re-implements the surround |
| a named `blob-lookup` | only **9** |

The 222-vs-9 gap is the finding. The keyed-blob read is the most duplicated
shape left in the fleet, and it is nearly invisible to a name-based grep
because almost every copy inlines the query rather than naming it.

The field-spec `pull->map` / `map->tx` helper the README described as "the
documented next increment" turned out to already exist (28 consumers call
it). The README was stale; it has been corrected rather than the code
re-written.

## Decision

Add, with tests on both runtimes:

- `blob-lookup` / `put-blob!` — the keyed EDN-blob entity read/write pair.
- `now-ms` — the portable wall clock.
- `stamp` / `append-record!` — the ledger record convention (type +
  timestamp, appended at the next sequence number).

## Consequences

- A keyed-blob store shrinks to its `Store` protocol and its domain
  vocabulary. Nothing here knows a domain noun.
- **A guarantee was not created by centralizing code.** `append-record!`
  reads-then-appends exactly like the hand-rolled bodies it replaces, so it
  is not atomic against a concurrent appender. This is stated in the
  docstring and the README rather than left for a caller to discover: a
  store with concurrent writers needs a single writer or an externally
  supplied seq, and should call `append-blob!` directly.
- `now-ms` is a real clock read. `stamp` takes the timestamp as an argument
  so a test can pin it, and `append-record!` has a 6-arity that does the
  same; only the 5-arity reads the clock.
- **No migration of the 222 consumers is performed by this ADR.** Adding
  the helper is safe and additive; rewriting 222 stores is a separate,
  reviewable change per repo. Counting the adopters is how the next
  increment will be justified, the same way this one was.

## Verification

`kbb -M:test` (JVM) and the ClojureScript runner (primary gate), both
run 2026-08-05: 13 tests / 40 assertions, 0 failures.
