(ns autodrive.fleet
  "Multi-agent driver: run N autonomous agents in one world, each perceiving
  the others as obstacles.

  Restored from the deleted `kami-autodrive` Rust crate
  (kotoba-lang/kami-engine, PR #82), ADR-2607010930.

  Coordination is priority + index right-of-way, not full negotiation: an
  agent yields to (i.e. senses, and routes/brakes around) every agent with a
  strictly higher `:priority`, and to equal-priority agents with a lower
  index. Higher-priority agents do not see lower ones, so the symmetry that
  deadlocks two reactive agents head-on is broken — someone always has the
  right of way.

  Each agent is sensed by the others as a sphere of its `:radius` at the
  lidar mount height, swept by a 360-degree ring lidar built per tick (see
  `autodrive.sensor-sim/ring-sweep`, this crate's portable raycasting
  reimplementation of the relevant `kami-sensor-sim` surface). Honest limits:
  this is decentralised yielding, not cooperative trajectory planning; a
  cornered bicycle still cannot reverse, and dense gridlock can still stall."
  (:require [autodrive.geom :as g]
            [autodrive.types :as t]
            [autodrive.plant :as plant]
            [autodrive.autopilot :as ap]
            [autodrive.sensor-sim :as sim]))

;; Range (m) within which a closing head-on encounter triggers lane discipline.
(def ^:const NEGOTIATE-RANGE 45.0)

(defn fleet-agent
  "One member of a fleet."
  [plant-instance autopilot goal radius priority]
  {:plant plant-instance
   :autopilot (ap/set-goal autopilot goal)
   :goal goal
   :radius radius
   :priority priority})

(defn agent-pose [agent] (plant/pose (:plant agent)))
(defn agent-arrived? [agent] (= :arrived (:state (:autopilot agent))))

(defn new-fleet
  [agents]
  {:agents (vec agents)
   :static-scene (sim/scene)
   :mount-z 1.0
   :intr (sim/lidar-intrinsics :hfov #?(:clj (* 2.0 Math/PI) :cljs (* 2.0 js/Math.PI))
                                :vfov 0.05 :h-beams 180 :v-beams 1
                                :range-min 0.2 :range-max 80.0)})

(defn with-static-scene [fleet scn] (assoc fleet :static-scene scn))

(defn- ahead-and-closing? [me forward-me p forward-p]
  (let [rel (g/sub2 p (t/pos me))
        dist (g/length2 rel)
        ahead (and (> dist 1e-3) (> (g/dot2 (g/normalize2 rel) forward-me) 0.5))
        closing (< (g/dot2 forward-me forward-p) -0.3)]
    [ahead closing dist]))

(defn step
  "Advance every agent one tick. Each agent senses the static scene plus the
  right-of-way subset of other agents (as spheres), runs its autopilot, and
  steps its plant."
  [fleet dt]
  (let [snap (mapv (fn [a] [(agent-pose a) (:radius a) (:priority a)]) (:agents fleet))
        mount-z (:mount-z fleet)]
    (update fleet :agents
            (fn [agents]
              (mapv
               (fn [i agent]
                 (let [[me my-r my-prio] (nth snap i)]
                   (let [scn (reduce
                              (fn [scn [j [p r prio]]]
                                (if (= j i)
                                  scn
                                  (let [[ahead closing dist] (ahead-and-closing? me (t/forward me) p (t/forward p))]
                                    (if (and ahead closing (< dist NEGOTIATE-RANGE))
                                      ;; Head-on: lane discipline. Route WIDE
                                      ;; right of the other agent, plus a "lane
                                      ;; wall" to OUR left that blocks a left
                                      ;; pass. Symmetric on both agents ⇒ pass
                                      ;; right-to-right.
                                      (let [scn (sim/scene-add scn (sim/sphere (g/v3 (:x p) (:y p) mount-z) (+ r 1.0)))
                                            wall (g/add2 (t/pos p) (g/scale2 (t/left me) (* 2.0 (+ my-r r))))]
                                        (sim/scene-add scn (sim/sphere (g/v3 (:x wall) (:y wall) mount-z) r)))
                                      ;; Crossing / overtaking / following.
                                      (sim/scene-add scn (sim/sphere (g/v3 (:x p) (:y p) mount-z) r))))))
                              (:static-scene fleet)
                              (map-indexed vector snap))
                         pose (agent-pose agent)
                         returns (sim/ring-sweep (:intr fleet) pose mount-z scn)
                         [ap' cmd] (ap/step (:autopilot agent) pose (plant/speed (:plant agent)) returns pose dt)
                         plant' (plant/step (:plant agent) cmd dt)]
                     (assoc agent :autopilot ap' :plant plant'))))
               (range (count agents)) agents)))))

(defn all-arrived? [fleet] (every? agent-arrived? (:agents fleet)))

(defn min-separation
  "Smallest surface-to-surface gap between any two agents (negative =>
  overlap/collision)."
  [fleet]
  (let [agents (:agents fleet) n (count agents)]
    (apply min ##Inf
           (for [i (range n) j (range (inc i) n)]
             (let [a (nth agents i) b (nth agents j)]
               (- (g/distance2 (t/pos (agent-pose a)) (t/pos (agent-pose b)))
                  (:radius a) (:radius b)))))))
