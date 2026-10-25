(ns kotoba.lang.kami-nv-compat.warp.wgpu-backend
  "WebGPU compute-shader backend for nv-compat/warp — CLJC port of
  src/warp/wgpu-backend.ts.

  On JVM: has-webgpu? returns false; acquire-device returns nil; wgpu-launch
  always falls back to the sync warp/launch path. This is the honest JVM
  behavior — there is no navigator.gpu on the JVM, and the sync fallback
  has identical semantics (sequential execution of the JS kernel fn).

  On CLJS (browser/Deno/Node 22+): the host supplies a reify of IWgpuBackend
  backed by navigator.gpu; wgpu-launch routes to the WebGPU pipeline when
  available. The actual WebGPU buffer/pipeline operations live behind the
  IWgpuBackend capability seam — this namespace never calls navigator.gpu
  directly.

  Types (BindingSpec, WgpuKernel) are portable data shapes shared by both
  paths. Wave 20 of ADR-2607020130.

  `rt-dispatch!` (wave 24) is a second, coarser dispatch entry for kami-rt's
  bespoke ray/path-trace compute kernels: unlike `wgpu-execute` (a generic
  JS-kernel-fn + WgpuKernel dispatch), callers hand it a WGSL source string
  and an ordered list of named buffers ({:binding :kind :data} or {:binding
  :kind :size} for the read_write output buffer) and get the read-back
  framebuffer directly — the host does all buffer/pipeline/bindgroup/encoder
  orchestration, kami-rt's core stays free of raw WebGPU calls."
  (:require [kotoba.lang.kami-nv-compat.warp.warp :as wp]))

;; ── Capability seam ──────────────────────────────────────────────────────

(defprotocol IWgpuBackend
  "Host-supplied WebGPU capability. JVM: no-op (always nil/false). CLJS: backed
  by navigator.gpu."
  (has-gpu? [this])
  (acquire-device [this])
  (wgpu-execute [this kernel dim inputs device])
  (rt-dispatch! [this device wgsl buffers width height]))

;; ── JVM no-op backend ────────────────────────────────────────────────────

(def jvm-backend
  "Default IWgpuBackend for JVM: no WebGPU. All wgpu-launch calls fall back to
  the sync warp/launch path."
  (reify IWgpuBackend
    (has-gpu? [_] false)
    (acquire-device [_] nil)
    (wgpu-execute [_ kernel dim inputs _device]
      (wp/launch {:kernel-fn (:fn kernel) :dim dim :inputs inputs}))
    (rt-dispatch! [_ _device _wgsl _buffers _width _height]
      (throw (ex-info "rt-dispatch!: no WebGPU device on JVM" {})))))

;; ── Feature detection (host-delegated) ───────────────────────────────────

(def ^:dynamic *wgpu-backend* jvm-backend)

(defn has-webgpu?
  "Returns true when a WebGPU-capable backend is bound. On JVM: always false."
  []
  (has-gpu? *wgpu-backend*))

(defn acquire-webgpu-device
  "Acquire (and cache) a WebGPU device, or nil if unavailable. On JVM: always nil."
  []
  (acquire-device *wgpu-backend*))

;; ── Binding declarations (portable data) ─────────────────────────────────

(defn storage-binding
  "Storage binding spec: WpArray input ↔ GPU storage buffer."
  [binding-idx input-idx]
  {:binding binding-idx :kind :storage :input-index input-idx :writeback true})

(defn uniform-binding
  "Uniform binding spec: scalar input ↔ GPU uniform buffer."
  [binding-idx input-idx]
  {:binding binding-idx :kind :uniform :input-index input-idx :writeback false})

;; ── WgpuKernel (portable data) ────────────────────────────────────────────

(defn wgpu-kernel
  "Build a dual JS+WGSL kernel. {:fn :wgsl :bindings :workgroup-size}."
  [{:keys [js wgsl bindings workgroup-size]
    :or {workgroup-size 64}}]
  {:fn js :name (or (:name js) "wgpu-kernel")
   :wgsl wgsl :bindings bindings :workgroup-size workgroup-size})

;; ── wgpu-launch (dispatches to the bound backend) ────────────────────────

(defn wgpu-launch
  "Dispatch a kernel via WebGPU when available; otherwise fall back to sync
  warp/launch. Async on CLJS (returns a js/Promise); sync on JVM (returns nil
  after running)."
  [{:keys [kernel dim inputs device]}]
  (wgpu-execute *wgpu-backend* kernel dim inputs (or device (acquire-webgpu-device))))
