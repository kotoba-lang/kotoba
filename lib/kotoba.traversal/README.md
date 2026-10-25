# kotoba-lang/traversal

**T5 library — in what order to visit the elements, given a real cache.**

[`layout`](https://github.com/kotoba-lang/layout) decides where bytes sit;
this decides the sequence they are touched in. The two are independent — a
perfect struct-of-arrays walked down the wrong axis still misses every line —
and the second is usually the larger effect, because changing an order changes
how much data crosses the slow boundary rather than how it is arranged once it
is across.

## The measured result that contradicts the folklore

Space-filling curves are supposed to keep 2-D neighbours near each other in
1-D. `neighbour-locality` measures it instead of repeating it, on a 16×16 grid:

| order | mean neighbour distance | worst | same 16-block |
|---|---|---|---|
| row-major | **8.5** | 16 | **50%** |
| Morton (Z) | **8.5** | 170 | **80%** |
| Hilbert | **9.92** | 129 | **80%** |

Morton's mean is *identical* to row-major's. Hilbert's is *worse*. Both curves
trade many medium jumps for a few enormous ones, and the mean is dominated by
that tail.

The win is real, but it is in **block co-residency** — the question a cache
line or a page actually asks. A 4×4 tile of the grid is 16 consecutive,
block-aligned positions on either curve, while row-major spreads it across four
separate rows.

So `:same-block` chooses the order, and `:mean` stays in the output as the
reminder that the intuitive metric answers the wrong question.

## Loop order, derived rather than remembered

```clojure
(t/loop-order mach [:i :j :k]
              [{:array :A :strides {:i 512 :k 1 :j 0}}     ; A[i][k]
               {:array :B :strides {:k 512 :j 1 :i 0}}     ; B[k][j]
               {:array :C :strides {:i 512 :j 1 :k 0}}]    ; C[i][j]
              8)
;=> {:loop/order [:i :k :j] :loop/innermost :j
;    :loop/ranked [{:loop :i :cost 16} {:loop :k :cost 9} {:loop :j :cost 2}]}
```

The textbook `ikj`, from first principles: `j` is the only loop under which no
array strides badly. Stride 0 is free (the reference is loop-invariant and
hoists), stride 1 is ideal, and cost **saturates at one line's worth of
elements** — past that you already pay a whole line per access and a larger
stride cannot make you pay more.

## Tiling

```clojure
(t/tile-plan mach {:extents [512 512] :element-bytes 8 :arrays 3 :level 2})
;=> {:tile/size 72 :tile/capacity-bytes 262144 :tile/usable-bytes 131072
;    :tile/working-set-bytes 124416 :tile/fits? true :tile/tiles [8 8] …}
```

Three decisions in there are not defaults, they are stated positions:

- **The capacity is the private share** — level capacity divided by the cores
  sharing it. An 8 MiB L3 across 8 cores licenses a tile against 1 MiB, not
  8 MiB. Sizing to the shared total is how a tile fits on paper and thrashes
  against seven siblings.
- **`:occupancy` defaults to 0.5**, because the level also holds the stack, the
  code, and whatever else is running. It is a parameter and it is reported.
- **The tile rounds down to whole cache lines**, so a tile row never straddles.

`:tile/model` travels with the answer and names what it does not model:
associativity conflicts, TLB reach, prefetch, NUCA latency.

## Every order is checked to be a permutation

```clojure
(t/bijection? :hilbert [16 16])  ;=> true
(t/linearize :morton [8 4] [0 0]) ;=> throws — a curve does not cover a ragged box
```

A reordering that silently skips or repeats an element is not a slow program,
it is a wrong one. Morton and Hilbert do exactly that on an extent they were
not given (ragged, or not a power of two), so `linearize` refuses those extents
rather than returning positions with holes in them.

Hilbert additionally guarantees that **consecutive positions are always
4-adjacent cells** — no jump at a quadrant boundary — which the tests check
exhaustively for sides 4, 8 and 16.

## Bit budgets are enforced, not wrapped

ClojureScript's bitwise operators are signed 32-bit, so an interleave running
past bit 30 goes negative there and not on the JVM. Rather than branch per
runtime, coordinates are capped — 2-D at 15 bits (side ≤ 32768), 3-D at 10
(side ≤ 1024) — and a coordinate outside the range throws instead of silently
producing a negative Morton code.

## Test

```sh
kbb -M:test
```

Pure `.cljc`. Depends only on
[`kotoba-lang/machine`](https://github.com/kotoba-lang/machine). See
ADR-2608030200 in the superproject.
