# kotoba-lang/kami-gen-procedural

Deterministic EDN-parameter composed character pipeline — **Approach 1 of 4** in a
head-to-head comparison of ways to build a 3D character-generation pipeline for
`kotoba-lang` (ADR-2607051100, `com-junkawasaki/root`). No ML inference, no per-asset
GPU cost, no PNG/GLB/WAV files checked into this repo: every tunable — body
proportions, costume palette, beak size/angle, hood droop, body-suit padding — is a
plain value in an EDN map, and the whole pipeline from that map to a real `.vrm` is
pure data + pure functions.

This is the direct 3D extension of
[`kotoba-lang/kami-isekai-assets`](https://github.com/kotoba-lang/kami-isekai-assets)'s
`kami.isekai.chargen/compose-character` (2D sprite-primitive composition) — same
"view source + fork, the EDN parameter map is the source of truth, not a binary asset"
philosophy, extended from 2D sprite primitives to real 3D parametric meshes.

## The 4 sibling approaches

All 4 were built standalone against the same test target (a "gugugaga" penguin-kigurumi
chibi character, photoreal Pixar-style reference image) for a direct comparison:

| Repo | Approach | Cost model |
|---|---|---|
| **`kami-gen-procedural`** (this repo) | Deterministic EDN-parameter composition | Zero GPU, zero external services |
| [`kami-gen-sdf-agent`](https://github.com/kotoba-lang/kami-gen-sdf-agent) | LLM-authored SDF/SCAD code | LLM inference per asset |
| [`kami-gen-ml3d`](https://github.com/kotoba-lang/kami-gen-ml3d) | `cloud-murakumo` TRELLIS/Hunyuan3D-2 image-to-3D | GPU inference per asset |
| [`kami-gen-hybrid`](https://github.com/kotoba-lang/kami-gen-hybrid) | Parametric rig (this repo's body/skeleton) + ML texture only | GPU inference for texture only |

This repo's ceiling: it cannot reproduce the reference image's photoreal chibi-CG
shading or an organic sculpted silhouette — output reads as stylized/parametric, not
photoreal. That is the expected, direct comparison point against `kami-gen-ml3d`.

## What it depends on (real APIs, not invented ones)

- [`kotoba-lang/character`](https://github.com/kotoba-lang/character) — parametric
  MetaHuman-compatible body/head/hair/blendshape mesh generator
  (`character/generate-character`), VRM 1.0-compatible humanoid skeleton
  (`character.body/generate-humanoid-skeleton`), and per-part PBR materials
  (`character.material/for-part`).
- [`kotoba-lang/mesher`](https://github.com/kotoba-lang/mesher) — Marching Cubes
  SDF-to-mesh (`mesher/sdf-to-colored-mesh`, `mesher/split-mesh-by-color`) — used here
  for the new "kigurumi" hood/beak costume attachment (a sphere union a tilted cone).
- [`kotoba-lang/vegetation`](https://github.com/kotoba-lang/vegetation) — its
  `mesh-from-profile` "one procedural mesh generator, many profiles" pattern is the
  structural template this repo's costume-attachment code follows (a small set of
  primitive-generating functions parameterized entirely by a plain profile map).
- [`kotoba-lang/vrm`](https://github.com/kotoba-lang/vrm) — VRM 1.0 data types
  (`vrm.vrm-types`), glTF document scaffolding (`vrm.gltf-types`), and GLB byte
  serialization (`vrm.export/export-glb`).

**Real gaps found in the upstream `character` API** (documented in
`kami.gen.procedural`'s namespace docstring, not papered over):

1. `character.params` has no `:proportions`/chibi concept at all. `:limb-scale` maps
   onto `character.body`'s real `:height` field (which already scales torso+limb
   length together); `:head-scale` is a post-hoc uniform vertex scale this repo applies
   to every generated part that isn't `"body"`/`"clothing"`, since `character.base-mesh/
   generate-head` has no size parameter of its own.
2. `character/generate-character` does not attach its rigid parts (head/eyes/eyebrows/
   hair/clothing) to skeleton-bone nodes — only `"body"` gets real `JOINTS_0`/
   `WEIGHTS_0` skin weights. This repo's VRM export is faithful to that: the hood/beak/
   body-suit costume meshes are rigid siblings in the same shared bind-pose coordinate
   frame (this *is* the ADR's "no separate rig needed for a rigid hood"), and only
   `"body"` plus the new `"body-suit"` shell carry real skin weights. Posing the
   exported VRM away from bind pose will move the skinned body but leave head/hair/
   hood/beak/clothing visually fixed — an existing upstream `character` limitation,
   not something this repo introduces or hides.

## Usage

```clojure
(require '[kami.gen.procedural :as proc])

(proc/compose-costumed-character {:base :race/human :costume :penguin-kigurumi :seed 42})
;; => {:body    {:parts [...MeshParts...] :skeleton {:bones [...]} :blendshape-targets [...]}
;;     :costume {:hood [...2 MeshParts, :hood + :beak...] :body-suit MeshPart :params {...}}
;;     :vrm     {:document VrmDocument :glb-bytes [byte-int ...]}
;;     :render/profile {:color [...] :w n :h n :geo :capsule :emissive 0.0}}
```

Every tunable is overridable, nothing is a hidden constant:

```clojure
(proc/compose-costumed-character
 {:seed 7
  :proportions {:head-scale 1.8 :limb-scale 0.55 :head-scale-pivot [0.0 0.0 0.0]}
  :kigurumi {:hood-radius 0.16 :hood-droop 0.08
             :beak-length 0.10 :beak-half-angle 0.4 :beak-tilt -0.4
             :body-suit-padding 0.015 :body-suit-color [0.05 0.05 0.06]
             :palette {:hood-color [0.05 0.05 0.06] :beak-color [0.9 0.5 0.05]}}
  :char-def {:skin {:tone [0.95 0.85 0.75]}}})
```

Publish the result to `network-isekai`'s Asset Hub (`public/assets/index.edn` schema):

```clojure
(proc/publish-to-asset-hub result)
;; => {:asset/id "kami-gen-procedural-bafy-sha256-..." :asset/kind :model3d
;;     :asset/format :vrm :asset/payload {:cid {:hash "bafy-sha256-..."} :bytes N :uri "..."}
;;     :asset/preview {:webgpu true} :asset/deps [...] ...}
```

`:seed` is not cosmetic-only: it deterministically jitters the kigurumi palette
(`character.math/hash-f32`, same deterministic-hash convention `kami-isekai-assets`'s
`kami.isekai.palette/jitter-color` uses) — the same seed always reproduces the same
character; a different seed reproducibly varies it.

Only `:base :race/human` and `:costume :penguin-kigurumi` are implemented; anything
else throws (`character.params` has no race concept to extend to yet — a real
limitation, not a silent wrong-but-valid fallback).

## Develop

```bash
kbb -M:test
```
