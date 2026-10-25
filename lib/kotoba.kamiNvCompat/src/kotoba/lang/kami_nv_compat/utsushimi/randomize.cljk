(ns kotoba.lang.kami-nv-compat.utsushimi.randomize
  "utsushimi — Replicator create / modify / randomize ops + resolve.
  Portable .cljc port of src/utsushimi/randomize.ts. Wave 31.

  Mirrors omni.replicator.core.{create, modify, randomize} and the
  resolve helper: scene-level domain-randomization ops are captured as
  tagged maps and materialized per-frame against a sampler.

  ADR-2605261800 SD6 / D10.4 utsushimi."
  (:require [kotoba.lang.kami-nv-compat.utsushimi.distribution :as dist]
            [kotoba.lang.kami-nv-compat.utsushimi.sampler :as sampler]))

;; ── semantics + primitives ─────────────────────────────────────────────
;;
;; Semantic = [class-tag value], e.g. ["class" "cube"].
;; PrimSpec {:kind (:camera|:light|:cube|:sphere) :position :rotation :radius
;;           :focal-length :light-type :intensity :semantics :rotation-y}

(defn make-camera
  ([] (make-camera [0.0 5.0 0.0] [0.0 0.0 0.0] 24))
  ([position] (make-camera position [0.0 0.0 0.0] 24))
  ([position rotation] (make-camera position rotation 24))
  ([position rotation focal-length]
   {:kind :camera :position position :rotation rotation :focal-length focal-length}))

(defn make-light
  ([] (make-light [0.0 0.0 0.0] "distant" 1000))
  ([rotation] (make-light rotation "distant" 1000))
  ([rotation light-type] (make-light rotation light-type 1000))
  ([rotation light-type intensity]
   {:kind :light :rotation rotation :light-type light-type :intensity intensity}))

(defn make-cube
  ([] (make-cube [0.0 0.0 0.0] []))
  ([position] (make-cube position []))
  ([position semantics]
   {:kind :cube :position position :semantics semantics}))

(defn make-sphere
  ([] (make-sphere [0.0 0.0 0.0] 1 []))
  ([position] (make-sphere position 1 []))
  ([position radius] (make-sphere position radius []))
  ([position radius semantics]
   {:kind :sphere :position position :radius radius :semantics semantics}))

;; ── modify ops ───────────────────────────────────────────────────────────
;; ModifyOp {:op (:pose|:visibility) ...}

(defn modify-pose
  ([] (modify-pose nil nil))
  ([position] (modify-pose position nil))
  ([position rotation] {:op :pose :position position :rotation rotation}))

(defn modify-visibility
  ([] (modify-visibility true))
  ([visible] {:op :visibility :visible visible}))

;; ── randomize ops ────────────────────────────────────────────────────────
;; RandomizeOp {:kind (:randomize-materials|:randomize-lights|:scatter-2d
;;                     |:scatter-3d|:randomize-physics) ...}

(defn randomize-materials
  [prims materials]
  {:kind :randomize-materials :prims (vec prims) :materials (dist/choice-dist materials)})

(defn randomize-lights
  ([] (randomize-lights nil nil nil))
  ([rotation-dist] (randomize-lights rotation-dist nil nil))
  ([rotation-dist intensity-dist] (randomize-lights rotation-dist intensity-dist nil))
  ([rotation-dist intensity-dist color-dist]
   {:kind :randomize-lights
    :rotation (or rotation-dist (dist/uniform-dist [-90 -180 -180] [90 180 180]))
    :intensity (or intensity-dist (dist/uniform-dist [500] [3000]))
    :color (or color-dist (dist/uniform-dist [0.7 0.7 0.7] [1 1 1]))}))

(defn scatter-2d
  ([prims] (scatter-2d prims :xy [[-2 -2] [2 2]] nil))
  ([prims plane] (scatter-2d prims plane [[-2 -2] [2 2]] nil))
  ([prims plane region] (scatter-2d prims plane region nil))
  ([prims plane region rotation-z-dist]
   {:kind :scatter-2d :prims (vec prims) :plane plane
    :region [(vec (region 0)) (vec (region 1))]
    :rotation-z (or rotation-z-dist (dist/uniform-dist [-180] [180]))}))

(defn scatter-3d
  ([prims] (scatter-3d prims [[-1 -1 0] [1 1 2]] nil))
  ([prims volume] (scatter-3d prims volume nil))
  ([prims volume rotation-dist]
   {:kind :scatter-3d :prims (vec prims)
    :volume [(vec (volume 0)) (vec (volume 1))]
    :rotation (or rotation-dist (dist/uniform-dist [-180 -180 -180] [180 180 180]))}))

(defn physics-properties
  ([prim] (physics-properties prim nil nil))
  ([prim mass-dist] (physics-properties prim mass-dist nil))
  ([prim mass-dist friction-dist]
   {:kind :randomize-physics :prim prim
    :mass (or mass-dist (dist/uniform-dist [0.5] [2]))
    :friction (or friction-dist (dist/uniform-dist [0.3] [0.9]))}))

;; ── resolve (materialize a randomize op for a frame) ─────────────────────
;; ScatterPose {:position :rotation-z? :rotation?}
;; ResolvedOp  {:kind ... per-kind fields}

(defn- num1 [v] (double (if (vector? v) (v 0) v)))
(defn- num-arr [v] (if (vector? v) (mapv double v) [(double v)]))

(defn resolve-op
  "Materialize a randomize op to a concrete scene operation for one frame."
  ([op] (resolve-op op nil))
  ([op samp]
   (let [s (or samp (sampler/global-sampler))]
     (case (:kind op)
       :randomize-materials
       {:kind :randomize-materials :prims (:prims op) :material (dist/sample (:materials op) s)}

       :randomize-lights
       {:kind :randomize-lights
        :rotation (num-arr (dist/sample (:rotation op) s))
        :intensity (num1 (dist/sample (:intensity op) s))
        :color (num-arr (dist/sample (:color op) s))}

       :scatter-2d
       (let [[rx0 ry0] ((:region op) 0)
             [rx1 ry1] ((:region op) 1)
             poses (mapv (fn [_]
                           (let [x (sampler/next-uniform! s rx0 rx1)
                                 y (sampler/next-uniform! s ry0 ry1)
                                 rz (num1 (dist/sample (:rotation-z op) s))]
                             (if (= :xy (:plane op))
                               {:position [x y 0.0] :rotation-z rz}
                               {:position [x 0.0 y] :rotation-z rz})))
                         (:prims op))]
         {:kind :scatter-2d :poses poses})

       :scatter-3d
       (let [v0 ((:volume op) 0)
             v1 ((:volume op) 1)
             poses (mapv (fn [_]
                           {:position [(sampler/next-uniform! s (v0 0) (v1 0))
                                       (sampler/next-uniform! s (v0 1) (v1 1))
                                       (sampler/next-uniform! s (v0 2) (v1 2))]
                            :rotation (num-arr (dist/sample (:rotation op) s))})
                         (:prims op))]
         {:kind :scatter-3d :poses poses})

       :randomize-physics
       {:kind :randomize-physics :prim (:prim op)
        :mass (num1 (dist/sample (:mass op) s))
        :friction (num1 (dist/sample (:friction op) s))}))))
