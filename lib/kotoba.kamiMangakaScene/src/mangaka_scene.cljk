(ns mangaka-scene
  "kami-mangaka-scene — headless 3D scene composition facade for
  mangaka.etzhayyim.com, restored as zero-dependency portable CLJC.

  Restored from `kami-mangaka-scene/src/lib.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace\") per ADR-2607010930. The
  original composed existing `kami-*` crates (`kami-vrm` +
  `kami-scene-graph` + `kami-render` + `kami-postfx` + more) behind a P0
  skeleton (\"types + builder API\"; renderer/simulation wiring was P1-P4,
  largely unimplemented before deletion).

  This restoration ports every portable data type and pure function from
  every `src/*.rs` module:

    - `mangaka-scene.camera`  <- camera.rs   (ShotGrammar, CameraSpec, LightSpec, LightRole, Dof)
    - `mangaka-scene.pose`    <- pose.rs     (PoseSpec, BoneRotation, IkTarget, Expression)
    - `mangaka-scene.lexicon` <- lexicon.rs  (pose_preset, expression_preset)
    - `mangaka-scene.sim`     <- sim.rs      (FxKind)
    - `mangaka-scene.render`  <- render.rs   (RenderPasses, RenderOpts, RenderResult *shapes*)
    - `mangaka-scene.scene`   <- scene.rs    (Transform, EnvironmentSpec, Anchor, MangakaScene
                                               portable subset: new/set-background/set-camera/
                                               add-light/character-ids/to-jsonld/from-jsonld)

  NOT ported (native-only, out of scope for portable CLJC — see each
  namespace's own docstring for the exact split):

    - `renderer.rs` — headless wgpu render pipeline (GPU device, pipelines, PNG readback).
    - `web.rs`       — wasm-bindgen browser preview surface (shares renderer.rs's wgpu state).
    - `py.rs`        — PyO3 bindings (`kami_mangaka_scene` Python extension module, built via
                        maturin per `pyproject.toml`'s `[tool.maturin] features = [\"python\"]`).
                        `pyproject.toml` is packaging config for that PyO3 wheel, not a separate
                        Python tool with its own logic — there is nothing Python-side to port.
    - `scene.rs`'s VRM-bound methods — `load_character`, `pose`'s live bone application,
      `tick`/`settle` (spring-bone simulation), `add_prop`'s glTF parsing,
      `compute_node_worlds`/`walk_node` (glTF scene-graph matrix composition). These require a
      live `kami_vrm::VrmDocument` + `kami_skeleton::Skeleton`, which are external crates not
      restored in this repo.

  Relationship to `kotoba-lang/kami-mangaka-scene-clj`: that is a DIFFERENT,
  already-restored repo — a live Clojure authoring tier (never part of the
  deleted Rust workspace) that emits the exact JSON-LD `MangakaScene::from_jsonld`
  here reads. This repo is the restored Rust-side counterpart those types were
  always faithful to. Do not confuse the two."
  (:require [mangaka-scene.camera :as camera]
            [mangaka-scene.pose :as pose]
            [mangaka-scene.lexicon :as lexicon]
            [mangaka-scene.sim :as sim]
            [mangaka-scene.render :as render]
            [mangaka-scene.scene :as scene]))

;; ── Convenience re-exports (mirrors lib.rs's `pub use`) ─────────────────

(def camera-spec camera/camera-spec)
(def default-camera-spec camera/default-camera-spec)
(def light-spec camera/light-spec)
(def shot-grammars camera/shot-grammars)

(def pose-spec pose/pose-spec)
(def rest-pose pose/rest-pose)
(def expressions pose/expressions)

(def pose-preset lexicon/pose-preset)
(def expression-preset lexicon/expression-preset)

(def render-opts render/render-opts)
(def default-render-opts render/default-render-opts)
(def render-result render/render-result)
(def render-passes-all render/render-passes-all)

(def fx-kinds sim/fx-kinds)

(def new-scene scene/new-scene)
(def default-transform scene/default-transform)
(def environment-spec scene/environment-spec)
(def to-jsonld scene/to-jsonld)
(def from-jsonld scene/from-jsonld)

;; ── SceneError ────────────────────────────────────────────────────────
;; Mirrors the Rust `SceneError` enum (`thiserror`-derived variants). Errors
;; here are plain data `{:type <keyword> :message string}` rather than
;; exceptions — callers `throw`/`ex-info` at the boundary that needs it.

(def scene-error-types
  #{:vrm-decode :gltf-decode :render :jsonld})

(defn scene-error
  [type message]
  {:type type :message message})
