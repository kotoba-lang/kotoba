(ns mangaka-scene.camera
  "Camera + lighting specs with manga shot grammar.

  Restored from `kami-mangaka-scene/src/camera.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace\") as zero-dependency portable
  CLJC, per ADR-2607010930.

  Ported 1:1: `ShotGrammar`, `Dof`, `CameraSpec` (+ `Default`), `LightRole`,
  `LightSpec` (+ `three_point_key` / `three_point_fill` / `three_point_rim`).

  glam `Vec3` is represented as `[x y z]`. This is the exact data shape the
  sibling `kotoba-lang/kami-mangaka-scene-clj` authoring tier already
  produces (see its README: \"faithful to the Rust public types … variant
  names verbatim\") — this namespace is the restored source of truth those
  types were originally faithful *to*.")

;; ── ShotGrammar ─────────────────────────────────────────────────────────

(def shot-grammars
  "Manga camera shot vocabulary. Variant names verbatim from the Rust enum."
  #{:full-shot :medium-shot :closeup :over-shoulder :dutch :birds-eye :worms-eye})

;; ── Dof ─────────────────────────────────────────────────────────────────

(defn dof
  "Depth-of-field spec: `{:focus-distance-m float :aperture float}`."
  [focus-distance-m aperture]
  {:focus-distance-m focus-distance-m
   :aperture aperture})

;; ── CameraSpec ──────────────────────────────────────────────────────────

(defn default-camera-spec
  "Mirrors `impl Default for CameraSpec`."
  []
  {:eye [0.0 1.6 3.5]
   :target [0.0 1.4 0.0]
   :up [0.0 1.0 0.0]
   :fov-deg 35.0
   :roll-deg 0.0
   :dof nil
   :shot :medium-shot})

(defn camera-spec
  "Build a `CameraSpec`, merging `overrides` onto `default-camera-spec`."
  ([] (default-camera-spec))
  ([overrides] (merge (default-camera-spec) overrides)))

;; ── LightRole / LightSpec ───────────────────────────────────────────────

(def light-roles
  "Variant names verbatim from the Rust `LightRole` enum."
  #{:key :fill :rim :ambient})

(defn light-spec
  [role direction colour intensity]
  {:role role
   :direction direction
   :colour colour
   :intensity intensity})

(defn- normalize3
  "Portable Vec3 normalize — used to reproduce the Rust `three_point_*`
  factories' `Vec3::new(...).normalize()` calls exactly."
  [[x y z]]
  (let [len (Math/sqrt (+ (* x x) (* y y) (* z z)))]
    (if (zero? len)
      [0.0 0.0 0.0]
      [(/ x len) (/ y len) (/ z len)])))

(defn three-point-key
  []
  (light-spec :key (normalize3 [-0.6 -0.8 -0.4]) [1.0 0.96 0.92] 4.0))

(defn three-point-fill
  []
  (light-spec :fill (normalize3 [0.7 -0.4 -0.2]) [0.86 0.92 1.0] 1.4))

(defn three-point-rim
  []
  (light-spec :rim (normalize3 [0.1 -0.2 0.95]) [1.0 1.0 1.0] 2.0))

(defn three-point
  "All three canonical lights, in `[key fill rim]` order."
  []
  [(three-point-key) (three-point-fill) (three-point-rim)])
