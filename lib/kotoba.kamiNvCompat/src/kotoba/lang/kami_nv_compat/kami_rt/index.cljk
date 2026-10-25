(ns kotoba.lang.kami-nv-compat.kami-rt.index
  "kami-rt barrel — Scene/TraceResult convenience wrappers, portable .cljc
  port of src/kami-rt/index.ts. Wave 26 (closes the kami-rt subdir).

  Most of index.ts is TS re-export bookkeeping with no CLJC equivalent —
  callers `require` kami-rt.bvh / kami-rt.pathtrace / kami-rt.wgpu-raytrace /
  kami-rt.wgpu-pathtrace / kami-rt.wgsl-shaders directly instead of going
  through a barrel. This namespace ports only the real logic: Scene
  construction and the trace-image / trace-image-cpu / path-trace /
  path-trace-cpu convenience wrappers."
  (:require [kotoba.lang.kami-nv-compat.kami-rt.bvh :as bvh]
            [kotoba.lang.kami-nv-compat.kami-rt.pathtrace :as pt]
            [kotoba.lang.kami-nv-compat.kami-rt.wgpu-raytrace :as wrt]
            [kotoba.lang.kami-nv-compat.kami-rt.wgpu-pathtrace :as wpt]))

(defn build-scene
  "Build a Scene ({:soup :bvh}) from [[v0 v1 v2] ...] triangles."
  [triangles]
  (let [soup (bvh/triangle-soup triangles)]
    {:soup soup :bvh (bvh/build-bvh soup)}))

(defn trace-image
  "Render `scene` from `cam` into a width×height RGBA-float framebuffer. Uses
  WebGPU when a device is available (or one is passed via opts' :device),
  otherwise the CPU tracer. Returns {:framebuffer :backend :width :height}."
  ([scene cam width height] (trace-image scene cam width height {}))
  ([scene cam width height opts]
   (let [shade (or (:shade opts) bvh/default-shade)
         result (wrt/trace-image-gpu (:soup scene) (:bvh scene) cam width height shade (:device opts))]
     (assoc result :width width :height height))))

(defn trace-image-cpu
  "Synchronous CPU render — convenience wrapper over bvh/trace-image-sync."
  ([scene cam width height] (trace-image-cpu scene cam width height bvh/default-shade))
  ([scene cam width height shade]
   {:framebuffer (bvh/trace-image-sync (:soup scene) (:bvh scene) cam width height shade)
    :backend :cpu :width width :height height}))

(defn path-trace
  "Progressive path-trace `scene` from `cam`. WebGPU when available (or a
  device is passed via opts' :device), else CPU. Returns
  {:framebuffer :backend :width :height}."
  ([scene cam width height] (path-trace scene cam width height {}))
  ([scene cam width height opts]
   (let [settings (or (:settings opts) pt/default-path-settings)
         result (wpt/path-trace-gpu scene cam width height settings (:device opts))]
     (assoc result :width width :height height))))

(defn path-trace-cpu
  "Synchronous CPU path trace."
  ([scene cam width height] (path-trace-cpu scene cam width height pt/default-path-settings))
  ([scene cam width height settings]
   {:framebuffer (pt/path-trace-sync scene cam width height settings)
    :backend :cpu :width width :height height}))
