# kotoba-lang/kami-gen-hybrid

**Approach 4 of 4** in a head-to-head comparison of 3D-character generation
pipelines built for this org (`kotoba-lang`), covering the same test target —
a "gugugaga" penguin-kigurumi chibi character. See
[ADR-2607051130](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607051130-kami-gen-hybrid-rig-texture-pipeline.md)
for the full design record. Siblings:

- [`kami-gen-procedural`](https://github.com/kotoba-lang/kami-gen-procedural) — Approach 1: fully deterministic EDN-parameter composition, including procedural kigurumi geometry (no ML at all).
- [`kami-gen-sdf-agent`](https://github.com/kotoba-lang/kami-gen-sdf-agent) — Approach 2: LLM-authored SDF/CSG program, refined by a vision-critique loop.
- [`kami-gen-ml3d`](https://github.com/kotoba-lang/kami-gen-ml3d) — Approach 3: cloud-murakumo TRELLIS/Hunyuan3D-2 full mesh synthesis.
- **`kami-gen-hybrid`** (this repo) — Approach 4: deterministic rig/body, ML-generated **texture only**.

## What's real here, and what isn't

This repo's whole point is a narrower, lower-risk ML surface than full mesh
synthesis: **shape stays 100% deterministic/parametric; only the costume's
surface appearance is ML-generated.**

| Piece | Status |
|---|---|
| Body/rig generation (`kotoba-lang/character`) | **Real.** A real call into `character/generate-character`, using that repo's own tested mesh/skeleton/blendshape generation (66 `deftest` forms / 17,843 assertions upstream). |
| `comfyui-clj` workflow graph + execution | **Real.** A real ComfyUI-API-format node graph (`CheckpointLoaderSimple -> CLIPTextEncode -> KSampler -> VAEDecode -> SaveTextureImage`, x3 for albedo/normal/roughness), registered against `comfyui-clj`'s real node registry, validated by its real schema checker, and run through its real cached topological executor. |
| VRM assembly/export (`kotoba-lang/vrm`) | **Real.** A real `.vrm` (GLB + `VRMC_vrm` extension) is written to disk: real geometry/skin/joint accessors, real embedded PNG images, real material -> texture -> image wiring. |
| **Diffusion image generation** | **Not live.** The one actually-ML step — turning a text prompt into pixels — is an injected capability (`:execute-texture`). This repo's tests and demonstration run always use `kami.gen.hybrid.texture/mock-execute-texture`, which returns real PNG files with real per-pixel data (a deterministic checkerboard for albedo/roughness, a flat neutral tangent-space normal map) — **not** a diffusion model's output. |

There is no live ComfyUI/diffusion GPU backend reachable from this dev
environment. This org's own generation backend,
[`network-isekai/backend`](https://github.com/gftdcojp/network-isekai/blob/main/backend/README.md),
lists image/SDXL generation as **"skeleton only, TODO"** in its own status
table as of 2026-07-05 — this repo is a real, motivated *consumer* of that
wiring finishing, not a place that pretends it already has. `kami.gen.hybrid.texture/real-execute-texture`
exists and is structurally correct (submits a ComfyUI `/prompt`, would poll
`/history`, would download the image) but **throws immediately and loudly**
if called without a configured `:endpoint` — it never silently falls back to
the mock.

## Usage

```clojure
(require '[kami.gen.hybrid :as hybrid]
         '[kami.gen.hybrid.texture :as texture])

(hybrid/generate
 {:base :race/human
  :costume-prompt "penguin kigurumi, chibi, gray/black body, yellow beak"
  :seed 42}
 {:execute-texture texture/mock-execute-texture   ; swap for a real backend once one exists
  :output-dir "/tmp/kami-gen-hybrid-demo"})
;; => {:body     <bare parametric humanoid body/rig — no kigurumi geometry>
;;     :workflow <the comfyui-clj workflow EDN>
;;     :textures {:albedo "..." :normal "..." :roughness "..."}  ; real PNG files
;;     :vrm      {:doc <VrmDocument> :path "..." :glb-bytes [...]}}
```

`:body` is `character/generate-character`'s own bare humanoid output (head,
eyes, eyebrows, hair, skinned body — 35-bone VRM 1.0 humanoid skeleton, 52
ARKit blendshape targets) with its `"clothing"` mesh part stripped: the whole
premise of the hybrid split is that costume comes from **texture**, applied
to the bare body's own `:skin` material, not from extra procedural costume
geometry the way `kami-gen-procedural`'s kigurumi hood/bodysuit does.

## Architecture

```
costume-prompt ──(kami.gen.hybrid.workflow/costume-prompt->workflow)──> comfyui-clj workflow EDN
                                                                              │
character/generate-character ──(minus "clothing" part)──> bare body/rig     │ comfyui.exec/execute
                                                                              │ (injected :execute-texture
                                                                              │  capability = the diffusion
                                                                              │  compute step)
                                                                              ▼
                                                             {:albedo :normal :roughness} PNGs
                                                                              │
                          kami.gen.hybrid.vrm-export/assemble-vrm  <─────────┘
                                        │
                                        ▼
                                     .vrm (GLB + VRMC_vrm)
```

- **`kami.gen.hybrid.workflow/costume-prompt->workflow`** — a pure, template-based
  EDN builder (no LLM call, no network, no randomness beyond `:seed`): fills the
  prompt string and the body's UV-unwrapped texture-slot resolution into a fixed
  graph shape. Per ADR-2607051130, this is genuinely fine for v0; a smarter,
  LLM-authored builder (one that varies node *structure* — extra ControlNet/LoRA
  nodes, a different sampler — not just these fixed slots) can be swapped in later
  behind `kami.gen.hybrid/generate`'s `:graph-builder` option, same injected-seam
  convention as this org's other propose/critique-shaped generator repos (e.g.
  sibling `kami-gen-sdf-agent`).
- **`kami.gen.hybrid.nodes`** — the actual `comfyui-clj` node pack registered for
  the run: `CheckpointLoaderSimple` / `CLIPTextEncode` / `EmptyLatentImage` are pure
  data plumbing; `KSampler` closes over the injected `execute-texture` capability
  (the one real diffusion-compute step); `VAEDecode` is a documented no-op
  pass-through (the mock capability already returns pixel-space RGBA, so there is
  nothing to decode — kept in the graph for shape-fidelity with real ComfyUI, not
  faked busywork); `SaveTextureImage` does real file IO (`javax.imageio`) — real
  PNG bytes, not injected, since writing a file isn't "heavy compute."
- **`kami.gen.hybrid.texture`** — `mock-execute-texture` (deterministic
  checkerboard/flat-normal fixtures) and `real-execute-texture` (structurally
  complete, fails loudly without a live endpoint).
- **`kami.gen.hybrid.vrm-export`** — body + textures -> `.vrm`. `kotoba-lang/vrm`'s
  own `vrm.compose`/`vrm.part` operate on *already-glTF* `VrmDocument`s (merging
  existing avatars); there is no published `character`-mesh -> glTF adapter
  anywhere in the dependency graph, so this namespace is this repo's own,
  disclosed value-add: per-material vertex/index/joint/weight buffer encoding
  (following `character.export`'s proven GLB-chunk technique, extended with
  skin/joints/inverseBindMatrices/humanoid-bone-mapping/embedded-images), then
  handed to `vrm.export/export-glb` for the real VRM 1.0 GLB serialization.

  Every mesh part shares one skin: `character.body/skin-body`'s inverse-square-
  distance auto-skinning (`character.body`'s own documented approximation) is
  applied — via that same public function — to the head/eye/eyebrow/hair parts
  too, since `character/generate-character` upstream only skins the body part
  but this exporter merges all `:skin`-material parts into one glTF primitive
  requiring one shared vertex-weight accessor. This is a natural, disclosed
  extension of an approximation `character.body` already uses, not a new one
  invented here.

## Known gaps (disclosed, not hidden)

- **No live diffusion backend** (see above) — the load-bearing caveat of this
  entire repo.
- **UV atlas packing**: `character.body/ring-mesh` maps each mesh part into its
  own full `[0,1]x[0,1]` UV space rather than a shared packed atlas (an upstream
  `character` limitation, not something this repo hides — see
  `kami.gen.hybrid/skin-uv-bbox`'s docstring). `texture-slot-resolution` computes
  a real (if currently always-square) resolution from that UV extent.
- **Blend shapes aren't re-embedded as glTF morph targets** in the exported
  `.vrm` — `:body`'s `:blendshape-targets` (52 ARKit targets, straight from
  `character`) are still returned/available for a caller that wants them; wiring
  them into the GLB's morph-target accessors is a real, disclosed follow-up, not
  a claim this repo already makes.
- **Fidelity ceiling**: this approach cannot reproduce a reference image's
  non-humanoid rounded penguin-suit silhouette — only its coloring/markings as a
  texture skin over a humanoid body shape. Expected, and the direct comparison
  point against Approach 1/3's sibling repos.

## Develop

```bash
kbb -M:test     # 4 deftest / 54 assertions, all against the mock texture executor
kbb -M:lint      # clj-kondo, errors fail
```

Deps (`:local/root`, sibling checkouts under this workspace):
`kotoba-lang/character` (body/rig), `com-junkawasaki/comfyui-clj` (texture
node-graph engine, which itself depends on `com-junkawasaki/langchain-clj`),
`kotoba-lang/vrm` (VRM assembly/export).
