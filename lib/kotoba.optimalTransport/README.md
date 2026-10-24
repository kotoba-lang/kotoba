# kotoba-lang/optimal-transport

Optimal-transport-based mesh shape interpolation ("morph targets") --
topology-flexible shape blending for two vertex-position arrays that need
NOT have the same vertex count or index order.

## Why optimal transport instead of naive index-aligned blend shapes

The standard glTF/VRM morph-target convention -- and this org's existing
hand-authored blend shapes, `character.blendshape`
(`orgs/kotoba-lang/character/src/character/blendshape.cljc`) -- assumes
`verts-a[i]` and `verts-b[i]` are the same logical vertex on two
topologically identical meshes (shared index buffer), so a morph target is
just `verts-b[i] - verts-a[i]` per index. That assumption breaks the moment
the two meshes come from different generators, different LODs, different
asset pipelines, or a scan vs. a procedural mesh -- there is simply no
`i`-to-`i` correspondence to subtract.

Optimal transport sidesteps this: it finds the cheapest way (under
squared-Euclidean cost by default) to move all of `verts-a`'s point mass
onto `verts-b`'s point mass, as a `n x m` transport PLAN rather than a
`1:1` mapping. `mesh-morph` turns that many-to-many plan into a
well-defined per-source-vertex target via the **barycentric projection of
the transport map**: for each source vertex, the mass-weighted average of
every target vertex it sends mass to. `verts-a` and `verts-b` genuinely do
not need the same length -- that is the actual, concrete reason to reach
for this library instead of a one-line vector subtraction.

## Algorithm

Entropic-regularized optimal transport, solved with **Sinkhorn
iterations** (`optimal-transport.sinkhorn`), in the **log-domain
stabilized** form: dual potentials `f`/`g` are updated via log-sum-exp
instead of directly forming the raw Gibbs kernel `exp(-C/epsilon)`, which
avoids the overflow/underflow that the naive multiplicative form hits at
the small `epsilon` values morph-target correspondences actually want
(small `epsilon` -> sharp, near-permutation matches; large `epsilon` ->
diffuse, blurred coupling). A naive (non-log-domain) variant,
`sinkhorn-naive`, is also provided for testing/comparison at moderate
`epsilon`.

This is genuinely **inspired by** optimal-transport theory -- entropic OT
is the discrete, computationally tractable relaxation of the classical
Monge/Kantorovich transport problem, and the broader Monge-Kantorovich /
Monge-Ampere regularity line of work (Figalli et al.) studies the smooth,
PDE-constrained limit of the same problem. **This library is not a
Monge-Ampere PDE solver and makes no regularity-theory claims** -- it
implements a practical, iterative numerical method: Cuturi's 2013
"Sinkhorn Distances", with the log-domain stabilization standard in modern
OT solvers (see e.g. Peyre & Cuturi, *Computational Optimal Transport*,
Remark 4.10 / Section 4.4, for the exact `f`/`g` update implemented here).

## Complexity / performance

`O(n*m)` per Sinkhorn iteration (`n` source vertices, `m` target
vertices), `O(n*m*iterations)` total, `O(n*m)` memory for the cost matrix
and transport plan. **This is intended for OFFLINE / AUTHOR-TIME
morph-target precomputation** -- run once per mesh pair, bake the
resulting `:deltas` into a static asset -- **not for per-frame runtime
use**. `kami.webgpu.mesh`'s `draw!` (the consumer) blends precomputed
morph-target deltas via a scalar `morph-weights` uniform at draw time; it
never re-solves a transport problem per frame, and neither should any
caller of this library.

## Integration point

`optimal_transport.mesh_morph/morph-target` returns
`{:name "..." :deltas [[dx dy dz] ...]}` -- **byte-for-byte the same shape**
`character.blendshape/generate-arkit-targets` returns per target -- so it
slots directly into:

- `character-creator.gpu-adapter`
  (`orgs/kotoba-lang/kami-app-character-creator/src/character_creator/gpu_adapter.cljc`),
  the existing CPU-side geometry adapter, and from there into
- `kami.webgpu.mesh`'s `:morph-target-deltas`
  (`orgs/kotoba-lang/webgpu/src/kami/webgpu/mesh.cljs`), which expects
  `[[[dx dy dz] ...] ...]` -- one seq of per-vertex deltas per named morph
  target, consumed as WGSL storage buffers and blended by a `morph-weights`
  seq at draw time.

No adapter code is required in between.

## Usage

```clojure
(require '[optimal-transport.mesh-morph :as morph])

(def verts-a [[0.0 0.0 0.0] [1.0 0.0 0.0] [0.0 1.0 0.0] [0.0 0.0 1.0]])
(def verts-b [[0.1 0.0 0.0] [1.1 0.1 0.0] [0.0 1.1 0.1]   ; a DIFFERENT
              [1.0 1.0 0.0] [0.0 1.0 1.0] [1.0 0.0 1.0]   ; vertex count
              [0.1 0.0 1.1]])                              ; is fine

;; a single named morph target, character.blendshape-shaped:
(def target (morph/morph-target verts-a verts-b {:name "smile" :epsilon 0.05}))
;; => {:name "smile" :deltas [[dx dy dz] ...]}   -- length = (count verts-a)

;; slot straight into a kami.webgpu.mesh geometry map:
(def geometry
  {:positions verts-a
   :normals   [...]
   :indices   [...]
   :morph-target-deltas [(:deltas target)]})   ; one entry per named target

;; or ask for interpolated positions directly (CPU preview / non-GPU caller):
(morph/interpolate verts-a verts-b 0.5 {:epsilon 0.05})
;; => [[x y z] ...] at 50% blend toward the OT-matched target positions
```

## Runtime

First-class runtime is **ClojureScript** (browser/Node), per this org's
2026-07-10 runtime-priority policy (`kotoba wasm` > `clojurewasm` >
ClojureScript > `nbb`, JVM/`bb` demoted to compat-only,
`com-junkawasaki/root` `AGENTS.md`). All math (`optimal_transport/
sinkhorn.cljc`) uses `#?(:clj ... :cljs ...)` reader conditionals for
`Math/exp`/`Math/log`/`Math/abs` vs. `js/Math.exp`/`js/Math.log`/
`js/Math.abs`, the same convention as `character.math`. Tests run via
`kbb -M:test` for CI convenience, matching every sibling `.cljc` repo
in this org.

No runtime dependencies -- Sinkhorn only needs scalar `exp`/`log`/`+`/`-`/
`*` and row/column sums over `[x y z]` triples, so this repo vendors its
own handful of vec3 helpers (`mesh_morph.cljc`) rather than add a
shared-math dependency.

## Testing

```bash
kbb -M:test    # cognitect test-runner
kbb -M:lint     # clj-kondo, --fail-level error
```
