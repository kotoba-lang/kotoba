(ns vehicle.builder
  "Programmatic builder for assembling a vehicle.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930.

   The builder hands out sequential node/beam/triangle/wheel ids so callers
   don't have to track them. Unlike the Rust `VehicleBuilder` (a mutable
   struct wrapping `&mut Vehicle`), this port is a plain immutable map
   `{:vehicle ... :next-node ... :next-beam ... :next-tri ... :next-wheel ...}`
   threaded through each function, which returns `[builder id]` for the
   id-producing operations."
  (:require [vehicle.vec3 :as v3]
            [vehicle.node :as node]
            [vehicle.beam :as beam]
            [vehicle.triangle :as triangle]
            [vehicle.wheel :as wheel]
            [vehicle.vehicle :as veh]))

(defn new-builder [name]
  {:vehicle (veh/new-vehicle name)
   :next-node 0
   :next-beam 0
   :next-tri 0
   :next-wheel 0})

(defn node!
  "Returns `[builder' node-id]`."
  [b position mass group]
  (let [id (:next-node b)
        n (node/with-group (node/new-node id position mass) group)]
    [(-> b (update :next-node inc) (update :vehicle veh/add-node n)) id]))

(defn anchor!
  [b position]
  (let [id (:next-node b)
        n (node/anchor id position)]
    [(-> b (update :next-node inc) (update :vehicle veh/add-node n)) id]))

(defn- find-node-pos [vehicle id]
  (:position (first (filter #(= (:id %) id) (:nodes vehicle)))))

(defn beam!
  "Returns `[builder' beam-id]`."
  [b n1 n2 spring damping]
  (let [p1 (find-node-pos (:vehicle b) n1)
        p2 (find-node-pos (:vehicle b) n2)
        rest (max (v3/length (v3/sub p2 p1)) 1e-3)
        id (:next-beam b)
        bm (beam/new-beam id n1 n2 rest spring damping)]
    [(-> b (update :next-beam inc) (update :vehicle veh/add-beam bm)) id]))

(defn beam-typed!
  "Returns `[builder' beam-id]`."
  [b n1 n2 spring damping ty deform break-group]
  (let [[b id] (beam! b n1 n2 spring damping)
        b (update-in b [:vehicle :beams (dec (count (:beams (:vehicle b))))]
                      (fn [bm] (assoc bm :beam-type ty :deform deform :break-group break-group)))]
    [b id]))

(defn triangle!
  [b n1 n2 n3 group]
  (let [id (:next-tri b)
        t (triangle/with-group (triangle/new-triangle id n1 n2 n3) group)]
    [(-> b (update :next-tri inc) (update :vehicle veh/add-triangle t)) id]))

(defn wheel!
  [b axle-n1 axle-n2 radius width tire]
  (let [id (:next-wheel b)
        w (-> (wheel/new-wheel id axle-n1 axle-n2 radius width)
              (assoc :tire tire)
              (update :hub-nodes conj axle-n1)
              (update :hub-nodes conj axle-n2))]
    [(-> b (update :next-wheel inc) (update :vehicle veh/add-wheel w)) id]))

(defn- find-wheel-idx [vehicle wheel-id]
  (first (keep-indexed (fn [i w] (when (= (:id w) wheel-id) i)) (:wheels vehicle))))

(defn add-tire-ring!
  "Generate `count` tire-ring nodes evenly around `centre` in the plane
   perpendicular to `axle-axis`, tied to the hub by side-wall pressured
   beams. Returns `[builder' ring-node-ids]`."
  [b wheel-id centre axle-axis radius cnt node-mass sidewall-spring sidewall-damping reference-pressure]
  (let [axis (v3/normalize-or-zero axle-axis)
        helper (if (< (Math/abs (:y axis)) 0.9) v3/unit-y v3/unit-x)
        u (v3/normalize-or-zero (v3/cross helper axis))
        v (v3/normalize-or-zero (v3/cross axis u))
        w-idx (find-wheel-idx (:vehicle b) wheel-id)
        w (nth (:wheels (:vehicle b)) w-idx)
        axle-n1 (:axle-n1 w)
        axle-n2 (:axle-n2 w)
        tau (* 2.0 Math/PI)
        sidewall-deform {:deform-limit 0.30 :break-limit 0.85 :max-plastic-strain 0.50}
        [b ids]
        (reduce
         (fn [[b ids] i]
           (let [angle (* (/ (double i) (double cnt)) tau)
                 p (v3/add centre (v3/scale (v3/add (v3/scale u (Math/cos angle))
                                                       (v3/scale v (Math/sin angle)))
                                              radius))
                 [b id] (node! b p node-mass :wheel-tire)
                 [b _] (beam-typed! b id axle-n1 sidewall-spring sidewall-damping
                                     (beam/beam-type-pressured 0.05 reference-pressure)
                                     sidewall-deform nil)
                 [b _] (beam-typed! b id axle-n2 sidewall-spring sidewall-damping
                                     (beam/beam-type-pressured 0.05 reference-pressure)
                                     sidewall-deform nil)]
             [b (conj ids id)]))
         [b []]
         (range cnt))
        tread-deform {:deform-limit 0.35 :break-limit 0.85 :max-plastic-strain 0.50}
        b (reduce
           (fn [b i]
             (let [a (nth ids i)
                   bb (nth ids (mod (inc i) (count ids)))
                   [b _] (beam-typed! b a bb (* sidewall-spring 1.2) (* sidewall-damping 0.8)
                                        beam/beam-type-normal tread-deform nil)]
               b))
           b
           (range cnt))
        w-idx2 (find-wheel-idx (:vehicle b) wheel-id)
        b (update-in b [:vehicle :wheels w-idx2 :tire-nodes] into ids)]
    [b ids]))

(defn build [b] (:vehicle b))
