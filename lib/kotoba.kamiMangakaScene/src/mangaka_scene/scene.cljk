(ns mangaka-scene.scene
  "Scene root — portable data/state subset of the Rust `MangakaScene`.

  Restored from `kami-mangaka-scene/src/scene.rs` (kotoba-lang/kami-engine,
  deleted in PR #82) as zero-dependency portable CLJC, per ADR-2607010930.

  ## Portable / native split

  The original `scene.rs` wraps a `hecs::World` + per-character VRM runtime
  state (`kami_vrm::VrmDocument`, `kami_skeleton::Skeleton`,
  `kami_vrm::spring::SpringSimulator`) and mixes two concerns:

  1. **Portable scene composition & JSON-LD round-trip** — `MangakaScene::new`,
     `set_background`, `set_camera`, `add_light`, `character_ids`,
     `to_jsonld`, `from_jsonld`. These touch only plain data
     (`Transform` / `EnvironmentSpec` / `CameraSpec` / `LightSpec`) and are
     ported 1:1 below.
  2. **Native-only VRM/GPU execution** — `load_character` (parses VRM glTF
     bytes via `kami_vrm::parse_vrm` + builds a `kami_skeleton::Skeleton`),
     `pose`/`tick`/`settle`/`compute_node_worlds`/`walk_node` (spring-bone
     simulation over a live glTF node graph), `add_prop` (glTF byte
     parsing), `add_wind`/`add_particle_burst` (were unimplemented stubs in
     the original — `kami-atmosphere`/`kami-dec`/`kami-pipelines` wiring
     never landed before deletion). None of this is portable: it requires
     the VRM/glTF/skeleton crates and (for spring simulation) is
     inherently stateful native runtime, not data. **Not ported.**

  This mirrors exactly the shape the sibling `kotoba-lang/kami-mangaka-scene-clj`
  authoring tier already assumes (see its README: it emits `MangakaScene`
  JSON-LD as *pure data, no GPU, no VRM bytes* for the Rust facade to
  consume) — this namespace is the restored Rust-side counterpart of that
  same JSON-LD contract, minus the VRM-bound execution `-clj` never touched
  either.

  `characters` here are lightweight records (`rkey` / `pose-label` /
  `expression` / `root-xform`) rather than live VRM-backed characters —
  exactly the fields `to_jsonld`/`from_jsonld` round-trip in the original,
  and exactly what a caller like `kami-mangaka-scene-clj` would already
  hold as plain data before handing it to the native renderer."
  (:require [mangaka-scene.lexicon :as lexicon]
            [mangaka-scene.pose :as pose]))

;; ── Transform ──────────────────────────────────────────────────────────

(defn default-transform
  []
  {:translation [0.0 0.0 0.0]
   :rotation [0.0 0.0 0.0 1.0]
   :scale [1.0 1.0 1.0]})

(defn transform
  ([] (default-transform))
  ([overrides] (merge (default-transform) overrides)))

;; ── EnvironmentSpec / Anchor ─────────────────────────────────────────────

(defn anchor [name xform]
  {:name name :xform xform})

(defn environment-spec
  [{:keys [biome weather seed ground-size-m layout-anchors]
    :or {layout-anchors []}}]
  {:biome biome
   :weather weather
   :seed seed
   :ground-size-m ground-size-m
   :layout-anchors layout-anchors})

;; ── CharacterId / PropId ───────────────────────────────────────────────

(defn character-id [n] {:id n})
(defn prop-id [n] {:id n})

;; ── MangakaScene ──────────────────────────────────────────────────────

(defn new-scene
  "Mirrors `MangakaScene::new()`."
  []
  {:characters []                       ; ordered vector of character records
   :props []
   :camera nil
   :lights []
   :env nil
   :next-char 0
   :next-prop 0})

(defn character-ids
  [scene]
  (mapv :id (:characters scene)))

(defn set-background
  [scene env]
  (assoc scene :env env))

(defn set-camera
  [scene cam]
  (assoc scene :camera cam))

(defn add-light
  [scene light]
  (update scene :lights conj light))

(defn add-character-record
  "Portable stand-in for the native `load_character` (which decodes VRM
  bytes into a live skeleton). Records a character's authoring-facing
  state directly — `rkey` is the VRM asset key, everything else defaults
  to rest/neutral, matching a freshly-loaded character before any
  `pose`/`expression` call."
  ([scene rkey] (add-character-record scene rkey {}))
  ([scene rkey overrides]
   (let [id (:next-char scene)
         ch (merge {:id id
                    :rkey rkey
                    :root-xform (default-transform)
                    :current-expression :neutral
                    :current-pose-label nil}
                   overrides)]
     (-> scene
         (update :characters conj ch)
         (update :next-char inc)))))

(defn- update-character [scene id f]
  (update scene :characters
          (fn [chs] (mapv (fn [ch] (if (= (:id ch) id) (f ch) ch)) chs))))

(defn pose
  "Portable subset of `MangakaScene::pose`: records the semantic pose label
  and root transform, and resolves the label via `lexicon/pose-preset` for
  informational purposes (bone rotations are returned, not applied to a
  live skeleton — there is none here). Explicit `bones` overrides passed in
  `pose-spec` are layered onto the preset the same way the Rust
  implementation layers them (explicit wins), producing the resolved bone
  rotation list as `:resolved-bones` on the character record."
  [scene id pose-spec]
  (let [preset (when-let [label (:label pose-spec)]
                 (lexicon/pose-preset label))
        explicit (:bones pose-spec)
        by-bone (fn [bones] (into {} (map (juxt :bone identity)) bones))
        resolved (vals (merge (by-bone preset) (by-bone explicit)))]
    (update-character scene id
                       (fn [ch]
                         (assoc ch
                                :root-xform (:root-xform pose-spec)
                                :current-pose-label (:label pose-spec)
                                :resolved-bones (vec resolved))))))

(defn expression
  [scene id emo]
  (update-character scene id #(assoc % :current-expression emo)))

;; ── JSON-LD round-trip ───────────────────────────────────────────────────

(defn to-jsonld
  "Mirrors `MangakaScene::to_jsonld`."
  [scene]
  {"@context" "https://kami.etzhayyim.com/mangaka-scene/v1"
   "characters" (mapv (fn [ch]
                         {"id" (:id ch)
                          "rkey" (:rkey ch)
                          "pose_label" (:current-pose-label ch)
                          "expression" (:current-expression ch)
                          "root_xform" (:root-xform ch)})
                       (:characters scene))
   "props" (mapv (fn [p] {"id" (:id p)}) (:props scene))
   "camera" (:camera scene)
   "lights" (:lights scene)
   "environment" (:env scene)})

(defn from-jsonld
  "Mirrors `MangakaScene::from_jsonld`. Characters / props are scene-local
  handles and intentionally not rehydrated (matches the original's
  behaviour and its own test's comment to that effect) — only
  environment/camera/lights round-trip."
  [v]
  (let [s (new-scene)
        s (if-let [env (get v "environment")] (assoc s :env env) s)
        s (if-let [cam (get v "camera")] (assoc s :camera cam) s)
        s (if-let [lights (get v "lights")] (assoc s :lights (vec lights)) s)]
    s))
