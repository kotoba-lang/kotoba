# kotoba-lang/gpu

**SSoT for `kami.gpu`** — capability-gated GPU pipeline IR (render-graph resolve per
backend tier: WebGPU / WebGL2 / native / console). Pure `.cljc`; no browser executor.

`kotoba.gpu` is NOT a facade. It owns the implementation, and the file says so:
re-exporting `kami.gpu` would make this contract's meaning depend on classpath
order, because `kami-engine-sdk` ships a different `kami.gpu` — a backend
protocol (`IGpuBackend`, `submit!`, `ensure-assets!`) with no function name in
common with the capability/render-graph IR here.

That duplication is deliberate and is the cheapest thing that works today; it
is not an end state. The collision it routes around is recorded in
ADR-2608120600 (com-junkawasaki/root), which counts `kami/gpu.cljc` among the
namespaces two repos ship with different content onto one classpath. Which
`kami.gpu` is canonical is an owner decision that has not been made.

See ADR-2607102200 addendum 6.

## `kami.gpu.launch` — launch geometry

`kami.gpu` answers *can this backend run this pass*. `kami.gpu.launch` answers
the separate question *given that it can, what shape should the dispatch be* —
because a pass a backend runs at 8% of its bandwidth is still a pass the
backend can run, and the tier table cannot tell you which one you have.

```clojure
(l/workgroup-size machine {:shared-bytes-per-invocation 64})
;=> {:size 512 :bound-by :shared-memory :subgroups 16
;    :shared-bytes-used 32768 :shared-bytes-available 49152}
```

Nothing here comes from a constant. `256` is the workgroup size everyone
writes down; it wastes half of a 1024-lane device and is **illegal** on one
whose maximum is 128. The plan reports which constraint bound it — device
maximum, shared-memory budget, problem size, or the subgroup floor overriding
one of those — because that is the part a reader needs when the number looks
wrong. An absent shared budget is never reported as the binding reason.

Coalescing is a **fraction, not a verdict**: a stride-2 access is not
"uncoalesced", it is half of every transaction wasted (`0.5`), and a column
walk of a 32-wide row is `0.03125`. Which to fix first is obvious from the
numbers and invisible from a boolean.

Workgroup **swizzle** orders the tiles of a 2-D dispatch along a space-filling
curve instead of row by row, so workgroups resident together touch nearby
memory — the same reason a fast GEMM swizzles its threadblock index. That is
the same question `traversal` answers for a CPU cache, so it is the same code:
no second Morton implementation living in a GPU file. The plan carries the
measured `:same-block` locality for both the chosen order and row-major, so
the swizzle is justified by a number rather than a citation.

A curve only covers a square power-of-two grid, so a ragged one is walked over
the enclosing square with out-of-range coordinates dropped — which is why
`swizzled-tiles` returns a *sequence* rather than an index formula: position N
is not tile N.

Depends on [`kotoba-lang/machine`](https://github.com/kotoba-lang/machine) and
[`kotoba-lang/traversal`](https://github.com/kotoba-lang/traversal). See
ADR-2608030200 in the superproject.

## Test

```sh
kbb -M:test
```
