(ns vehicle.implicit
  "Implicit Euler integrator with Conjugate Gradient sparse solver.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930.

   Standard mass-spring implicit Euler:
     (M + dt^2 K) v_new = M v_old + dt F
     x_new = x_old + dt v_new

   This is an *alternate* integrator to XPBD (see `vehicle.vehicle`),
   selectable via `:integrator-mode :implicit`."
  (:require [vehicle.vec3 :as v3]
            [vehicle.node :as node]
            [vehicle.beam :as beam]))

(defn new-cg-state [node-count]
  {:r (vec (repeat node-count v3/zero))
   :p (vec (repeat node-count v3/zero))
   :ap (vec (repeat node-count v3/zero))
   :max-iters 60
   :tolerance 1e-4})

(defn ensure-capacity [state n]
  (if (< (count (:r state)) n)
    (let [grow (fn [v] (into v (repeat (- n (count v)) v3/zero)))]
      (-> state (update :r grow) (update :p grow) (update :ap grow)))
    state))

(defn- id->idx [nodes]
  (let [n-id-max (inc (reduce max 0 (map :id nodes)))]
    (reduce (fn [m [i n]] (assoc m (:id n) i))
            (vec (repeat n-id-max nil))
            (map-indexed vector nodes))))

(defn- apply-system-matrix
  "Apply the matrix (M + dt^2 K) to vector `v` (a vector of vec3s indexed
   by node index). Returns the resulting vector."
  [nodes beams id-to-idx v dt]
  (let [dt2 (* dt dt)
        out (mapv (fn [n vi] (if (node/fixed? n) v3/zero (v3/scale vi (:mass n))))
                   nodes v)]
    (reduce
     (fn [out b]
       (if (:broken b)
         out
         (let [i1 (get id-to-idx (:n1 b))
               i2 (get id-to-idx (:n2 b))]
           (if (or (nil? i1) (nil? i2))
             out
             (let [p1 (:position (nth nodes i1))
                   p2 (:position (nth nodes i2))
                   delta (v3/sub p2 p1)
                   len (v3/length delta)]
               (if (< len 1e-6)
                 out
                 (let [dir (v3/scale delta (/ 1.0 len))
                       ;; No live tire pressure is tracked; default to each
                       ;; beam's own reference-pressure so :pressured beams
                       ;; get their intended no-adjustment (multiplier 1.0)
                       ;; baseline instead of the wrong, hardcoded pressure=0
                       ;; (which previously under-lengthened every tire
                       ;; sidewall beam). No-op for non-:pressured kinds,
                       ;; whose live-rest-length ignores the pressure arg.
                       rest (beam/live-rest-length b (get-in b [:beam-type :reference-pressure] 0.0))
                       bt (:beam-type b)
                       skip? (case (:kind bt)
                               :bounded (let [ratio (/ len (max rest 1e-6))]
                                          (and (>= ratio (:min-ratio bt)) (<= ratio (:max-ratio bt))))
                               :support (>= len rest)
                               false)]
                   (if skip?
                     out
                     (let [k (:spring b)
                           v-diff (v3/sub (nth v i2) (nth v i1))
                           kvd (v3/scale dir (* k (v3/dot dir v-diff)))
                           kvd-dt2 (v3/scale kvd dt2)]
                       (-> out
                           (update i1 v3/sub kvd-dt2)
                           (update i2 v3/add kvd-dt2)))))))))))
     out
     beams)))

(defn- vdot [a b] (reduce + 0.0 (map v3/dot a b)))

(defn cg-solve
  "Solve (M + dt^2 K) v = rhs via Conjugate Gradient. Returns `[v' iters]`."
  [nodes beams id-to-idx rhs v state dt]
  (let [n (count nodes)
        state (ensure-capacity state n)
        ap0 (apply-system-matrix nodes beams id-to-idx v dt)
        r0 (mapv v3/sub rhs ap0)
        p0 r0
        rs-old0 (vdot r0 r0)]
    (if (< rs-old0 (* (:tolerance state) (:tolerance state)))
      [v 0]
      (loop [k 0 v v r r0 p p0 rs-old rs-old0]
        (if (>= k (:max-iters state))
          [v (:max-iters state)]
          (let [ap (apply-system-matrix nodes beams id-to-idx p dt)
                p-ap (vdot p ap)]
            (if (< (Math/abs p-ap) 1e-12)
              [v k]
              (let [alpha (/ rs-old p-ap)
                    v' (mapv (fn [vi pi] (v3/add vi (v3/scale pi alpha))) v p)
                    r' (mapv (fn [ri api] (v3/sub ri (v3/scale api alpha))) r ap)
                    rs-new (vdot r' r')]
                (if (< rs-new (* (:tolerance state) (:tolerance state)))
                  [v' (inc k)]
                  (let [beta (/ rs-new rs-old)
                        p' (mapv (fn [ri pi] (v3/add ri (v3/scale pi beta))) r' p)]
                    (recur (inc k) v' r' p' rs-new)))))))))))

(defn implicit-step
  "Implicit Euler step. `nodes` is a vector of node maps, `external-forces`
   a parallel vector of vec3s. Returns `[nodes' iters]`."
  [nodes beams external-forces dt state]
  (let [n (count nodes)
        state (ensure-capacity state n)
        id-to-idx (id->idx nodes)
        rhs (mapv (fn [nn f] (if (node/fixed? nn) v3/zero
                                  (v3/add (v3/scale (:velocity nn) (:mass nn)) (v3/scale f dt))))
                   nodes external-forces)
        v-init (mapv (fn [nn f] (if (node/fixed? nn) v3/zero
                                     (v3/add (:velocity nn) (v3/scale f (* (:inv-mass nn) dt)))))
                      nodes external-forces)
        [v-new iters] (cg-solve nodes beams id-to-idx rhs v-init state dt)
        nodes' (mapv (fn [nn vi]
                        (if (node/fixed? nn)
                          nn
                          (-> nn (assoc :velocity vi) (update :position v3/add (v3/scale vi dt)))))
                      nodes v-new)]
    [nodes' iters]))
