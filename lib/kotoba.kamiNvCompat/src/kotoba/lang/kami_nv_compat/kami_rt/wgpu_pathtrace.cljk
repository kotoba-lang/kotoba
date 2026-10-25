(ns kotoba.lang.kami-nv-compat.kami-rt.wgpu-pathtrace
  "kami-rtx WebGPU dispatch for the Monte-Carlo path tracer — portable .cljc
  port of src/kami-rt/wgpu-pathtrace.ts. Wave 25.

  Uploads geometry + BVH + per-triangle albedo/emission as storage buffers,
  camera + settings as a uniform, dispatches one thread per pixel running
  `spp` paths, reads the RGBA-float framebuffer back. Falls back
  transparently to the CPU tracer (pathtrace/path-trace-sync) when no
  WebGPU device is available.

  Reuses the same warp.wgpu-backend `rt-dispatch!` seam that
  kami-rt.wgpu-raytrace established — this namespace never calls
  navigator.gpu directly."
  (:require [kotoba.lang.kami-nv-compat.warp.wgpu-backend :as wgpu]
            [kotoba.lang.kami-nv-compat.kami-rt.pathtrace :as pt]
            [kotoba.lang.kami-nv-compat.kami-rt.wgsl-shaders :as wgsl]))

(defn pack-path-params
  "Pack the 5×vec4 uniform block consumed by pathtrace-wgsl's `Params`."
  [cam width height settings]
  (let [o (:origin cam)
        ll (:lower-left cam)
        hh (:horizontal cam)
        vv (:vertical cam)
        bg (:background settings)]
    (double-array
     [(o 0) (o 1) (o 2) width
      (ll 0) (ll 1) (ll 2) height
      (hh 0) (hh 1) (hh 2) (max 1 (:samples-per-pixel settings))
      (vv 0) (vv 1) (vv 2) (:max-bounces settings)
      (bg 0) (bg 1) (bg 2) 0])))

(defn path-trace-gpu
  "Path-trace `width × height` on the GPU via WebGPU. Resolves to the CPU
  result when no device is available. Returns {:framebuffer :backend},
  :backend one of :webgpu :cpu."
  ([scene cam width height]
   (path-trace-gpu scene cam width height pt/default-path-settings nil))
  ([scene cam width height settings]
   (path-trace-gpu scene cam width height settings nil))
  ([scene cam width height settings device-override]
   (let [device (or device-override (when (wgpu/has-webgpu?) (wgpu/acquire-webgpu-device)))]
     (if (nil? device)
       {:framebuffer (pt/path-trace-sync scene cam width height settings)
        :backend :cpu}
       (let [fb-bytes (* width height 4 4)
             params (pack-path-params cam width height settings)
             buffers [{:binding 0 :kind :storage-read :data (:verts (:soup scene))}
                      {:binding 1 :kind :storage-read :data (:nodes (:bvh scene))}
                      {:binding 2 :kind :storage-read :data (:tri-index (:bvh scene))}
                      {:binding 3 :kind :storage-read :data (:albedo (:mats scene))}
                      {:binding 4 :kind :storage-read :data (:emission (:mats scene))}
                      {:binding 5 :kind :storage-read-write :size fb-bytes}
                      {:binding 6 :kind :uniform :data params}]
             fb (wgpu/rt-dispatch! wgpu/*wgpu-backend* device wgsl/pathtrace-wgsl buffers width height)]
         {:framebuffer fb :backend :webgpu})))))
