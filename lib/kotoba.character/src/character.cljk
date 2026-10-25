(ns character
  "KAMI Character — MetaHuman-compatible character SDK for KAMI Engine.
  Restored from the legacy kami-engine/kami-character Rust crate
  (deleted in kotoba-lang/kami-engine PR #82, 'Remove Rust workspace
  from kami-engine') as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root). Native execution (wgpu /
  wasmtime / wasmi) stays substrate; this namespace tree owns the
  CLJC contracts / data interpreters / EDN IR for the character
  domain: parametric face/body/hair generation, MetaHuman DNA
  calibration + FACS, control rig, and animation blueprint.

  ## SDK Overview

  ### Character Pipeline
  ```
  Photo -> Murakumo VL -> CharacterDef + HairStyle + MetaHumanDna
    -> generate-character / metahuman/generate-metahuman / dna/from-bytes
    -> CharacterMesh / MetaHumanMesh / TriangulatedMesh
    -> export/export-glb / SkinnedVertex GPU upload
  ```

  ### MetaHuman DNA Pipeline
  ```
  .dna binary (Epic Games) -> dna/from-bytes -> meshes + joints + blend shapes
    -> dna/triangulate-mesh -> positions/normals/UVs/indices (WebGPU ready)
    -> dna/to-skeleton -> bone hierarchy
  ```

  ### Hair Generation Pipeline
  ```
  HairStyle params -> hair-gen/generate-groom -> GroomAsset (strand curves)
    -> groom/to-hair-cards -> HairCard (quad strips for rasterization)
    -> groom/to-kgr / groom/from-kgr -> .kgr binary (storage)
  ```

  ### Face Animation Pipeline
  ```
  FACS AU weights -> control-rig/evaluate -> bone transforms
    -> anim-blueprint/update -> state machine -> blend tree -> pose
  ```

  Namespaces: `character.params` (parametric definitions),
  `character.math` (glam-compatible Vec3/Quat/Mat4), `character.bin`
  (portable binary IO), `character.base-mesh`, `character.blendshape`,
  `character.hair`, `character.body`, `character.material`,
  `character.export` (GLB), `character.metahuman` (DNA/FACS/LOD),
  `character.dna` (.dna parser), `character.skeletal-mesh` (.ksm),
  `character.groom` (.kgr), `character.hair-gen`, `character.control-rig`,
  `character.anim-blueprint`, `character.space` (ADR-0048 §1 tagged-point
  coordinate-space-safety convention — see `generate-character-tagged`)."
  (:require [character.base-mesh :as base-mesh]
            [character.blendshape :as blendshape]
            [character.hair :as hair]
            [character.body :as body]
            [character.params :as params]
            [character.space :as space]))

(def material-ids #{:skin :eye-white :iris :pupil :lip :eyebrow :hair :clothing :eyelash})

(defn generate-character
  "Generate a complete character mesh from a CharacterDef map. Returns
  `{:parts [MeshPart ...] :skeleton Skeleton :blendshape-targets [...]}`."
  [def]
  (let [{:keys [vertices indices]} (base-mesh/generate-head 48 64)
        head-verts (-> vertices
                        (blendshape/apply-face-shape (:face def))
                        (blendshape/apply-eye-shape (:eyes def))
                        (blendshape/apply-nose-shape (:nose def))
                        (blendshape/apply-mouth-shape (:mouth def)))
        head-verts (base-mesh/laplacian-smooth head-verts indices 2 0.2)
        head-normals (base-mesh/compute-normals head-verts indices)
        head-uvs (base-mesh/frontal-uv head-verts)
        head-vertices (vec (map-indexed (fn [i pos] {:position pos :normal (nth head-normals i) :uv (nth head-uvs i)}) head-verts))
        eye-parts (base-mesh/generate-eyes (:eyes def))
        eyebrow-parts (base-mesh/generate-eyebrows (:brows def))
        hair-part (hair/generate-hair (:hair def))
        skeleton (body/generate-humanoid-skeleton (:height (:body def)))
        body-part (body/skin-body (body/generate-body (:body def) (:bones skeleton)) (:bones skeleton))
        clothing-part (body/generate-clothing (:clothing def) (:body def))
        expression-targets (blendshape/generate-arkit-targets head-verts)
        head-part {:name "head" :vertices head-vertices :indices indices :material :skin}
        parts (into [head-part] (concat eye-parts eyebrow-parts))
        parts (conj parts hair-part body-part clothing-part)]
    {:parts parts :skeleton skeleton :blendshape-targets expression-targets}))

;; ---------------------------------------------------------------------------
;; ADR-0048 §1 — coordinate-space-safety convention (additive; does NOT
;; change `generate-character`'s existing bare-`[x y z]`-vector shape)
;; ---------------------------------------------------------------------------

(def head-local-part-names
  "The exact `:name`s `generate-character` builds from the HEAD-LOCAL
  generators (`character.base-mesh/generate-head`/`generate-eyes`/
  `generate-eyebrows`, `character.hair/generate-hair`) — centred at local
  origin, NOT at the head bone's actual world position. Every other part
  this fn produces (`\"body\"`/`\"clothing\"`, from `character.body`) bakes
  WORLD-space positions in at generation time already. This is the exact
  split `kami-gen-hybrid` commit 848012e hand-diagnosed as the root cause
  of eye/hair vertices being skinned to `leftShoulder`/`rightShoulder`
  instead of `head` — `character` (not a downstream consumer guessing by
  name) is the authority on which of its own parts are which space, so
  this table lives here, once, rather than being re-derived (or
  mis-derived) by every caller that needs to know."
  #{"head" "eye_white_l" "eye_white_r" "iris_l" "iris_r"
    "pupil_l" "pupil_r" "eyebrow_l" "eyebrow_r" "hair"})

(defn part-space
  "`:head-local` for a part named in `head-local-part-names`, else
  `:world` (matches every part `generate-character` produces today —
  `\"body\"`/`\"clothing\"` and any future world-space part fall through to
  `:world` by default)."
  [part-name]
  (if (contains? head-local-part-names part-name) :head-local :world))

(defn generate-character-tagged
  "Like `generate-character`, but every part's vertex `:position` is a
  `character.space` TAGGED point (`{:space :head-local|:world :xyz [x y
  z]}`) instead of a bare `[x y z]` vector — ADR-0048 §1's coordinate-
  space-safety convention, applied at MESH-PART granularity (see
  `character.space`'s ns docstring 'Retrofit scope' for why not per-
  internal-vertex-math-call).

  ADDITIVE, not a breaking change to `generate-character`: existing
  callers of `generate-character` (`kami-gen-procedural`,
  `kami-app-character-creator`) keep consuming the original bare-vector
  shape completely unchanged. Use `generate-character-tagged` from any NEW
  caller that combines parts across spaces before further processing
  (skin-weighting, GLB export, ...) — the exact bug class (mixing
  head-local and world-space vertices as if they shared one frame) that
  motivated ADR-0048 in the first place."
  [def]
  (let [{:keys [parts] :as result} (generate-character def)]
    (assoc result :parts
           (mapv (fn [part] (space/tag-part (part-space (:name part)) part)) parts))))
