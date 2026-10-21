# kotoba-lang/async

**Layer 2 (cap/effect) of the kotoba foundational stdlib** — bounded channels as
**pure state machines**. `put` / `take` are pure transitions a host or durable
loop drives — **no threads, no wall-clock, no core.async dependency** — so the
same CSP model runs through the Kotoba reference evaluator, restricted
JavaScript, and typed Wasm. The sole production source is `.kotoba`; JVM
Clojure is only a compiler/test host. See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Why this shape

The kotoba-WASM premise (no threads, no wall clock) rules out `core.async`
go-blocks and `tokio`-style runtimes. But the vertical libs (`langgraph`
interrupts / resume, the actor durable outer loop) still need a vocabulary for
*bounded queues* and *backpressure*. This lib models a channel as plain EDN
canonical bounded document state and `put`/`take` as `[new-state result]`
transitions — the host loop
threading the state through. That is exactly the "bounded state-machine channel"
the foundational-stdlib ADR specified, and it composes with the durable outer
loop in `AGENTS.md` (lease / tick / budget) without inventing a runtime.

## Current surface

`kotoba.lang.async`:

- `fixed-chan` — make a fixed channel; `chan` selects `:fixed`, `:dropping`, or
  `:sliding`. Capacity must be 1–32 and invalid construction fails closed.
- `put [ch val]` → `[ch' accepted?]` — fixed blocks (not accepted) when full;
  dropping discards the new value when full; sliding discards the oldest
- `take [ch]` → `[ch' val-or-nil]` — `nil` means "nothing available now"
- `close [ch]`, `closed? [ch]`
- `can-put? [ch]`, `can-take? [ch]`
- `drain [ch]` → `[ch' [vals…]]` — take everything immediately available
- `scope`, `scope-spawn`, `scope-close`, `scope-complete`, `scope-fail`,
  `scope-cancel`, `scope-join-ready?`, `scope-summary` — a fail-fast structured
  scope with at most 32 children. Admission closes before join; a failed child
  cancels running siblings; no child remains running after terminal scope state.

The structured scope is also plain canonical state. It does not create host
threads, choose an executor, read a clock, or pretend cancellation has reached
an external process. A host or durable loop performs the work and reports each
terminal child transition back into the scope.

## Install

```clojure
io.github.kotoba-lang/async {:git/sha "<sha>"}
```

## Use

```clojure
(def channel (chan :dropping 2))
(def offered (put channel (document-keyword :a)))

(def s0 (scope))
(def spawned (scope-spawn s0 (document-keyword :fetch)))
(def s1 (first spawned))
(def child-id (second spawned))
(def joining (scope-close s1))
(def done (scope-complete joining child-id (document-keyword :ok)))
(scope-join-ready? done) ;=> true
```

Payloads and transition pairs are canonical `:document` values, so arbitrary
host objects cannot cross the boundary unchecked.

## Verify

```sh
kbb -M:test
```

The parity suite executes the `.kotoba` semantic authority and the `.cljc`
load path through the same state-transition vectors.
