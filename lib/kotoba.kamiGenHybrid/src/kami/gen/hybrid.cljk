(ns kami.gen.hybrid
  "ADR-2607051130 (Approach 4 of 4, `com-junkawasaki/root` /
  `90-docs/adr/2607051130-kami-gen-hybrid-rig-texture-pipeline.md`):
  deterministic parametric rig/body from `kotoba-lang/character`, with
  ONLY the costume's surface appearance ML-generated (a `comfyui-clj`
  texture node graph), assembled into a `.vrm` via `kotoba-lang/vrm`.

  What's real in this namespace: body/rig generation (a real call into
  `kotoba-lang/character`'s own `generate-character`), the `comfyui-clj`
  workflow graph and its execution (a real node registry, real topological
  execution, real validation against that engine's own schema), and VRM
  assembly/export (a real GLB/VRM file with real embedded geometry,
  skinning, and texture images). What's NOT real: diffusion image
  generation. `execute-texture` is an injected capability — this repo's
  tests and its own demonstration run always inject
  `kami.gen.hybrid.texture/mock-execute-texture` (deterministic checkerboard/
  flat-normal fixture PNGs, real files with real pixels, not learned
  output). See the README for why: this org's own `network-isekai/backend`
  lists image/SDXL generation as \"skeleton only, TODO\" as of 2026-07-05.

  Unlike its three portable (`.cljc`) dependencies (`character`,
  `comfyui-clj`, `vrm`), this repo's own orchestration/glue code is
  JVM-only `.clj` — it needs real file IO (`javax.imageio` PNG encode,
  `java.nio.file` reads) that isn't part of what those libraries' own
  portability contracts cover."
  (:require [character :as character]
            [character.params :as params]
            [comfyui.node :as node]
            [comfyui.workflow :as wf]
            [comfyui.exec :as exec]
            [kami.gen.hybrid.nodes :as nodes]
            [kami.gen.hybrid.workflow :as hwf]
            [kami.gen.hybrid.vrm-export :as vrm-export]))

;; ── supported bases ──────────────────────────────────────────────────
;; v0 supports exactly one base preset (`:race/human` -> `character.params/
;; default-character-def`); this table is the injection seam for adding
;; more later (e.g. body-preset variants via `character.params/resolve-
;; body-preset`) without changing `generate`'s contract.

(def supported-bases
  {:race/human params/default-character-def})

(defn- base-character-def [base]
  (if-let [f (get supported-bases base)]
    (f)
    (throw (ex-info "kami.gen.hybrid: unsupported :base"
                     {:base base :supported (set (keys supported-bases))}))))

;; ── body/rig (deterministic, no ML) ──────────────────────────────────

(defn bare-body
  "Calls `character/generate-character-tagged` for `base` and strips its
  `\"clothing\"` mesh part. ADR-2607051130: the whole point of this
  hybrid split is that costume comes from TEXTURE (the diffusion-generated
  albedo/normal/roughness maps applied to the bare body's own `:skin`
  material), not from extra procedural costume geometry the way
  `kami-gen-procedural`'s kigurumi hood/bodysuit approach does — so this
  is `compose-costumed-character`'s body half, minus that geometry,
  exactly as the ADR specifies. Guaranteed-valid topology/UVs/blendshapes
  come straight from `character`'s own generation + its own test suite (99
  deftest forms / 53,452 assertions) — nothing about that guarantee is
  re-verified here, it's inherited.

  ADR-0048 §1 follow-up: uses `generate-character-tagged` (not the bare-
  vector `generate-character`) so every part's vertex `:position` carries
  its `character.space` `:space` tag (`:head-local` for head/eyes/
  eyebrows/hair, `:world` for body/clothing) all the way to
  `kami.gen.hybrid.vrm-export/assemble-vrm`, which is exactly where the
  ADR's motivating bug (commit 848012e — head-local vertices skin-weighted
  as if they were world-space) happened. `skin-uv-bbox`/`nodes.clj` below
  only ever read `:uv`, never `:position`, so tagging is transparent to
  them.

  Returns `{:parts :skeleton :blendshape-targets :character-def}` — the
  same shape `character/generate-character-tagged` returns, plus
  `:character-def` (the resolved def, needed downstream by
  `kami.gen.hybrid.vrm-export` for per-material PBR factors)."
  [base]
  (let [def (base-character-def base)
        built (character/generate-character-tagged def)]
    (-> built
        (update :parts (fn [parts] (vec (remove #(= "clothing" (:name %)) parts))))
        (assoc :character-def def))))

;; ── UV-unwrapped texture slot resolution ──────────────────────────────

(defn skin-uv-bbox
  "UV bounding box across every `:skin`-material part's vertices. Real
  computation over real per-vertex UV data — not a hardcoded constant —
  though in practice it comes out ~[0,1]x[0,1] for every part here, since
  `character.body/ring-mesh` maps each of its parts into its own full
  [0,1]x[0,1] UV space rather than a shared packed atlas (a real, disclosed
  limitation of the upstream body generator, not something this function
  hides)."
  [parts]
  (let [uvs (for [{part-mat :material :keys [vertices]} parts
                  :when (= part-mat :skin)
                  {:keys [uv]} vertices]
              uv)]
    (when (empty? uvs)
      (throw (ex-info "skin-uv-bbox: no :skin-material vertices found" {:parts (map :name parts)})))
    (reduce (fn [[minu minv maxu maxv] [u v]]
              [(min minu u) (min minv v) (max maxu u) (max maxv v)])
            [##Inf ##Inf ##-Inf ##-Inf]
            uvs)))

(defn texture-slot-resolution
  "`{:width :height}` for the shared `:skin` texture (albedo/normal/
  roughness all target the same material slot / resolution), derived from
  `skin-uv-bbox`'s real UV extent scaled to `base-resolution` px along the
  longer UV axis. Given `skin-uv-bbox`'s ~square input (see its docstring)
  this comes out `base-resolution` x `base-resolution` in practice."
  ([parts] (texture-slot-resolution parts 256))
  ([parts base-resolution]
   (let [[minu minv maxu maxv] (skin-uv-bbox parts)
         du (max 1e-6 (- maxu minu))
         dv (max 1e-6 (- maxv minv))
         longer (max du dv)]
     {:width (int (max 8 (Math/round (* base-resolution (/ du longer)))))
      :height (int (max 8 (Math/round (* base-resolution (/ dv longer)))))})))

;; ── prompt -> workflow -> executed textures -> vrm ────────────────────

(defn generate
  "`brief`: `{:base :costume-prompt :seed}` (e.g. `{:base :race/human
  :costume-prompt \"penguin kigurumi, chibi, gray/black body, yellow beak\"
  :seed 42}`).

  `caps` (all but `:execute-texture` optional):
  - `:execute-texture` (required) — the injected diffusion-compute
    capability, `(fn [params] -> {:width :height :format :rgba8 :pixels
    <byte-array>})`. `kami.gen.hybrid.texture/mock-execute-texture` for
    tests/demos; `real-execute-texture` for a live backend (throws loudly
    without a configured `:endpoint` — see its docstring).
  - `:output-dir` — where generated PNGs + the final `.vrm` are written
    (default: a fresh temp dir).
  - `:graph-builder` — `(fn [costume-prompt opts] -> {:workflow :targets})`,
    default `kami.gen.hybrid.workflow/costume-prompt->workflow` (a pure
    template; the injection seam for a future LLM-authored graph builder
    that varies node structure, not just these fixed slots — see that
    namespace's docstring).
  - `:base-resolution` — texture-slot px size (default 256).

  Returns `{:body :workflow :textures :vrm}` per the ADR."
  [{:keys [base costume-prompt seed] :or {seed 0}}
   {:keys [execute-texture output-dir graph-builder base-resolution]
    :or {graph-builder hwf/costume-prompt->workflow
         base-resolution 256}}]
  (when-not (fn? execute-texture)
    (throw (ex-info "kami.gen.hybrid/generate: :execute-texture capability is required" {})))
  (let [output-dir (or output-dir
                        (str (System/getProperty "java.io.tmpdir") "/kami-gen-hybrid-" (System/nanoTime)))
        body (bare-body base)
        {:keys [width height]} (texture-slot-resolution (:parts body) base-resolution)
        {:keys [workflow targets]} (graph-builder costume-prompt {:width width :height height :seed seed})
        reg (node/registry (nodes/pack execute-texture output-dir))
        validation (wf/validate reg workflow)
        _ (when-not (:valid? validation)
            (throw (ex-info "kami.gen.hybrid/generate: built workflow failed comfyui-clj validation"
                             validation)))
        {:keys [results]} (exec/execute {:registry reg} workflow {:targets targets})
        textures {:albedo (first (get results "save_albedo"))
                  :normal (first (get results "save_normal"))
                  :roughness (first (get results "save_roughness"))}
        vrm (vrm-export/assemble-vrm body textures {:output-dir output-dir})]
    {:body body :workflow workflow :textures textures :vrm vrm}))
