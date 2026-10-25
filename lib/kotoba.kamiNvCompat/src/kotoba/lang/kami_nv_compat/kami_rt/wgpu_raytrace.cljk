(ns kotoba.lang.kami-nv-compat.kami-rt.wgpu-raytrace
  "kami-rt WebGPU dispatch path — portable .cljc port of
  src/kami-rt/wgpu-raytrace.ts. Wave 24.

  Compiles raytrace-wgsl, uploads the scene (tris / BVH nodes / triIdx) as
  storage buffers + camera/shade as a uniform, dispatches one thread per
  pixel, reads the RGBA float framebuffer back. Falls back transparently to
  the CPU tracer (bvh/trace-image-sync) when no WebGPU device is available,
  so callers never branch — same contract the warp wgpu-backend established.
  All raw WebGPU buffer/pipeline/bindgroup/encoder orchestration lives behind
  the IWgpuBackend `rt-dispatch!` capability seam; this namespace never calls
  navigator.gpu directly."
  (:require [kotoba.lang.kami-nv-compat.warp.wgpu-backend :as wgpu]
            [kotoba.lang.kami-nv-compat.kami-rt.bvh :as bvh]
            [kotoba.lang.kami-nv-compat.kami-rt.wgsl-shaders :as wgsl]))

(defn pack-params
  "Pack the 8×vec4 uniform block consumed by raytrace-wgsl's `Params`."
  [cam width height num-tris shade]
  (let [o (:origin cam)
        ll (:lower-left cam)
        hh (:horizontal cam)
        vv (:vertical cam)
        ld (:light-dir shade)
        alb (:albedo shade)
        bt (:bg-top shade)
        bb (:bg-bottom shade)]
    (double-array
     [(o 0) (o 1) (o 2) width
      (ll 0) (ll 1) (ll 2) height
      (hh 0) (hh 1) (hh 2) num-tris
      (vv 0) (vv 1) (vv 2) 0
      (ld 0) (ld 1) (ld 2) (:ambient shade)
      (alb 0) (alb 1) (alb 2) 0
      (bt 0) (bt 1) (bt 2) 0
      (bb 0) (bb 1) (bb 2) 0])))

(defn trace-image-gpu
  "Render `width × height` RGBA-float framebuffer on the GPU via WebGPU.
  Resolves to the CPU result when no device is available. Returns
  {:framebuffer :backend}, :backend one of :webgpu :cpu."
  ([soup scene-bvh cam width height]
   (trace-image-gpu soup scene-bvh cam width height bvh/default-shade nil))
  ([soup scene-bvh cam width height shade]
   (trace-image-gpu soup scene-bvh cam width height shade nil))
  ([soup scene-bvh cam width height shade device-override]
   (let [device (or device-override (when (wgpu/has-webgpu?) (wgpu/acquire-webgpu-device)))]
     (if (nil? device)
       {:framebuffer (bvh/trace-image-sync soup scene-bvh cam width height shade)
        :backend :cpu}
       (let [fb-bytes (* width height 4 4)
             params (pack-params cam width height (:count soup) shade)
             buffers [{:binding 0 :kind :storage-read :data (:verts soup)}
                      {:binding 1 :kind :storage-read :data (:nodes scene-bvh)}
                      {:binding 2 :kind :storage-read :data (:tri-index scene-bvh)}
                      {:binding 3 :kind :storage-read-write :size fb-bytes}
                      {:binding 4 :kind :uniform :data params}]
             fb (wgpu/rt-dispatch! wgpu/*wgpu-backend* device wgsl/raytrace-wgsl buffers width height)]
         {:framebuffer fb :backend :webgpu})))))
