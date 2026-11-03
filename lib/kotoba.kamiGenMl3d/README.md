# kami-gen-ml3d

Photo/text → 3D via `gftdcojp/cloud-murakumo`'s real distributed GPU generation
backend (TRELLIS / Hunyuan3D-2), then auto-rigged to a VRM humanoid.
ADR-2607051120. **Approach 3 of 4** in a head-to-head 3D-pipeline comparison —
see the sibling repos `kami-gen-procedural` (Approach 1, ADR-2607051100),
`kami-gen-sdf-agent` (Approach 2, ADR-2607051110), and `kami-gen-hybrid`
(Approach 4, ADR-2607051130).

> **This repo's job-submission and auto-rig code is real and tested
> end-to-end against a mock executor. It has NOT been run against a live
> TRELLIS/Hunyuan3D-2 GPU backend** — doing so requires `MURAKUMO_BACKEND_URL`
> (or a reachable `trellis-cuda` proc image) configured by the fleet
> operator, and incurs real `:gpu/class :a100-80` billing. See
> ADR-2607051120.

## Pipeline

```
{:image-path :model :prompt}
  -> cloud-murakumo.gen/job            (build+validate the :model3d :gen.job)
  -> cloud-murakumo.worker/run-job     (injected :execute -- mock or real)
  -> kami.gen.ml3d.rig/auto-rig-glb    (heuristic VRM humanoid auto-rig)
  -> vrm.parse/parse-vrm               (round-trip validation)
  -> kami.gen.ml3d/->asset             (network-isekai Asset Hub record)
```

`kami.gen.ml3d/generate-from-image` returns:

```clojure
{:gen.job   ;; the normalized job, per cloud-murakumo.gen/job
 :run       ;; the :murakumo.run ledger entry from worker/run-job
 :mesh-path ;; downloaded/local path to the .glb/.gltf output
 :vrm       ;; {:path <file> :document <parsed VrmDocument>}
 :asset}    ;; network-isekai Asset Hub :asset/* record, CID-addressed
```

## `cloud-murakumo` dependency: direct, not a copied EDN slice

`deps.edn` takes a `:local/root` dependency directly on `gftdcojp/cloud-
murakumo` (`io.github.gftdcojp/cloud-murakumo`). `kami.gen.ml3d/model3d-fn`
calls `cloud-murakumo.spec/load-spec` + `cloud-murakumo.spec/functions` and
picks out `:fn/id :model3d` — the exact same function map
`cloud-murakumo.gen-test` itself asserts on, not a copy.

This was checked to be clean before committing to it: `cloud-murakumo`'s
`deps.edn` `:deps` (the part that lands on every consumer's classpath) is
just `org.clojure/clojure` + `org.clojure/data.json` — the `shadow-cljs`/cljs
UI-substrate dependency lives behind its own `:cljs` alias, which we never
activate. `kbb -Spath` in this repo confirms `cloud-murakumo`'s `src` AND
`resources` paths (so `(io/resource "murakumo.edn")` resolves) land on our
classpath transitively through the `:local/root` dep, with no cljs leakage.
Given that, depending directly and reading the live function map off
cloud-murakumo's own `resources/murakumo.edn` beat inlining a copy that could
silently drift from the real spec (this org's `:model3d` schema, models, or
`:gpu/class` could change upstream without this repo noticing).

`kami.gen.ml3d/build-job` calls `cloud-murakumo.gen/job` unmodified.
`generate-from-image` calls `cloud-murakumo.worker/run-job` unmodified, with
an injected `:execute` (see below). None of `cloud-murakumo`'s job
normalization, model resolution, autoscale, scheduler, or worker logic is
reimplemented here.

## `execute`: mock (tested) vs real (wired, unexercised)

- **`kami.gen.ml3d/mock-execute`** — ignores the invocation and returns a
  freshly-generated fixture GLB (`kami.gen.ml3d.fixture`, a hand-rolled
  8-vertex/12-triangle box with humanoid-ish proportions) plus a made-up
  `:gpu-seconds`. This is what the test suite runs, and what any demo run in
  this dev environment actually exercises. **It is not a TRELLIS/Hunyuan3D-2
  result.**
- **`kami.gen.ml3d/real-execute`** — a thin wrapper around
  `cloud-murakumo.worker/default-execute` (which on JVM calls
  `cloud-murakumo.executor/execute`, dispatching on the invocation's `:via`
  — `:proc` shells out to the `trellis-cuda` image's CLI). It adds one extra
  fail-closed guard: since the `:trellis` engine's invocation is `:via
  :proc` (no backend URL embedded), `default-execute` alone would just
  attempt to spawn a nonexistent `trellis-run` subprocess and fail with a
  raw `IOException`. `real-execute` checks for `MURAKUMO_BACKEND_URL` /
  `COMFY_URL` / `KAMI_RENDER_URL` first and throws a clear, specific
  `ex-info` if none are configured — matching cloud-murakumo's own
  `default-execute` fail-closed contract (`worker.cljc`: "未配線時は明示エラー")
  through this wrapper too. **This function has never been called against a
  live backend** — there isn't one in this dev environment.

`generate-from-image` requires `:execute` explicitly (no silent default),
matching this org's no-silent-fallback convention
(`cloud-murakumo.gen/resolve-model`'s own doc comment: "silent fallback しない").

## Auto-rig: a genuine first-pass heuristic, not a solved problem

ADR-2607051120 is explicit that auto-rigging an arbitrary generated mesh to a
valid VRM humanoid skeleton is unsolved elsewhere in this org — this is new,
nontrivial code (`kami.gen.ml3d.rig`), not glue between two libraries that
already do it.

What it does:

1. Reads the downloaded mesh's `POSITION` accessor (via `vrm.convert/read-
   accessor-f32`) and computes its bounding box.
2. Places 19 standard VRM humanoid joints (hips/spine/chest/neck/head +
   shoulder/upperArm/lowerArm/hand/upperLeg/lowerLeg/foot ×2 sides) at fixed
   height-fraction / lateral-offset-fraction positions within that bounding
   box — rough Vitruvian-style human proportions, **not derived from the
   mesh's actual silhouette** beyond its overall extent. Built via
   `kotoba-lang/skeleton`'s real `bone`/`skeleton`/`animation-clip`/
   `evaluate` (an empty-track clip IS the rest pose — this genuinely
   exercises `skeleton.cljc`'s own pose evaluator, not a hand-rolled
   reimplementation of it).
3. Assigns each mesh vertex to its 2 nearest bone joints by straight-line
   point distance (not bone segments/capsules — the crude part), producing
   real `JOINTS_0`/`WEIGHTS_0` glTF vertex attributes.
4. Assembles a `VrmDocument` directly from `kotoba-lang/vrm`'s
   `vrm.vrm-types`/`vrm.gltf-types` (skin, humanoid bone-name mapping,
   inverse-bind matrices) and calls `vrm.export/export-glb` on it — the same
   GLB writer `vrm.compose/compose`'s own output goes through.

**Why not `vrm.compose/compose`?** `compose` merges multiple
*already-humanoid-rigged* VRM parts sharing one scene (e.g. swap hair while
keeping the body's skeleton — see `kami-gen-procedural`'s use of it for a
`kotoba-lang/character` body that already has bones). Its skin-rebuild phase
only *rebuilds* a skin that already exists on the `:skeleton-base` source; it
has no path for synthesizing a brand-new skin/skeleton for a raw, skinless
input mesh with no existing `:humanoid` mapping — exactly this repo's
problem. So `kami.gen.ml3d.rig` builds the `VrmDocument` by hand instead of
driving it through `compose`'s part-merge machinery, while still reusing
every other layer of `kotoba-lang/vrm` (types, glTF/GLB container, JSON,
export, and `vrm.parse`/`vrm.humanoid` for round-trip validation).

**This heuristic is tested only against this repo's own synthetic box
fixture — never against real TRELLIS/Hunyuan3D-2 output**, because no live
backend was available to generate one in this dev environment. Real
generated meshes will vary wildly in silhouette, pose, and scale; a
height-fraction heuristic will mis-rig anything that isn't roughly a
symmetric, upright, T/A-pose-ish humanoid bounding box. Treat this as a
starting point for a real per-mesh silhouette analysis, not a finished
auto-rig.

The test suite does verify real correctness properties: the exported GLB
round-trips through `vrm.parse/parse-vrm` (a real VRM 1.0 file, not just
"some bytes"), `vrm.humanoid/to-kami-skeleton` re-reads the same 19-bone
skin/skeleton this repo wrote, and the mesh primitive carries real
`JOINTS_0`/`WEIGHTS_0` attributes.

### Bug found and fixed upstream in `kotoba-lang/vrm` along the way

Building the round-trip test above (`auto-rig-glb-round-trips-through-vrm-
parse`) hit a real crash: `vrm.humanoid/to-kami-skeleton` threw
`ArithmeticException: integer overflow` reading an inverse-bind matrix with
any negative translation component (i.e. almost any real humanoid skeleton).
This is the *exact same* bug class `vrm.convert/read-f32-le` had before
`kotoba-lang/vrm` commit `58e4044` ("real bug fix: read-f32-le throws
ArithmeticException on JVM for negative floats") — `vrm.humanoid/read-mat4-
accessor` has its own separate copy of the same byte-assembly pattern that
was never patched, and `vrm`'s own test fixture happened to only ever use
identity (translation-free) inverse-bind matrices, so nothing caught it.
Fixed directly in `kotoba-lang/vrm` (`unchecked-int`, mirroring the existing
fix exactly) with a regression test (`vrm.humanoid-test/to-kami-skeleton-
handles-negative-inverse-bind-translation`); `kotoba-lang/vrm`'s full test
suite (39 tests / 149 assertions) passes after the fix. This benefits every
consumer of `vrm.humanoid/to-kami-skeleton`, not just this repo.

## Second rig stage: UniRig via `cloud-murakumo`'s `:autorig` (ADR-0048 §2)

ADR-0048 §2 adds a real, GPU-inference auto-rigger (**UniRig**, arXiv:2504.12451,
`VAST-AI/UniRig`) alongside the bbox heuristic above — as an **ensemble/cross-
check, not a replacement**. `cloud-murakumo` gained a new `:autorig` `:gen`
function (`:fn/engine :unirig`, `:gpu/class :l4` — much lighter than
`:model3d`'s `:a100-80`, since auto-rigging has no diffusion/rendering stage)
that `kami.gen.ml3d/auto-rig-via-unirig` submits to via the exact same
`cloud-murakumo.gen/job` + `cloud-murakumo.worker/run-job` + injected
`:execute` pattern as `generate-from-image`'s own `:model3d` call:

```
{:mesh-path :model :params}
  -> cloud-murakumo.gen/job            (build+validate the :autorig :gen.job)
  -> cloud-murakumo.worker/run-job     (injected :execute -- mock or real)
  -> vrm.parse/parse-vrm               (round-trip validation)
```

`kami.gen.ml3d/generate-from-image-with-rig-choice` wraps the full pipeline
with a `:rig-strategy` (`:heuristic` (default, unchanged behavior) |
`:unirig` | `:both`). `:both` runs BOTH riggers against the same downloaded
mesh and returns a `compare-rigs` report (bone count + a coarse "does the
joint-name set look like a plausible humanoid" check against VRM 1.0's 15
required bones) — intentionally simple, not a scoring system, matching 2026
head-to-head auto-rig benchmarks (StraySpark) finding even best-in-class
riggers need human cleanup. It never silently swaps the primary `:vrm` result
for UniRig's without the caller asking for `:unirig`/`:both`.

Same fail-closed mock/real split as `:model3d`: **`mock-execute-autorig`**
(tested, used by this repo) ignores the invocation and reruns
`kami.gen.ml3d.rig/auto-rig-glb` against a fresh fixture mesh with
`rig/unirig-mock-bone-plan` — a deliberately different bone plan (adds the
optional `upperChest` bone, 20 bones vs the default plan's 19) so the `:both`
ensemble test has two genuinely different rigs to compare, not two identical
outputs from the same call. **This is not a real UniRig result** — no live
UniRig backend exists in this dev environment, and ADR-0048 does not
authorize spending on one. **`real-execute-autorig`** is real, correctly
wired code that will fail loudly without a configured backend, same as
`real-execute`; it has never been run against a live UniRig endpoint.

## CID / Asset Hub publish

`kami.gen.ml3d/->asset` reuses the exact `content-cid` sha256 convention from
`cloud-murakumo.executor/content-cid` (`"bafy-sha256-" + hex(sha256(bytes))`)
so this repo's CIDs are directly comparable to its 3 sibling `kami-gen-*`
repos', and shapes the result per `gftdcojp/network-isekai`'s
`public/assets/index.edn` `:asset/*` schema (`:asset/kind :model3d`,
`:asset/format :vrm`, CID-addressed `:asset/payload`).

## Develop

```sh
kbb -M:test
```

19 tests / 94 assertions, all against `mock-execute`/`mock-execute-autorig` —
no network, no GPU, no cost.
# Murakumo postprocessor

The bounded heuristic GLB-to-VRM converter is available as a process boundary
for the Hunyuan3D generation service:

```sh
kbb --backend sci scripts/kami-heuristic-vrm-postprocess.cljk --input model.glb --output model.vrm
```

It re-parses the emitted VRM and requires at least the VRM 1.0 mandatory
humanoid mapping before returning success. This proves structural validity,
not animation quality on arbitrary generated meshes; production remains gated
on a real Hunyuan3D artifact visual/rig evaluation and UniRig comparison.
