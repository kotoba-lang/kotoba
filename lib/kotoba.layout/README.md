# kotoba-lang/layout

**T5 library — where the bytes of an aggregate go, planned against a real machine.**

A particle with `x y z mass`. Held as an array of structs, a pass that reads
only `x` still pulls `y z mass` into every cache line it touches. Held as a
struct of arrays, `x` is contiguous and the line is all payload.

```clojure
(l/cost mach (l/aos mach particle) 1024 {:access/fields #{:x}})
;=> {:cost/lines 384 :cost/bytes-useful 4096 :cost/utilization 0.166… :cost/streams 1 …}

(l/cost mach (l/soa mach particle) 1024 {:access/fields #{:x}})
;=> {:cost/lines  64 :cost/bytes-useful 4096 :cost/utilization 1.0    :cost/streams 4 …}
```

Six times the lines for the same useful bytes. But this namespace does not
declare SoA the winner in the abstract — a pass that touches *every* field of
one element wants the struct back. It computes what each layout costs for a
**stated** access pattern on a **stated** machine, and reports the model it used.

## The cost model is a value

`cost` returns `:cost/model` alongside the numbers, and `recommend` returns the
losers as well as the winner:

```clojure
(l/recommend mach particle 1024 {:access/fields #{:x}})
;=> {:recommend/chosen {…}
;    :recommend/ranked [{:candidate :soa   :cost {:cost/lines  64 …}}
;                       {:candidate :aosoa :cost {:cost/lines  64 …}}
;                       {:candidate :aos   :cost {:cost/lines 384 …}}
;                       {:candidate :aos-reordered …}]
;    :recommend/model  {:model/id :kotoba.layout.cost/compulsory-lines-v1 …}}
```

A layout choice whose justification cannot be printed is how a team ends up
with an optimization nobody can re-derive and nobody dares delete.

The model states what it does **not** model — capacity misses, conflict misses,
prefetch, write-allocate, store buffers, TLB, NUMA — and two consequences that
people expect to be false:

- **With no struct padding and a pass touching every field, AoS and SoA fetch
  exactly the same bytes.** This model cannot separate them. The separation
  appears only when the pass touches a subset, or when the struct carries
  padding SoA does not pay.
- **A line count says nothing about concurrent sequential streams.** Hardware
  prefetchers track a bounded number, so a SoA over many fields is not free
  even where the line count says it is. Hence `:cost/streams`, which breaks
  ties in `recommend`.

## Reordering fields breaks the ABI

Sorting fields by descending alignment is the standard padding squeeze —
`{flag:1, mass:8, x:4}` goes from 24 bytes to 16 — and it changes the byte
offsets that [`kotoba-wasm`](https://github.com/kotoba-lang/kotoba-wasm)'s
Canonical ABI fixes by declaration order.

So every plan carries `:layout/abi-canonical?` and `:layout/scope`, and
`abi-guard!` throws rather than letting an internal-only layout leak across a
component boundary:

```clojure
(l/abi-guard! (l/aos mach fields {:reorder? true}) :lift-record)
;=> ExceptionInfo: non-canonical layout at an ABI boundary
;   {:remedy "use (aos machine fields) — declaration order, no line padding"}
```

Only a declaration-ordered, unpadded AoS may cross. SoA cannot by construction:
there is no struct for a record lift to point at. Silently shipping a reordered
struct through a Canonical ABI lift is a wire-format bug that presents as data
corruption.

## The stride regimes

`lines-for-strided-run` has two, and the boundary between them is the whole
point of a stride:

| condition | cost | reading |
|---|---|---|
| `step × width ≥ line` | `⌈n/step⌉ × ⌈width/line⌉` | touched items land on distinct lines — you pay for the bytes you skipped |
| `step × width < line` | `⌈n×width/line⌉` | consecutive touched items share lines — skipping is free, the line came in anyway |

Which regime you are in flips with the layout. Reading `x` with stride 4:
AoS crosses into the sparse regime (24×4 > 64) and costs 256 lines at 6%
utilization; SoA stays dense (4×4 < 64) and costs 64 at 25%.

## False sharing

Judged on `:layout/write-stride-bytes` — how far apart two threads' writes land
— which is the struct size for AoS but the **field** width for SoA and AoSoA.
So SoA is at risk where AoS is not:

```clojure
(l/false-sharing-risk mach (l/soa mach particle) {:concurrent-writers 4})
;=> {:risk :present :writes-per-line 16 :fix :pad-to-line :footprint-multiplier 16.0}
```

The symptom — a parallel loop that gets *slower* with more threads — is often
misread as lock contention.

## AoSoA block width

`default-block` picks `line / narrowest-field`, so each field's sub-array is a
whole number of cache lines (exact when field widths are multiples of the
narrowest — 1/2/4/8, the normal case), floored at the SIMD lane count for the
widest field. For the particle on a 64-byte line: block 16, sub-arrays at
`[0 64 128 192]`, zero padding.

## Test

```sh
kbb -M:test
```

Pure `.cljc`. Depends only on
[`kotoba-lang/machine`](https://github.com/kotoba-lang/machine). See
ADR-2608030200 in the superproject.
