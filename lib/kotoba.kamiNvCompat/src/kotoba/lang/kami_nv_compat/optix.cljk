(ns kotoba.lang.kami-nv-compat.optix
  "Drop-in NVIDIA OptiX® C-style API-compat facade — portable .cljc port of
  src/optix.ts. Mirrors the documented public surface of optix.h (device
  context / module / program group / pipeline / shader binding table /
  launch) so existing OptiX host code ports to KAMI via require-path-only
  changes.

  `optixLaunch` dispatches to kami-rt (WebGPU ray-query class WGSL traversal
  + CPU fallback) rather than a no-op success.

  OptixDeviceContext accumulates modules/pipelines as they're created
  against it (TS mutates `context._modules`/`_pipelines` arrays) — the one
  piece of genuine mutable state in this facade, so :modules/:pipelines are
  atoms, matching the atom-per-instance pattern used throughout this port
  (e.g. murakumo-render/farm, amenominaka/application). Everything else
  (compile options, module/pipeline/SBT records) is plain immutable data.

  Dropped one TS-only mechanism: the pre-allocated-`framebuffer`-to-write-
  into option on OptixLaunchParams. That's a JS/GPU-host perf convention
  (reuse a Float32Array instead of allocating one per launch); Clojure's
  render calls throughout this port (kami-rt.index/trace-image[-cpu], the
  KamiViewerExtension precedent) always return a FRESH framebuffer, so
  optix-launch / optix-launch-async simply return {:result :framebuffer}
  (+ :backend for the async-shaped one) rather than writing into (and
  length-validating) a caller-supplied buffer.

  Clean-room: this is a from-spec re-implementation of the OptiX *public
  API names* (Google v. Oracle, 593 U.S. ___ (2021)). No OptiX source,
  headers, PTX, or SDK binaries are used. The canonical engine has a
  distinct name — `hikari-rt` / `kami-rt` (see kami-rt.index).

  Trademark: NVIDIA® and OptiX® are trademarks of NVIDIA Corporation; this
  project is not affiliated with or endorsed by NVIDIA.

  ADR-2605261800 §D1/D6 (nv-compat facade), R1.2 OptiX surface. Wave 43 of
  ADR-2607020130."
  (:require [kotoba.lang.kami-nv-compat.kami-rt.index :as rt]))

;; ── result codes (optix.h OptixResult subset) ─────────────────────────────

(def optix-success 0)
(def optix-error-invalid-value 7001)
(def optix-error-host-out-of-memory 7002)
(def optix-error-launch-failure 7050)

;; ── compile / pipeline option records ─────────────────────────────────────

(defn default-module-compile-options []
  {:max-register-count 0 :opt-level 3 :debug-level 0})

(defn default-pipeline-compile-options []
  {:uses-motion-blur         false
   :traversable-graph-flags  0
   :num-payload-values       2
   :num-attribute-values     2
   :exception-flags          0})

;; ── opaque handles ───────────────────────────────────────────────────────
;;
;; OptixDeviceContext {:log-callback :log-callback-level
;;                      :modules (atom []) :pipelines (atom [])}
;; OptixModule         {:context :source-wgsl :compile-options}
;; OptixProgramGroup   {:module :kind}     — kind: :raygen :miss :hitgroup :callable
;; OptixPipeline       {:context :program-groups :compile-options}
;; OptixShaderBindingTable {:raygen-record :miss-record-base :hitgroup-record-base}

;; ── constructors (C-style, mirrors optix.py) ──────────────────────────────

(defn optix-device-context-create
  "C-style device context constructor. `cuda-context` is accepted for API
  parity and ignored — kami-rt targets a WebGPU device. `opts` =
  {:log-callback :log-callback-level}."
  ([] (optix-device-context-create nil {}))
  ([cuda-context] (optix-device-context-create cuda-context {}))
  ([_cuda-context opts]
   {:log-callback       (:log-callback opts)
    :log-callback-level (or (:log-callback-level opts) 0)
    :modules            (atom [])
    :pipelines          (atom [])}))

(defn optix-module-create-from-ptx
  "Upstream OptiX builds modules from CUDA PTX/OptiX-IR. kami-rt has no CUDA
  backend; use optix-module-create-from-wgsl instead."
  []
  (throw (ex-info
           (str "optix-module-create-from-ptx requires CUDA PTX; the kami-rt "
                "backend has no CUDA path. Use optix-module-create-from-wgsl "
                "(KAMI-native) instead.")
           {})))

(defn optix-module-create-from-wgsl
  "KAMI-native extension (not in upstream OptiX): build a module from a WGSL
  string, and register it on `context`."
  [context module-compile-options _pipeline-compile-options wgsl-source]
  (let [mod {:context context :source-wgsl wgsl-source :compile-options module-compile-options}]
    (swap! (:modules context) conj mod)
    mod))

(defn optix-program-group-create
  [_context groups]
  (mapv (fn [g] {:module (:module g) :kind (:kind g)}) groups))

(defn optix-pipeline-create
  "Build a pipeline from program groups, and register it on `context`."
  [context pipeline-compile-options program-groups]
  (let [pl {:context context :program-groups (vec program-groups) :compile-options pipeline-compile-options}]
    (swap! (:pipelines context) conj pl)
    pl))

(defn optix-shader-binding-table-create
  ([] (optix-shader-binding-table-create {}))
  ([init]
   {:raygen-record        (or (:raygen-record init) 0)
    :miss-record-base     (or (:miss-record-base init) 0)
    :hitgroup-record-base (or (:hitgroup-record-base init) 0)}))

;; ── launch ───────────────────────────────────────────────────────────────
;;
;; OptixLaunchParams {:scene :camera :width :height :shade? :device?}

(defn- validate-launch [pipeline params]
  (cond
    (empty? (:program-groups pipeline))                        optix-error-invalid-value
    (not (some #(= (:kind %) :raygen) (:program-groups pipeline))) optix-error-invalid-value
    (or (<= (:width params) 0) (<= (:height params) 0))         optix-error-invalid-value
    :else nil))

(defn optix-launch
  "Synchronous launch — dispatches the CPU kami-rt tracer. Returns
  {:result :framebuffer}. Mirrors optixLaunch from optix.py but actually
  traces (R1.2) rather than no-op (R1.0)."
  [pipeline _sbt params]
  (if-let [bad (validate-launch pipeline params)]
    {:result bad :framebuffer nil}
    (try
      (let [res (if (:shade params)
                  (rt/trace-image-cpu (:scene params) (:camera params) (:width params) (:height params) (:shade params))
                  (rt/trace-image-cpu (:scene params) (:camera params) (:width params) (:height params)))]
        {:result optix-success :framebuffer (:framebuffer res)})
      (catch #?(:clj Exception :cljs :default) _
        {:result optix-error-launch-failure :framebuffer nil}))))

(defn optix-launch-async
  "Async-shaped launch — dispatches the WebGPU kami-rt tracer when a device
  is available, transparently falling back to CPU. Returns
  {:result :framebuffer :backend}. Synchronous on JVM (matching the
  rtx-renderer / omni-kit-app precedent — no true I/O concurrency here
  either way); this is the recommended entry point in browsers."
  [pipeline _sbt params]
  (if-let [bad (validate-launch pipeline params)]
    {:result bad :framebuffer [] :backend :cpu}
    (try
      (let [res (rt/trace-image (:scene params) (:camera params) (:width params) (:height params)
                                 {:shade (:shade params) :device (:device params)})]
        {:result optix-success :framebuffer (:framebuffer res) :backend (:backend res)})
      (catch #?(:clj Exception :cljs :default) _
        {:result optix-error-launch-failure :framebuffer [] :backend :cpu}))))

;; ── compat-map metadata ──────────────────────────────────────────────────

(def kami-engine "hikari-rt")
(def adr "ADR-2605261800")
