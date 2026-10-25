(ns kotoba.lang.kami-nv-compat.utsushimi.index
  "utsushimi — clean-room synthetic-data-generation engine (utsushimi 写し身).
  Portable .cljc port of src/utsushimi/index.ts. Wave 32 (closes utsushimi).

  The canonical KAMI implementation behind nv-compat/omni-replicator-core.
  Bit-reproducible DR sampler + distributions + create/modify/randomize
  ops + COCO/Kitti writers + a render bridge that grounds annotations in
  real kami-rt camera projection and (optionally) kami-rt RGB frames.

  Most of index.ts is TS re-export bookkeeping with no CLJC equivalent —
  callers require utsushimi.sampler / .distribution / .randomize /
  .writers / .render-bridge directly. This namespace ports the real
  orchestration logic: generate-dataset.

  Note on prim identity: the TS source tracks each randomizer op's
  referenced prims across per-frame clones via JS object-reference
  identity (`working.indexOf(target)`). Clojure prim specs are plain
  immutable maps, so cloning is unnecessary (sharing a map reference is
  always safe) and 'identity' naturally becomes structural equality —
  vec-index-of below. This is observably identical to the TS behavior
  for the intended usage (distinct prim literals); it would only diverge
  from JS reference semantics in the pathological case of two
  accidentally-structurally-identical-but-distinct prims in the same
  scene, which the upstream API was never designed to distinguish
  reliably either.

  ADR-2605261800 SD6 / D10.4 utsushimi."
  (:require [kotoba.lang.kami-nv-compat.utsushimi.sampler :as sampler]
            [kotoba.lang.kami-nv-compat.utsushimi.randomize :as r]
            [kotoba.lang.kami-nv-compat.utsushimi.writers :as writers]
            [kotoba.lang.kami-nv-compat.utsushimi.render-bridge :as rb]))

;; CameraSpec {:eye :target :up? :vfov-deg?}
;; GenerateOptions {:prims :randomizers :camera :num-frames :image-width?
;;                   :image-height? :seed? :writers :render?}
;; GenerateResult {:frames :outputs :rgb?}

(defn- vec-index-of
  [coll x]
  (first (keep-indexed (fn [i v] (when (= v x) i)) coll)))

(defn- remap-prim
  [p base working]
  (let [i (vec-index-of base p)]
    (if i (working i) p)))

(defn- remap-op
  "Rebind an op's prim references from the base list to the per-frame
  working clones (matched by structural position in the base list)."
  [op base working]
  (case (:kind op)
    (:randomize-materials :scatter-2d :scatter-3d)
    (update op :prims (fn [prims] (mapv #(remap-prim % base working) prims)))

    :randomize-physics
    (update op :prim #(remap-prim % base working))

    op))

(defn- apply-resolved
  "Apply one op's resolved (materialized-for-this-frame) result to the
  working prim list. randomize-lights / randomize-physics resolve for
  reproducibility but do not alter 2D annotation geometry."
  [op res working]
  (case (:kind res)
    (:scatter-2d :scatter-3d)
    (let [op-prims (:prims op)]
      (reduce (fn [w [i pose]]
                (let [target (op-prims i)
                      idx (vec-index-of w target)
                      placed (assoc target
                                    :position (:position pose)
                                    :rotation-y (or (:rotation-z pose)
                                                    (when (:rotation pose) ((:rotation pose) 1))
                                                    0))]
                  (if idx (assoc w idx placed) (conj w placed))))
              working
              (map-indexed vector (:poses res))))

    :randomize-materials
    (if (= :randomize-materials (:kind op))
      (reduce (fn [w prim]
                (let [idx (vec-index-of w prim)
                      tinted (if idx (w idx) prim)
                      tinted2 (update tinted :semantics
                                      (fn [sems] (conj (vec sems) ["color" (str (:material res))])))]
                  (if idx (assoc w idx tinted2) w)))
              working
              (:prims op))
      working)

    working))

(defn generate-dataset
  "Run a full synthetic-data generation pass: for each frame, advance the
  DR sampler, randomize the scene, project ground-truth 2D boxes, and
  write to every writer. Deterministic given :seed."
  [opts]
  (let [img-w (or (:image-width opts) 640)
        img-h (or (:image-height opts) 480)
        up (or (:up (:camera opts)) [0.0 1.0 0.0])
        vfov (or (:vfov-deg (:camera opts)) 45)
        cam (rb/make-proj-camera (:eye (:camera opts)) (:target (:camera opts))
                                  up vfov (/ (double img-w) img-h))
        samp (sampler/make-sampler (or (:seed opts) 0))
        base (vec (:prims opts))]
    (loop [f 0 frames [] rgb []]
      (if (>= f (:num-frames opts))
        (cond-> {:frames frames :outputs (mapv writers/finalize-writer (:writers opts))}
          (:render opts) (assoc :rgb rgb))
        (let [working (reduce (fn [wk op]
                                 (let [res (r/resolve-op op samp)]
                                   (apply-resolved (remap-op op base wk) res wk)))
                               base
                               (:randomizers opts))
              annotated (rb/annotate-frame cam working img-w img-h)
              sample {:frame f :primitives annotated}]
          (doseq [wr (:writers opts)] (writers/write-frame! wr f sample))
          (recur (inc f)
                 (conj frames annotated)
                 (if (:render opts)
                   (conj rgb (rb/render-frame-cpu (:eye (:camera opts)) (:target (:camera opts))
                                                   up vfov working img-w img-h))
                   rgb)))))))
