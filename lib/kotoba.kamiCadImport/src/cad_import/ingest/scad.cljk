(ns cad-import.ingest.scad
  "OpenSCAD-style parametric ingest.

   Restored from kami-cad-import (kotoba-lang/kami-engine, deleted PR #82,
   \"Remove Rust workspace\"), per ADR-2607010930. Ported 1:1 from the
   original `src/ingest/scad.rs`.

   Mirrors the minimal `ScadEntity` shape from `kami-scad` (Sphere /
   Cube / Cylinder + position / rotation / scale) without taking a
   direct dependency — `kami-scad` pulls render + voxel + SDF + mesher +
   gltf, which would explode this crate's dependency graph for what is
   essentially three primitive shapes and an AABB calculation.

   Primitives (`ScadPrim`) are tagged maps:
   `{:type :sphere :radius r}`, `{:type :cube :size [sx sy sz]}`, or
   `{:type :cylinder :h h :r1 r1 :r2 r2}` (cylinder along +Y, centred at
   the origin)."
  (:require [cad-import.part :as part]
            [cad-import.xform :as xf]))

;; ── ScadPrim ────────────────────────────────────────────────────────

(defn sphere [radius] {:type :sphere :radius radius})
(defn cube [size] {:type :cube :size size})
(defn cylinder [h r1 r2] {:type :cylinder :h h :r1 r1 :r2 r2})

(defn- local-aabb
  "Tight local-space AABB `[lo hi]` for a `ScadPrim`."
  [{:keys [type radius size h r1 r2]}]
  (case type
    :sphere [[(- radius) (- radius) (- radius)] [radius radius radius]]
    :cube (let [[sx sy sz] size
                hx (* sx 0.5) hy (* sy 0.5) hz (* sz 0.5)]
            [[(- hx) (- hy) (- hz)] [hx hy hz]])
    :cylinder (let [r (max r1 r2)]
                [[(- r) (* h -0.5) (- r)] [r (* h 0.5) r]])))

;; ── ScadTransform ───────────────────────────────────────────────────

(defn default-transform [] {:position [0.0 0.0 0.0] :rotation [0.0 0.0 0.0 1.0] :scale [1.0 1.0 1.0]})
(defn translate [t x y z] (assoc t :position [x y z]))
(defn scale [t sx sy sz] (assoc t :scale [sx sy sz]))
(defn rotate-xyzw [t x y z w] (assoc t :rotation [x y z w]))

(defn- transform->affine [t]
  (xf/trs->affine (:scale t) (:rotation t) (:position t)))

;; ── world AABB ──────────────────────────────────────────────────────

(defn- world-aabb
  "World-space AABB `[lo hi]` after applying `transform` to `prim`'s
   local AABB."
  [prim transform]
  (let [[lo hi] (local-aabb prim)
        affine (transform->affine transform)]
    (xf/world-aabb-of-local-corners affine (xf/aabb-corners lo hi))))

;; ── AnnotatedEntity / ScadAnnotation ────────────────────────────────
;;
;; `AnnotatedEntity` = `{:primitive ScadPrim :transform ScadTransform
;;                        :annotation ScadAnnotation}`
;; `ScadAnnotation` = `{:part-id :display-name :kind :material :mass-kg
;;                       :parent :break-group :supplier :revision
;;                       :source}`

(defn from-annotated
  "Convert an annotated SCAD entity stream into a validated
   `VehicleAssembly`. The assembly-level `assembly-source` is used for
   any part whose `:annotation :source` is `nil`. `hardpoints` is a seq
   of Hardpoint maps (see `cad-import.part`).

   Returns `[:ok assembly]` or `[:error error-map]`."
  [vehicle-id display-name revision assembly-source entities hardpoints]
  (let [asm0 (-> (part/new-assembly vehicle-id assembly-source)
                 (assoc :display-name display-name)
                 (assoc :revision revision))
        asm (reduce
             (fn [asm {:keys [primitive transform annotation]}]
               (let [[aabb-min aabb-max] (world-aabb primitive transform)
                     part-map {:id (:part-id annotation)
                               :display-name (or (:display-name annotation) (:part-id annotation))
                               :kind (:kind annotation)
                               :material (:material annotation)
                               :aabb-min aabb-min
                               :aabb-max aabb-max
                               :mass-kg (:mass-kg annotation)
                               :parent (:parent annotation)
                               :break-group (:break-group annotation)
                               :source (or (:source annotation) assembly-source)
                               :supplier (or (:supplier annotation) part/default-supplier)
                               :revision (or (:revision annotation) (:revision asm0))}]
                 (part/add-part asm part-map)))
             asm0 entities)
        asm (reduce part/add-hardpoint asm hardpoints)
        [status err] (part/validate asm)]
    (if (= status :error) [:error err] [:ok asm])))
