# ADR-0002 — Runtime-enforced capabilities: the `aiueos:host` ABI + topic bus

- Status: accepted
- Date: 2026-06-25

## Context

Phase-0 (ADR-0001) verified capabilities *statically* — a manifest declares
`:aiueos/imports`, the reasoner checks they resolve, the broker confers a set. But
the running components were pure compute: they could not actually *call* a
capability, so the conferred set was never enforced at run time. For a robot OS
this is the whole game: "the vision node cannot drive the motors" must be
enforced when the node runs, not merely asserted in a manifest.

## Decision

Add a broker-mediated host ABI, `aiueos:host`, bound via a wasmtime `Linker`, where
**every host function is gated on the conferred capability set** carried in the
store context. A call to a capability the component wasn't granted **traps** — it
cannot proceed. Capabilities become runtime enforcement, not just a static claim.

Phase-0 ABI is deliberately numeric (no linear-memory marshaling):

| import              | capability        |
|---------------------|-------------------|
| `log(i64)`          | `log/write`       |
| `clock() -> i64`    | `clock/monotonic` |
| `publish(i32,i64)`  | `topic/publish`   |
| `poll(i32) -> i64`  | `topic/subscribe` |

Add an in-process **topic bus** ([`topic`](../../src/topic.rs)) — the ROS-topic
analogue: numeric topic ids, i64 samples, last-write-wins, per-topic counts. On
`boot`, one bus is threaded *by value* through each component in launch order, so
a producer's `publish` is visible to a later consumer's `poll`. This is a running
sensor → planner → actuator dataflow over capability-gated nodes, with no shared
mutable state (the bus moves in and back out of each run).

`topic/publish` and `topic/subscribe` join the default kernel capabilities, so a
component opts into bus access by importing them; the host ABI then allows the
matching calls and traps the rest.

## Decouple execution from compilation (feature split)

Calling host functions requires the component to *import* them, which the
kototama CLJ compiler does not emit for arbitrary aiueos capabilities. So
host-calling components are authored as **WAT** (or precompiled wasm) referenced
via `:aiueos/wasm`, which wasmtime loads directly — no kototama needed.

This motivated splitting the old `wasm-runtime` feature in two:

- **`wasm-runtime`** — *execute* wasm (binary/WAT) under fuel + memory limits with
  the `aiueos:host` ABI. Needs only wasmtime.
- **`kototama`** — *compile* CLJ → wasm; implies `wasm-runtime`.

Besides being cleaner, the split let the host ABI / robotics work build and test
(`--features wasm-runtime`) while the kototama toolchain was temporarily broken by
an unrelated in-progress edit in the `kami-engine-clj` submodule — execution does
not depend on the compiler.

## Consequences

- `aiueos up examples/robot/robot.aiueos.edn` boots a 3-node robot: sensor publishes
  21 → planner polls and publishes 42 → actuator polls and drives 42. The planner
  is an `:agent` (AI-generated trust) doing topic IO while still denied
  network/secrets/persistence. The actuator imports only `topic/subscribe`, so a
  `publish` from it traps — it structurally cannot command the bus.
- The broker's `materialize_and_run` now takes the conferred capability set and a
  bus, threading the bus across a booted system. `launch` (single component) uses
  a fresh bus.
- Tests gate by capability: `kototama` for CLJ-compile paths, `wasm-runtime` for
  the WAT/host-ABI robotics paths.

## Not yet (later phases)

- Named topics with per-topic capabilities (`topic/scan`, `topic/cmd`) — these
  would also turn topic wiring into real capability-graph edges, so `boot_order`
  reflects dataflow.
- Queued/typed messages (not just latest i64), linear-memory payloads.
- Real device drivers (CAN/I2C/SPI/GPIO) as components over kernel-provided unsafe
  adapters; a real-time / periodic scheduler with priorities and deadlines. Hard
  servo loops stay native; wasm suits the supervisory/planning layers.
