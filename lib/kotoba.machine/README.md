# kotoba-lang/machine

**T5 contract — what a piece of hardware *is*, as validated data.**

Cache line width, page size, private L2 capacity, NUMA distance, SIMD width,
GPU subgroup size, device queue depth. Every hardware-shaped planner in this
stack needs these numbers, and before this repo they lived nowhere — so each
planner would have invented its own constants.

Constants invented per planner is exactly how an *optimization fossil* forms:
a number that was true on the machine someone measured once and silently
wrong everywhere after.

```clojure
(require '[machine.core :as m])

(m/line-bytes probed)                     ;=> 128  (the WIDEST declared line)
(m/private-cache-bytes probed 3 :unified) ;=> 4194304  (L3 / 8 sharers)
(m/simd-lanes probed 4)                   ;=> 8
(m/reorderable? (m/storage-device probed :nvme0)) ;=> false
```

## Three properties that carry the design

**1. Provenance is part of the descriptor.**

```clojure
:machine/provenance :measured | :vendor-declared | :assumed
:machine/source     "sysctl hw.cachelinesize"
```

`machine.core/measured` refuses an empty source, and
[`perfgate`](https://github.com/kotoba-lang/perfgate) refuses to qualify a
performance claim whose machine is weaker than `:measured`. That is the
mechanism that stops a guess from hardening into a fact.

**2. Absent means absent — never a default.**

Every accessor answers `nil` for a section the descriptor does not carry, and
`require-fact` throws with the path it wanted. `(or (line-bytes m) 64)` is how
a fossil gets in; `require-fact` is the alternative. The shipped `unknown`
profile carries no `:cpu`, `:page`, `:gpu` or `:storage` at all, so a host
that has not probed yet fails loudly rather than planning against a guess.

**3. It does not probe.**

Reading `sysctl`, `cpuid`, `/sys/devices/system/cpu` or `navigator.gpu.limits`
is a host effect, and a contract that performs effects is not a contract. A
host builds the descriptor and hands it in.

## Validation

`validation-errors` returns *every* reason a descriptor is invalid, not the
first — a descriptor is hand-written once and the useful output is the whole
list. Top-level keys are **closed**: a typo'd `:strorage` is an error, because
silently reading as "no storage devices" produces a planner that quietly stops
planning.

Checks that catch real transcription errors rather than just types:

| check | why it matters |
|---|---|
| `bytes = ways × line × sets` | a cache geometry that does not multiply out is a typo |
| capacity strictly increases by level | an L2 smaller than L1 inverts every "does the working set fit" answer |
| line width is a power of two | non-power-of-two lines break every alignment computation downstream |
| huge pages larger than the base page | otherwise the TLB reasoning is backwards |
| NUMA self-distance is minimal | a node further from itself than from a peer inverts every placement decision |
| NUMA matrix is square and matches node count | a ragged matrix indexes out of range at plan time |
| workgroup ≥ subgroup | a workgroup narrower than a subgroup cannot be dispatched |
| storage ids are unique | two devices under one id silently shadow each other |
| max transfer ≥ block size | a device that cannot move one block cannot be planned against |

## Shipped profiles

Two, and neither pretends to be a specific product. A hardcoded `apple-m4`
full of numbers nobody in this repo measured would *be* the fossil this
contract exists to prevent.

- **`portable-64`** — the weakest common value across mainstream 64-bit
  targets (64-byte lines, 4 KiB pages, one node). Safe anywhere, unambitious
  everywhere, marked `:assumed`.
- **`unknown`** — valid, so it threads through a pipeline, but carries no
  facts at all.

Real machines come from a host probe stamped with `machine.core/measured`.

## Fingerprint

`fingerprint` is a deterministic 31-bit value over a canonical rendering
(sorted map keys, sorted sets, vectors in order). It is **not** cryptographic
and is not claimed to be — it exists so a performance claim can notice the
machine underneath it changed (`perfgate/stale-on?`). Sealing an artifact is
[`kotoba-lang/artifact`](https://github.com/kotoba-lang/artifact)'s job.

The arithmetic stays under 2⁵³ so JVM longs and JS doubles agree exactly: no
BigInt, no host hash function.

## Consumers

| repo | uses |
|---|---|
| [`layout`](https://github.com/kotoba-lang/layout) | `line-bytes`, `simd-lanes` |
| [`traversal`](https://github.com/kotoba-lang/traversal) | `private-cache-bytes`, `line-bytes` |
| [`paging`](https://github.com/kotoba-lang/paging) | `page-bytes` |
| [`ioplan`](https://github.com/kotoba-lang/ioplan) | `storage-device`, `reorderable?` |
| [`perfgate`](https://github.com/kotoba-lang/perfgate) | `fingerprint`, `:machine/provenance` |
| [`gpu`](https://github.com/kotoba-lang/gpu) | `gpu` limits, for launch geometry |

## Test

```sh
kbb -M:test
```

Pure `.cljc`, zero production dependencies, no host objects. See
ADR-2608030200 in the superproject.
