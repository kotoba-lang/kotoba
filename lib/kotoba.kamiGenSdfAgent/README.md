# kotoba-lang/kami-gen-sdf-agent

An LLM-authored (v0: heuristic-authored) signed-distance-field / CSG mesh
generation pipeline. Given a text brief (e.g. "penguin kigurumi hood, rounded
chibi body, yellow beak"), `kami.gen.sdf-agent/generate` runs a bounded
propose -> compile -> render -> critique loop and returns a diffable,
replayable EDN program plus the mesh and preview image it converged on.

This is **Approach 2 of 4** in a head-to-head comparison of mesh-generation
strategies against the same photoreal chibi-penguin-kigurumi reference
target -- see `com-junkawasaki/root` ADR-2607051110
(`90-docs/adr/2607051110-kami-gen-sdf-agent-procedural-mesh-pipeline.md`) and
its 3 siblings:

- `kotoba-lang/kami-gen-procedural` (Approach 1: LLM fills a fixed parametric schema)
- `kotoba-lang/kami-gen-sdf-agent` (this repo, Approach 2: LLM writes/edits a small CSG/SDF program)
- `kotoba-lang/kami-gen-ml3d` (Approach 3: ML image-to-3D generation)
- `kotoba-lang/kami-gen-hybrid` (Approach 4: combines the above)

The ADR's own expectation, worth restating honestly here: the CSG/SDF
primitive vocabulary (spheres, cones, rounded boxes, cylinders, boolean
combinators) composes well for rounded/blobby props and structures, and
poorly for organic chibi-character silhouettes, skin, or costume folds. This
repo is expected to land closer to Approach 1's fidelity ceiling than
Approach 3's for a character subject -- its best real fit going forward is
probably props/structures, not characters. v0 also produces a static,
prop-like mesh with no VRM/skeleton rig (a CSG-composed body has no bone
hierarchy).

## What's real vs. stubbed in v0 (read this before trusting any output)

- **compile (real, never mocked).** `kami.gen.sdf-agent.sdf` implements the
  actual signed-distance-field math -- exact sphere / rounded-box / capped-
  cylinder / capped-cone primitive formulas (the standard Inigo Quilez `sdf`
  reference formulas) and CSG boolean combinators (union = min, intersect =
  max, difference = max(a, -b)) -- and compiles a CSG EDN program into a
  sampler function. `kami.gen.sdf-agent/compile-program` feeds that sampler
  into `kotoba-lang/mesher`'s real Marching Cubes (`mesher/sdf-to-colored-mesh`)
  to extract an actual mesh. Every `generate` round runs this for real.

  Why this repo owns the SDF math instead of calling into `kotoba-lang/sdf`:
  as of 2026-07-05 that repo is a scaffold with no functions at all (its own
  README says "Scaffold only -- the CLJC restoration is pending"). This
  repo's `deps.edn` keeps a `:local/root` dependency on it anyway, as the
  intended migration target once it grows real primitives; today nothing
  here calls into it. `kotoba-lang/scad` (a real, tested OpenSCAD-text CSG
  evaluator) is also kept as a `:local/root` dependency for vocabulary/
  interop parity, but isn't required by this pipeline either -- this repo's
  own EDN CSG tree (see the grammar below) is a more constrained,
  structured-LLM-output-friendly input than raw OpenSCAD text, and `scad`'s
  own evaluator only visually-approximates difference/intersection as union
  anyway (a Phase-1 limitation of that repo, not this one).

- **render (real, never mocked).** `kami.gen.sdf-agent.render` is a real (if
  deliberately simple) software rasterizer: a fixed isometric orthographic
  projection, a z-buffered flat-shaded triangle fill, written out as an
  actual PNG via the JDK's own `javax.imageio.ImageIO` (no wgpu, no extra
  dependency). It follows the spirit of the offscreen-render reference
  pattern in `kotoba-lang/kami-engine` ADR-0047 (render the real artifact
  from a fixed camera so critique has a real image), without that ADR's wgpu
  pipeline. Every round's mesh is actually rasterized to a real PNG on disk.

- **propose (v0: heuristic, NOT an LLM call).** `kami.gen.sdf-agent.propose/
  default-propose` is a deterministic function: it builds a fixed 3-part CSG
  template (body sphere / hood-head sphere / beak cone) from `brief`
  keywords on round 1, then applies the previous round's `:edit-suggestion`
  as a bounded numeric edit on later rounds. **No LLM is called.** This is
  the documented injection seam: `generate`'s `:propose` option is a plain
  `(fn [brief history] -> program)`; a real deployment passes an LLM-backed
  function with that exact signature (e.g. one that prompts a model with
  `brief` plus the previous round's render + critique, and parses its CSG-
  EDN reply) and nothing else in this repo changes.

- **critique (v0: heuristic pixel analysis, NOT a vision-LLM call).**
  `kami.gen.sdf-agent.critique/default-critique` re-reads the rendered PNG
  (the same two inputs -- image + text brief -- a real vision-LLM critique
  call would get; it does not receive privileged 3D mesh data) and scores it
  on the rendered silhouette's 2D bounding-box aspect ratio vs. a target,
  presence of a plausible yellow-accent region when the brief says "yellow",
  and non-degeneracy. **No LLM is called.** This is the other documented
  injection seam: `generate`'s `:critique` option is a plain
  `(fn [render-path brief] -> {:score :accept? :edit-suggestion})`.

Despite propose/critique being heuristic rather than LLM-backed in v0, the
loop is a real, observable feedback loop, not a fixed script: `generate`'s
default heuristics genuinely read each round's *actual rendered pixels* and
adjust the *next round's actual geometry* in response -- see `Example` below,
where round 1 scores 0.69 (beak too small / no yellow detected) and round 2's
critique-driven beak resize gets it to 0.95 and accepts.

## The bounded loop (no silent caps)

`generate` never loops unboundedly -- `:max-rounds` (default 4) is a hard
cap. If no round's critique ever sets `:accept? true`, `generate` still
returns a usable result: the **best-scoring** round's program/mesh (not
necessarily the last round's), and always both `println`s and returns in
`:log` that the cap was hit, which round won, and its score. A capped run is
always reported, never silently truncated -- matching this org's "no silent
caps" convention.

## CSG program grammar

A program is a single EDN tree. A node is a vector `[tag & args]`:

```clojure
[:sphere   {:r n :center [x y z] :color [r g b a]}]
[:box      {:size [sx sy sz] :center [x y z] :round n :color rgba}]
[:cylinder {:r n :h n :center [x y z] :axis :x|:y|:z :color rgba}]
[:cone     {:r n :h n :at [x y z] :r2 n :axis :x|:y|:z :color rgba}]
;; :at is the BASE center (not the midpoint); the apex sits `h` further
;; along +axis from :at. :r2 (default 0.0) is the top radius -- 0 = a true
;; cone, >0 = a frustum.

[:union       child & children]
[:intersect   child & children]
[:difference  child & children]   ;; first child minus the rest
```

World convention used throughout: **z is up**, **+y is "front"** (the
direction primitives like a beak point outward toward, by convention).
Colors are `[r g b a]` in `0.0-1.0`; a combinator's output color at any point
follows whichever child's distance was actually decisive there (e.g. after a
`:difference`, the cut surface takes the subtrahend's color, not the
minuend's) -- see `kami.gen.sdf-agent.sdf`'s combinator docstrings.

## Usage

```clojure
(require '[kami.gen.sdf-agent :as agent])

(def result
  (agent/generate {:brief "penguin kigurumi hood, rounded chibi body, yellow beak"}))

(:rounds result)     ;; => 2 (accepted before hitting the max-rounds-4 cap)
(:accepted? result)  ;; => true
(:program result)    ;; => the final CSG EDN tree, e.g.
;; [:union
;;  [:sphere {:r 1.0 :center [0.0 0.0 0.0] :color [0.08 0.08 0.1 1.0]}]
;;  [:sphere {:r 0.6 :center [0.0 0.0 1.35] :color [0.12 0.12 0.16 1.0]}]
;;  [:cone {:r 0.224 :h 0.42 :r2 0.0 :axis :y
;;          :at [0.0 0.492 1.35] :color [0.95 0.78 0.05 1.0]}]]
(get-in result [:mesh :vertex-count])  ;; => a few thousand, resolution-dependent
(:render result)     ;; => path to the accepted round's offscreen PNG preview
(:history result)    ;; => every round's :program :score :critique :render, replayable
```

With a fixture propose/critique pair (e.g. for tests, or to drive the loop
from your own logic without either heuristic):

```clojure
(agent/generate
 {:brief "a simple ball"
  :propose  (fn [brief history] [:sphere {:r 1.0 :center [0 0 0]}])
  :critique (fn [render-path brief] {:score 1.0 :accept? true :edit-suggestion nil})
  :max-rounds 4})
```

Other options: `:resolution` (Marching Cubes per-axis grid resolution,
default 40), `:out-dir` (where per-round PNGs are written, default a fresh
temp dir), `:render-opts` (passed through to `render-preview!`, e.g.
`{:width 300 :height 300}`).

## Develop

```bash
kbb -M:test
```
