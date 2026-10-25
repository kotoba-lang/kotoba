(ns kotoba.webgpu-rs.frame
  "Pure per-draw-call math extracted from kami-webgpu-rs's `Renderer::draw`
  and `model_mat`: instance model matrices, the main/shadow view-projection
  matrices, and the flat float buffers `draw` uploaded to the GPU uniform
  (`gf`, matches the `G` WGSL struct in `lit_shader.wgsl`/
  `shadow_shader.wgsl` exactly) and instance-vertex (`idata`) buffers.
  None of this touches a `wgpu::*` type — it's the CPU-side computation of
  *what bytes to upload*, not the upload itself, so it's ported in full;
  only `wgpu::Queue::write_buffer` (the actual GPU call) stays a
  host-adapter concern. See [[kotoba.webgpu-rs.config]] for the numeric
  buffer-layout/tuning constants this packs in.

  No network, no I/O."
  (:require [kotoba.webgpu-rs.config :as cfg]
            [kotoba.webgpu-rs.mat4 :as m]))

;; --- instance model matrix (kami-webgpu-rs's `model_mat`) -----------------

(defn model-mat
  "World matrix for an instance: translate to `:pos` (lifted by half its
  `:size` height so the cuboid sits on the ground), rotate about Y by
  `:yaw`, scale by `[w h w]`."
  [{[px py pz] :pos [w h] :size yaw :yaw}]
  (m/mul* (m/from-translation [px (+ py (* h 0.5)) pz])
          (m/from-rotation-y yaw)
          (m/from-scale [w h w])))

;; --- camera derivation (centroid-relative default eye/target) -------------

(defn- normalize-or-zero [v]
  (let [len2 (reduce + (map #(* % %) v))]
    (if (< len2 1e-20) [0.0 0.0 0.0] (mapv #(/ % (Math/sqrt len2)) v))))

(defn instance-centroid-xz
  "Mean `[x z]` over `instances`' `:pos` (matches Rust's `insts.len().max(1)`
  guard against div-by-zero on an empty scene)."
  [instances]
  (let [n (max 1 (count instances))
        [sx sz] (reduce (fn [[ax az] {[x _ z] :pos}] [(+ ax x) (+ az z)])
                         [0.0 0.0] instances)]
    [(/ sx n) (/ sz n)]))

(defn resolve-eye-target
  "`{:eye :target}` — `globals`' own `:eye`/`:target` if set, else derived
  from the instance centroid (an overview looking down at the scene from
  `[cx+60 80 cz+60]` toward `[cx 0 cz]`)."
  [globals instances]
  (let [[cx cz] (instance-centroid-xz instances)]
    {:eye (or (:eye globals) [(+ cx 60.0) 80.0 (+ cz 60.0)])
     :target (or (:target globals) [cx 0.0 cz])}))

(def ^:private deg60->rad (/ (* 60.0 Math/PI) 180.0))

(defn view-proj
  "The main camera's view-projection matrix: 60-degree vertical FOV
  perspective * look-at."
  [eye target aspect]
  (m/mul (m/perspective-rh deg60->rad aspect 0.5 4000.0)
         (m/look-at-rh eye target [0.0 1.0 0.0])))

(defn light-view-proj
  "The sun shadow-map's view-projection matrix: an orthographic frustum
  centred on the instance centroid, looking along `:sun-dir`."
  [globals instances]
  (let [[cx cz] (instance-centroid-xz instances)
        sd (normalize-or-zero (:sun-dir globals))
        ltgt [cx 0.0 cz]
        leye (mapv (fn [t s] (- t (* s 200.0))) ltgt sd)]
    (m/mul (m/orthographic-rh -130.0 130.0 -130.0 130.0 1.0 420.0)
           (m/look-at-rh leye ltgt [0.0 1.0 0.0]))))

;; --- uniform buffer packing (the `G` WGSL struct, 60 floats / 240 bytes) --

(defn pack-globals
  "The flat 60-float uniform buffer `draw` writes to `gbuf` each frame:
  `vp`(16) + `[sun-dir,eye.x]`(4) + `[sun,eye.y]`(4) + `[horizon,eye.z]`(4)
  + `light-vp`(16) + `light-a/b/c/d`(4x4, tuning constants — see
  [[kotoba.webgpu-rs.config]]). Layout matches `lit_shader.wgsl`'s/
  `shadow_shader.wgsl`'s `struct G` field order exactly."
  [globals instances w h]
  (let [{:keys [eye target]} (resolve-eye-target globals instances)
        aspect (/ (double w) (double (max 1 h)))
        vp (view-proj eye target aspect)
        lvp (light-view-proj globals instances)
        [ex ey ez] eye
        [sdx sdy sdz] (:sun-dir globals)
        [sx sy sz] (:sun globals)
        [hx hy hz] (:horizon globals)]
    (vec (concat vp
                 [sdx sdy sdz ex]
                 [sx sy sz ey]
                 [hx hy hz ez]
                 lvp
                 cfg/light-a cfg/light-b cfg/light-c cfg/light-d))))

;; --- per-instance vertex buffer packing (96 bytes / 24 floats each) -------

(defn pack-instance
  "One instance's 24-float vertex-buffer record: `model-mat`(16) +
  `[color,1.0]`(4) + `[metallic,roughness,emissive,0.0]`(4). Layout
  matches [[kotoba.webgpu-rs.config/instance-attributes]]."
  [{[cr cg cb] :color :keys [metallic roughness emissive] :as inst}]
  (vec (concat (model-mat inst) [cr cg cb 1.0] [metallic roughness emissive 0.0])))

(defn pack-instances
  "All instances' vertex-buffer floats, concatenated in draw order,
  capped at [[kotoba.webgpu-rs.config/max-instances]] (matches
  kami-webgpu-rs's `MAX_INST` cap on `n_inst`)."
  [instances]
  (vec (mapcat pack-instance (take cfg/max-instances instances))))
