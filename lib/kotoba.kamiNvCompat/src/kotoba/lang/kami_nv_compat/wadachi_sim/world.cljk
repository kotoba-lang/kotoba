(ns kotoba.lang.kami-nv-compat.wadachi-sim.world
  "wadachi-sim — clean-room AV simulation world (DriveSim lineage). Portable
  .cljc port of src/wadachi-sim/world.ts. Wave 29.

  The canonical KAMI engine behind the nv-compat/drive-sim facade. NVIDIA
  DRIVE Sim is the Omniverse-based sensor-realistic AV simulator;
  wadachi-sim reproduces its core loop — a scenario world (ego + traffic
  actors + static obstacles + ground) advanced over time, with camera /
  LiDAR / radar sensor models grounded in the kami-rt ray tracer.

  This namespace owns the world representation and per-tick scene
  construction: every actor / obstacle becomes an oriented box tessellated
  into triangles so the LiDAR and camera sensors can ray-trace it via the
  shared kami-rt BVH.

  World frame: +x forward, +y left, +z up; ego yaw about +z; ground at z=0.

  Clean-room: from-spec simulator. No DRIVE Sim source/binaries. Civilian,
  SAE-L4 ceiling, simulation-only (no actuation). ADR-2605261800 D1
  (DriveSim -> wadachi-sim); AV scope per ADR-2605242000 / ADR-2606010600."
  (:require [kotoba.lang.kami-nv-compat.kami-rt.index :as kami-rt]))

;; ── world entities ───────────────────────────────────────────────────────
;;
;; EgoState    {:x :y :yaw :speed :extent}
;; Actor       {:id :kind :x :y :yaw :vx :vy :extent}
;; StaticObstacle {:id :kind :x :y :yaw :extent}
;; Scenario    {:ego :actors :obstacles :ground-half-size}
;; kind is a plain string ("car" "pedestrian" "cyclist" ...), matching the
;; kami-drive AgentKind convention.

;; ── oriented-box tessellation ────────────────────────────────────────────

(defn box-tris
  "12 triangles of a box centered at (cx,cy,base+hz) with half-extents
  `half`, rotated `yaw` about +z. The box sits on the ground (base at z=0)."
  [cx cy half yaw]
  (let [hx (half 0)
        hy (half 1)
        hz (half 2)
        c (Math/cos yaw)
        s (Math/sin yaw)
        local [[(- hx) (- hy) 0.0] [hx (- hy) 0.0] [hx hy 0.0] [(- hx) hy 0.0]
               [(- hx) (- hy) (* 2.0 hz)] [hx (- hy) (* 2.0 hz)]
               [hx hy (* 2.0 hz)] [(- hx) hy (* 2.0 hz)]]
        v (mapv (fn [[lx ly lz]]
                  [(- (+ cx (* lx c)) (* ly s))
                   (+ cy (* lx s) (* ly c))
                   lz])
                local)
        q (fn [a b cc d] [[(v a) (v b) (v cc)] [(v a) (v cc) (v d)]])]
    (vec (concat (q 0 1 2 3)                       ; bottom
                 (q 4 5 6 7)                        ; top
                 (q 0 1 5 4) (q 1 2 6 5) (q 2 3 7 6) (q 3 0 4 7)))))  ; sides

(defn- ground-tris
  [half]
  (let [v [[(- half) (- half) 0.0] [half (- half) 0.0] [half half 0.0] [(- half) half 0.0]]]
    [[(v 0) (v 1) (v 2)] [(v 0) (v 2) (v 3)]]))

(defn build-sensor-scene
  "Build the kami-rt scene for the current world (ground + actors +
  obstacles). The ego itself is not included (sensors are mounted on it)."
  [scenario]
  (let [tris (concat (ground-tris (:ground-half-size scenario))
                      (mapcat #(box-tris (:x %) (:y %) (:extent %) (:yaw %)) (:actors scenario))
                      (mapcat #(box-tris (:x %) (:y %) (:extent %) (:yaw %)) (:obstacles scenario)))]
    (kami-rt/build-scene (vec tris))))

;; ── ground-truth object list ─────────────────────────────────────────────
;;
;; GtObject {:id :kind :center :extent :yaw}

(defn world-aabb
  "Axis-aligned world bounds of an oriented box (for projection / collision)."
  [cx cy half yaw]
  (let [hx (half 0)
        hy (half 1)
        hz (half 2)
        c (Math/abs (Math/cos yaw))
        s (Math/abs (Math/sin yaw))
        ex (+ (* hx c) (* hy s))
        ey (+ (* hx s) (* hy c))]
    {:min [(- cx ex) (- cy ey) 0.0]
     :max [(+ cx ex) (+ cy ey) (* 2.0 hz)]}))

(defn- gt-entry
  [o]
  {:id (:id o) :kind (:kind o) :center [(:x o) (:y o) ((:extent o) 2)]
   :extent (:extent o) :yaw (:yaw o)})

(defn ground-truth
  "All annotatable objects (actors + obstacles) with world geometry."
  [scenario]
  (vec (concat (map gt-entry (:actors scenario))
               (map gt-entry (:obstacles scenario)))))
