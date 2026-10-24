(ns mangaka-scene.render
  "Render options + result *data shapes*.

  Restored from `kami-mangaka-scene/src/render.rs` (kotoba-lang/kami-engine,
  deleted in PR #82) as zero-dependency portable CLJC, per ADR-2607010930.

  Ported: `RenderPasses` (bitflags, as a keyword set), `RenderOpts` (+
  `Default`), `RenderResult` shape.

  NOT ported: the actual GPU execution (`MangakaScene::render` /
  `render_multi`, which delegate to `renderer.rs`'s headless wgpu pipeline)
  — that is native-only and out of scope for a portable CLJC restoration.
  See `mangaka-scene.scene` docstring for the full portable/native split.")

;; ── RenderPasses (bitflags) ──────────────────────────────────────────────

(def render-passes-all
  "Mirrors `RenderPasses::ALL` = BASE | DEPTH | OUTLINE | TONE."
  #{:base :depth :outline :tone})

(defn render-passes
  "Build a `RenderPasses` set from any combination of `:base :depth :outline
  :tone`."
  [& passes]
  (set passes))

;; ── RenderOpts ────────────────────────────────────────────────────────────

(defn default-render-opts
  "Mirrors `impl Default for RenderOpts`. Manga page aspect ~4:5.7 (B5)."
  []
  {:width 1024
   :height 1448
   :passes render-passes-all
   :seed 0})

(defn render-opts
  ([] (default-render-opts))
  ([overrides] (merge (default-render-opts) overrides)))

;; ── RenderResult ──────────────────────────────────────────────────────────

(defn render-result
  "`base-png` / `depth-png` / `outline-png` / `toon-png` are opaque byte
  payloads (native renderer output) — this shape carries them through, it
  does not produce them."
  [{:keys [base-png depth-png outline-png toon-png camera]}]
  {:base-png base-png
   :depth-png depth-png
   :outline-png outline-png
   :toon-png toon-png
   :camera camera})
