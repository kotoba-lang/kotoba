(ns kami.gpu
  "GPU-pipeline IR contract — the capability-gated render graph.

   Premised on the WebGPU / WebGL2 pipeline model (vertex / fragment / compute · bind groups ·
   render passes · instanced draws), so ONE EDN graph maps to every GPU backend:
     • WebGPU   — web (kami.webgpu) + native (wgpu)
     • WebGL2   — web fallback (wgpu downlevel, or a CLJS WebGL renderer)
     • Metal / Vulkan / DX12 — native via wgpu + naga (WGSL → MSL/SPIR-V/HLSL)
     • PS5 / Switch — vendor transpile of the same WGSL (PSSL / NVN)
   Canvas2D is deliberately NOT a target — its immediate-mode 2D output diverges from the GPU
   pipeline, so it would break 'same EDN ⇒ same output'. 2D is expressed as GPU instanced quads.

   WebGL2 lacks compute shaders and storage buffers, so not every pass runs everywhere. A backend
   advertises its `:caps`; a pass declares what it `:requires`; `resolve-graph` drops the passes a
   backend can't run (e.g. a compute pass on WebGL2) and reports them — so the same graph degrades
   gracefully per target instead of failing. `.cljc`: shared by the web (shadow-cljs) and bb/JVM.")

;; ── backend capability tiers ─────────────────────────────────────────────────────────────────────
;; A real backend fills these by feature-detecting the device; these are the canonical profiles.
(def caps-webgpu  {:backend :webgpu  :compute true  :storage true  :instancing true})
(def caps-native  {:backend :native  :compute true  :storage true  :instancing true})  ;; wgpu Metal/Vulkan/DX12
(def caps-console {:backend :console :compute true  :storage true  :instancing true})  ;; PS5/Switch (vendor)
(def caps-webgl2  {:backend :webgl2  :compute false :storage false :instancing true})  ;; the degraded web tier

(def tiers {:webgpu caps-webgpu :native caps-native :console caps-console :webgl2 caps-webgl2})

;; ── capability resolution ────────────────────────────────────────────────────────────────────────
(defn missing-caps
  "The capabilities a pass requires that the backend's caps don't provide."
  [caps pass]
  (vec (remove #(true? (get caps %)) (:requires pass))))

(defn pass-runnable?
  "Does the backend (caps) satisfy a pass's :requires? (no :requires ⇒ always runnable)."
  [caps pass]
  (empty? (missing-caps caps pass)))

(defn resolve-graph
  "Filter a render graph's ordered :passes to those the backend can run on this `caps` tier.
   Returns the graph with :passes narrowed, plus :caps and a :skipped report
   [{:pass id :missing [cap…]} …] — so a WebGL2 backend transparently drops compute passes
   (ray-tracing, gaussian-splat, strand) while the raster core renders identically everywhere."
  [caps graph]
  (let [runnable (filterv #(pass-runnable? caps %) (:passes graph))
        skipped  (vec (for [p (:passes graph) :when (not (pass-runnable? caps p))]
                        {:pass (or (:id p) (:pipeline p)) :missing (missing-caps caps p)}))]
    (assoc graph :passes runnable :caps caps :skipped skipped)))

(defn resolve-for
  "resolve-graph by tier keyword (:webgpu/:webgl2/:native/:console)."
  [tier graph]
  (resolve-graph (get tiers tier caps-webgpu) graph))

(defn caps-from-device
  "Build a caps map from a backend kind + detected device feature flags, e.g.
   (caps-from-device :webgpu {:compute true :storage true})."
  [backend flags]
  (merge {:backend backend :compute false :storage false :instancing true} flags))

;; ── authoring helper ─────────────────────────────────────────────────────────────────────────────
(defn requires
  "Tag a pass with the capabilities it needs (e.g. a compute pass → (requires p :compute :storage))."
  [pass & caps]
  (update pass :requires (fnil into []) caps))
