(ns cad-import.jbeam-emit
  "VehicleAssembly -> JBeam data emitter (Phase 2 topology).

   Restored from kami-cad-import (kotoba-lang/kami-engine, deleted PR #82,
   \"Remove Rust workspace\"), per ADR-2607010930. Ported 1:1 from the
   original `src/jbeam_emit.rs`.

   The original Rust emitter serialised to a JBeam JSON *string* via
   `serde_json`. This port has no JSON dependency (zero-dependency
   requirement, ADR-2607010930) and instead returns the JBeam document
   as a plain Clojure map — the exact shape `vehicle.jbeam/load-edn`
   (kotoba-lang/kami-vehicle, also restored to CLJC under the same ADR)
   expects, so callers that want JSON just run the map through whatever
   JSON library they already depend on, and callers that want to load it
   straight into a `Vehicle` skip serialisation entirely.

   Each `VehiclePart` picks an emit strategy from its `:kind`:

   | strategy       | node count | beam count | applies to |
   |----------------|-----------:|-----------:|---|
   | `:aabb-cube`   | 8  | 12 edges + 4 diagonals = 16 | structural / rigid masses |
   | `:aabb-hull20` | 20 (8 corners + 12 edge mids) | 12 + 4 + 24 + up to 12 = up to 52 | sheet panels (Body, Window, Interior, Trim) |
   | `:wheel-ring`  | 14 (2 axle + 12 ring) | 12 + 24 + 12 = 48 | Wheel |

   `:wheel-ring` also emits a `:wheels` entry so
   `vehicle.jbeam/load-edn` instantiates a real wheel (Pacejka tire +
   pressure-modulated side-walls) instead of a generic mass cluster.

   Hardpoints add one inter-part beam each, anchored to the nearest
   existing node on each side."
  (:require [cad-import.part :as part]
            [cad-import.xform :as xf]))

;; ── strategy selection ───────────────────────────────────────────────

(defn emit-strategy [kind]
  (case kind
    (:body :window :interior :trim) :aabb-hull20
    :wheel :wheel-ring
    :aabb-cube))

(defn node-group [kind]
  (case kind
    :wheel "wheel_hub" ; axle nodes go to hub group; ring nodes to wheel_tire below
    (:chassis :suspension :brake) "body"
    (:powertrain :fluid :electrical) "cargo"
    "body"))

(defn hardpoint-beam-kind [kind]
  (case kind
    :weld "normal"
    (:bolt :hinge :latch) "bounded"
    :press "normal"
    :adhesive "normal"))

(defn hardpoint-break-strain [kind material]
  (let [base (part/break-strain material)]
    (case kind
      :weld base
      :press base
      :bolt (* base 0.7)
      :hinge (* base 0.6)
      :latch (* base 0.4)
      :adhesive (* base 0.5))))

;; ── helper geometry ─────────────────────────────────────────────────

(def cube-edges
  [[0 1] [1 2] [2 3] [3 0]
   [4 5] [5 6] [6 7] [7 4]
   [0 4] [1 5] [2 6] [3 7]])
(def cube-diagonals [[0 6] [1 7] [2 4] [3 5]])

(defn corner-id [part-id idx] (str part-id "_n" idx))
(defn mid-id [part-id edge-idx] (str part-id "_m" edge-idx))
(defn axle-id [part-id side] (str part-id "_axle_" side))
(defn ring-id [part-id idx]
  (str part-id "_r" (if (< idx 10) (str "0" idx) (str idx))))

(defn- centroid [pts]
  (if (empty? pts)
    xf/v3-zero
    (xf/v3-scale (reduce xf/v3-add xf/v3-zero pts) (/ 1.0 (count pts)))))

;; ── strategies ──────────────────────────────────────────────────────

(defn- emit-aabb-cube [p]
  (let [total (part/effective-mass-kg p)
        per (/ total 8.0)
        group (node-group (:kind p))
        corners (part/aabb-corners p)
        nodes (mapv (fn [i c] {:id (corner-id (:id p) i) :pos c :mass per :group group})
                    (range 8) corners)
        spring (part/beam-spring-n-m (:material p))
        damping (* spring 0.05)
        strain (part/break-strain (:material p))
        bg (part/effective-break-group p)
        beams (mapv (fn [[a b]]
                      {:n1 (corner-id (:id p) a) :n2 (corner-id (:id p) b)
                       :spring spring :damping damping :type "normal"
                       :break-strain strain :break-group bg})
                    (concat cube-edges cube-diagonals))]
    [nodes beams]))

(defn- emit-aabb-hull20 [p]
  (let [total (part/effective-mass-kg p)
        per-corner (* total 0.075)
        per-mid (* total 0.0333)
        group (node-group (:kind p))
        corners (part/aabb-corners p)
        corner-nodes (mapv (fn [i c] {:id (corner-id (:id p) i) :pos c :mass per-corner :group group})
                            (range 8) corners)
        mids (mapv (fn [[a b]] (xf/v3-scale (xf/v3-add (nth corners a) (nth corners b)) 0.5)) cube-edges)
        mid-nodes (mapv (fn [i m] {:id (mid-id (:id p) i) :pos m :mass per-mid :group group})
                         (range (count cube-edges)) mids)
        nodes (into corner-nodes mid-nodes)

        spring (part/beam-spring-n-m (:material p))
        damping (* spring 0.05)
        strain (part/break-strain (:material p))
        bg (part/effective-break-group p)

        outer-beams (mapv (fn [[a b]]
                             {:n1 (corner-id (:id p) a) :n2 (corner-id (:id p) b)
                              :spring spring :damping damping :type "normal"
                              :break-strain strain :break-group bg})
                           cube-edges)
        diag-beams (mapv (fn [[a b]]
                            {:n1 (corner-id (:id p) a) :n2 (corner-id (:id p) b)
                             :spring spring :damping damping :type "normal"
                             :break-strain strain :break-group bg})
                          cube-diagonals)
        corner-mid-beams (vec (mapcat (fn [i [a b]]
                                         [{:n1 (mid-id (:id p) i) :n2 (corner-id (:id p) a)
                                           :spring (* spring 0.5) :damping (* damping 0.5) :type "normal"
                                           :break-strain strain :break-group bg}
                                          {:n1 (mid-id (:id p) i) :n2 (corner-id (:id p) b)
                                           :spring (* spring 0.5) :damping (* damping 0.5) :type "normal"
                                           :break-strain strain :break-group bg}])
                                       (range) cube-edges))
        aabb-max-dim (apply max (xf/v3-sub (:aabb-max p) (:aabb-min p)))
        near (* aabb-max-dim 0.55)
        _ (centroid corners) ; parity with the original's unused `cen` binding
        inter-mid-beams (vec
                          (for [i (range (count mids))
                                j (range (inc i) (count mids))
                                :let [d (xf/v3-length (xf/v3-sub (nth mids i) (nth mids j)))]
                                :when (< d near)]
                            {:n1 (mid-id (:id p) i) :n2 (mid-id (:id p) j)
                             :spring (* spring 0.4) :damping (* damping 0.4) :type "normal"
                             :break-strain strain :break-group bg}))
        beams (-> outer-beams (into diag-beams) (into corner-mid-beams) (into inter-mid-beams))]
    [nodes beams]))

(defn- wheel-axes
  "For a wheel part, infer [axle-dir r1 r2 radius width]. The axle is
   the *shortest* AABB axis; the two longer axes span the rolling
   plane."
  [p]
  (let [[ex ey ez] (xf/v3-sub (:aabb-max p) (:aabb-min p))
        axes (sort-by first [[(Math/abs ex) [1.0 0.0 0.0]]
                              [(Math/abs ey) [0.0 1.0 0.0]]
                              [(Math/abs ez) [0.0 0.0 1.0]]])
        axle-dir (second (nth axes 0))
        r1 (second (nth axes 1))
        r2 (second (nth axes 2))
        width (first (nth axes 0))
        radius (* 0.5 (+ (first (nth axes 1)) (first (nth axes 2))) 0.5)]
    [axle-dir r1 r2 radius width]))

(def ring-nodes 12)

(defn- emit-wheel-ring [p]
  (let [[axle-dir r-a r-b radius width] (wheel-axes p)
        centre (xf/v3-scale (xf/v3-add (:aabb-min p) (:aabb-max p)) 0.5)
        total (part/effective-mass-kg p)
        per-axle (* total 0.125)
        per-ring (/ (* total 0.75) ring-nodes)

        axle-l (xf/v3-sub centre (xf/v3-scale axle-dir (* width 0.5)))
        axle-r (xf/v3-add centre (xf/v3-scale axle-dir (* width 0.5)))
        id-l (axle-id (:id p) "l")
        id-r (axle-id (:id p) "r")
        axle-nodes [{:id id-l :pos axle-l :mass per-axle :group "wheel_hub"}
                    {:id id-r :pos axle-r :mass per-axle :group "wheel_hub"}]

        ring-ids (mapv #(ring-id (:id p) %) (range ring-nodes))
        ring-node-list (mapv (fn [i id]
                                (let [theta (* (/ i (double ring-nodes)) (* 2 Math/PI))
                                      pos (-> centre
                                              (xf/v3-add (xf/v3-scale r-a (* radius (Math/cos theta))))
                                              (xf/v3-add (xf/v3-scale r-b (* radius (Math/sin theta)))))]
                                  {:id id :pos pos :mass per-ring :group "wheel_tire"}))
                              (range ring-nodes) ring-ids)
        nodes (into axle-nodes ring-node-list)

        spring (part/beam-spring-n-m (:material p))
        damping (* spring 0.05)
        strain (part/break-strain (:material p))
        bg (part/effective-break-group p)

        tread-beams (mapv (fn [i]
                             (let [j (mod (inc i) ring-nodes)]
                               {:n1 (nth ring-ids i) :n2 (nth ring-ids j)
                                :spring spring :damping damping :type "normal"
                                :break-strain strain :break-group bg}))
                           (range ring-nodes))
        sidewall-beams (vec (mapcat (fn [i]
                                       [{:n1 (nth ring-ids i) :n2 id-l
                                         :spring (* spring 0.5) :damping (* damping 0.5) :type "pressured"
                                         :break-strain (* strain 1.5) :break-group bg}
                                        {:n1 (nth ring-ids i) :n2 id-r
                                         :spring (* spring 0.5) :damping (* damping 0.5) :type "pressured"
                                         :break-strain (* strain 1.5) :break-group bg}])
                                     (range ring-nodes)))
        half (quot ring-nodes 2)
        spoke-beams (mapv (fn [i]
                             {:n1 (nth ring-ids i) :n2 (nth ring-ids (mod (+ i half) ring-nodes))
                              :spring (* spring 0.3) :damping (* damping 0.3) :type "support"
                              :break-strain strain :break-group bg})
                           (range half))
        beams (-> tread-beams (into sidewall-beams) (into spoke-beams))
        wheel {:axle [id-l id-r] :radius radius :width width :tire "road_dry" :tire-nodes ring-ids}]
    [nodes beams wheel]))

;; ── inter-part hardpoints ───────────────────────────────────────────

(defn- part-anchor-candidates
  "All emitted node positions for a part (corner / mid / ring / axle) —
   used to find the nearest anchor for a hardpoint."
  [p]
  (let [corners (part/aabb-corners p)]
    (case (emit-strategy (:kind p))
      :aabb-cube
      (mapv (fn [i c] [(corner-id (:id p) i) c]) (range 8) corners)

      :aabb-hull20
      (into (mapv (fn [i c] [(corner-id (:id p) i) c]) (range 8) corners)
            (map-indexed (fn [i [a b]] [(mid-id (:id p) i) (xf/v3-scale (xf/v3-add (nth corners a) (nth corners b)) 0.5)])
                         cube-edges))

      :wheel-ring
      (let [[axle-dir r-a r-b radius width] (wheel-axes p)
            centre (xf/v3-scale (xf/v3-add (:aabb-min p) (:aabb-max p)) 0.5)]
        (into [[(axle-id (:id p) "l") (xf/v3-sub centre (xf/v3-scale axle-dir (* width 0.5)))]
               [(axle-id (:id p) "r") (xf/v3-add centre (xf/v3-scale axle-dir (* width 0.5)))]]
              (for [i (range ring-nodes)]
                (let [theta (* (/ i (double ring-nodes)) (* 2 Math/PI))
                      pos (-> centre
                              (xf/v3-add (xf/v3-scale r-a (* radius (Math/cos theta))))
                              (xf/v3-add (xf/v3-scale r-b (* radius (Math/sin theta)))))]
                  [(ring-id (:id p) i) pos])))))))

(defn- nearest-anchor [p world]
  (let [candidates (part-anchor-candidates p)]
    (first (reduce (fn [[best-id best-d] [id pos]]
                      (let [d (xf/v3-length (xf/v3-sub pos world))]
                        (if (< d best-d) [id d] [best-id best-d])))
                    [(first (first candidates)) ##Inf]
                    candidates))))

(defn- emit-hardpoint [hp asm]
  (let [from (part/part-by-id asm (:from-part hp))
        to (part/part-by-id asm (:to-part hp))]
    (if (or (nil? from) (nil? to))
      [:error {:error :unknown-hardpoint-part
                :part (if (nil? from) (:from-part hp) (:to-part hp))}]
      (let [n1 (nearest-anchor from (:position hp))
            n2 (nearest-anchor to (:position hp))
            mat (if (< (part/beam-spring-n-m (:material from)) (part/beam-spring-n-m (:material to)))
                  (:material from) (:material to))
            bg (min (part/effective-break-group from) (part/effective-break-group to))]
        [:ok {:n1 n1 :n2 n2
              :spring (part/beam-spring-n-m mat)
              :damping (* (part/beam-spring-n-m mat) 0.05)
              :type (hardpoint-beam-kind (:kind hp))
              :break-strain (hardpoint-break-strain (:kind hp) mat)
              :break-group bg}]))))

;; ── public API ──────────────────────────────────────────────────────

(defn emit
  "Emit a JBeam-format document (a Clojure map) for the assembly.
   Returns `[:ok jbeam-map]` or `[:error error-map]` (mirrors Rust's
   `Result<String, AssemblyError>`, minus the JSON serialisation step —
   see the namespace docstring)."
  [asm]
  (let [[status err] (part/validate asm)]
    (if (= status :error)
      [:error err]
      (let [strategy-results (mapv (fn [p]
                                      (case (emit-strategy (:kind p))
                                        :aabb-cube (emit-aabb-cube p)
                                        :aabb-hull20 (emit-aabb-hull20 p)
                                        :wheel-ring (emit-wheel-ring p)))
                                    (:parts asm))
            nodes (vec (mapcat first strategy-results))
            beams-from-parts (vec (mapcat second strategy-results))
            wheels (vec (keep #(nth % 2 nil) strategy-results))
            hp-results (mapv #(emit-hardpoint % asm) (:hardpoints asm))
            hp-error (first (filter #(= (first %) :error) hp-results))]
        (if hp-error
          [:error (second hp-error)]
          (let [hp-beams (mapv second hp-results)
                beams (into beams-from-parts hp-beams)]
            [:ok {:name (:vehicle-id asm) :nodes nodes :beams beams :wheels wheels}]))))))
