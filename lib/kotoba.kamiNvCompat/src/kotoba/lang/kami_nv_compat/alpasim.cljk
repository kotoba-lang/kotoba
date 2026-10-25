(ns kotoba.lang.kami-nv-compat.alpasim
  "Drop-in NVIDIA AlpaSim API-compat facade — portable .cljc port of
  src/alpasim.ts. An open-loop-free closed-loop validation harness for
  reasoning AV models: step a model through a scenario, scoring its
  decisions against consequences (AlpaGym closed-loop reward shape), backed
  by the clean-room kami-drive BEV simulator + the nv-compat/alpamayo
  planner.

  The world coordinate frame is global; at each tick the ego's neighbourhood
  is transformed into the ego frame, the model predicts a trajectory, the
  first dynamic action is applied to the ego via the unicycle model,
  scripted agents advance, and collision / progress / comfort are
  accumulated into an AlpaGym-style reward.

  run-closed-loop threads loop state through a plain reduce over tick
  indices instead of TS's imperative mutable loop — same per-tick ordering
  (perceive with PRE-advance agent/ego state, predict, integrate ego,
  advance agents, THEN score clearance/collision against the POST-advance
  positions), just expressed as an accumulator map instead of `let`-
  reassignment + in-place array mutation. Preserved exactly because getting
  this ordering wrong (e.g. scoring against pre-advance agents) would
  silently change collision/reward semantics.

  Dropped one TS no-op: `Number.isFinite(minClearance) ? minClearance :
  Infinity` — minClearance can only ever be ##Inf (the seed, when there are
  no agents) or a real finite number (once any tick has an agent), never
  NaN/-Infinity, so the ternary always evaluates to minClearance itself;
  metrics' :min-clearance is assigned directly.

  Clean-room: from-spec simulator. No AlpaSim / AlpaGym / DRIVE source or
  binaries. Civilian, SAE-L4 ceiling, sim-only (no actuation). Canonical
  KAMI engine: wadachi-sim (DriveSim lineage, ADR-2605261800 D1) + michibiki.

  nv-compat namespace; AV scope per wadachi / kami-autodrive ADRs. Wave 42
  of ADR-2607020130."
  (:require [kotoba.lang.kami-nv-compat.alpamayo :as alp]
            [kotoba.lang.kami-nv-compat.kami-drive.unicycle :as unicycle]))

;; ── world types ──────────────────────────────────────────────────────────
;;
;; WorldAgent {:id :kind :x :y :vx :vy :radius}  — world-frame, constant velocity
;; WorldEgo   {:x :y :yaw :speed :radius}
;; Scenario   {:ego :agents :command :speed-limit? :duration-s :hz}
;; RolloutStep    {:t :ego :action :min-clearance}
;; RolloutMetrics {:progress :collision :min-clearance :jerk-rms}
;; RolloutResult  {:steps :metrics :reward}

;; ── world -> ego-frame transform ────────────────────────────────────────

(defn- to-ego-frame
  "A world-frame agent as seen from `ego`'s frame (position + relative
  velocity, both rotated by -ego.yaw)."
  [ego a]
  (let [c   (Math/cos (- (:yaw ego)))
        s   (Math/sin (- (:yaw ego)))
        dx  (- (:x a) (:x ego))
        dy  (- (:y a) (:y ego))
        rvx (- (:vx a) (* (:speed ego) (Math/cos (:yaw ego))))
        rvy (- (:vy a) (* (:speed ego) (Math/sin (:yaw ego))))]
    {:id (:id a) :kind (:kind a)
     :x  (- (* dx c) (* dy s))
     :y  (+ (* dx s) (* dy c))
     :vx (- (* rvx c) (* rvy s))
     :vy (+ (* rvx s) (* rvy c))}))

(defn- advance-agent [a dt]
  (-> a (update :x + (* (:vx a) dt)) (update :y + (* (:vy a) dt))))

;; ── closed-loop rollout ──────────────────────────────────────────────────

(defn- reward-fn
  "AlpaGym-style reward: progress (normalized) − comfort penalty, zeroed on
  collision. Roughly [0, 1]."
  [metrics scenario]
  (letfn [(clamp01 [v] (cond (< v 0) 0 (> v 1) 1 :else v))]
    (if (:collision metrics)
      0
      (let [max-progress    (* (or (:speed-limit scenario) 30) (:duration-s scenario))
            progress-score  (clamp01 (/ (:progress metrics) (max 1e-3 max-progress)))
            comfort-penalty (clamp01 (/ (:jerk-rms metrics) 20))]     ; 20 m/s^3 ~ harsh
        (clamp01 (* progress-score (- 1 (* 0.3 comfort-penalty))))))))

(defn run-closed-loop
  "Run `model` (an alpamayo model map) closed-loop through `scenario`. Each
  tick: perceive (world -> ego frame), predict, apply the first dynamic
  action, advance agents, score."
  [model scenario]
  (let [hz      (:hz scenario)
        dt      (/ 1.0 hz)
        n-steps (max 1 (Math/round (double (* (:duration-s scenario) hz))))
        init    {:ego (:ego scenario) :agents (:agents scenario) :steps []
                  :progress 0.0 :collision false :min-clearance ##Inf
                  :prev-accel 0.0 :jerk-sq 0.0}
        final   (reduce
                  (fn [{:keys [ego agents steps progress collision min-clearance prev-accel jerk-sq]} i]
                    (let [t         (* i dt)
                          perceived (mapv #(to-ego-frame ego %) agents)
                          obs       {:ego {:x 0 :y 0 :yaw 0 :speed (:speed ego)}
                                     :command (:command scenario)
                                     :agents perceived
                                     :speed-limit (:speed-limit scenario)}
                          out       (alp/predict model obs)
                          wp1       (get (:trajectory out) 1)
                          action    (if wp1
                                      {:accel (:accel wp1) :curvature (:curvature wp1)}
                                      {:accel 0 :curvature 0})
                          before    {:x (:x ego) :y (:y ego)}
                          bev       (unicycle/step-unicycle
                                      {:x (:x ego) :y (:y ego) :yaw (:yaw ego) :speed (:speed ego)}
                                      action dt)
                          ego'      (assoc ego :x (:x bev) :y (:y bev) :yaw (:yaw bev) :speed (:speed bev))
                          progress' (+ progress (Math/hypot (- (:x ego') (:x before)) (- (:y ego') (:y before))))
                          agents'   (mapv #(advance-agent % dt) agents)
                          clearances (mapv (fn [a]
                                             (- (Math/hypot (- (:x a) (:x ego')) (- (:y a) (:y ego')))
                                                (+ (:radius a) (:radius ego'))))
                                           agents')
                          step-min    (reduce min ##Inf clearances)
                          collision'  (boolean (or collision (some #(<= % 0) clearances)))
                          min-clearance' (min min-clearance step-min)
                          jerk        (/ (- (:accel action) prev-accel) dt)
                          jerk-sq'    (+ jerk-sq (* jerk jerk))]
                      {:ego ego' :agents agents'
                       :steps (conj steps {:t t :ego ego' :action action :min-clearance step-min})
                       :progress progress' :collision collision'
                       :min-clearance min-clearance' :prev-accel (:accel action) :jerk-sq jerk-sq'}))
                  init (range n-steps))
        jerk-rms (Math/sqrt (/ (:jerk-sq final) n-steps))
        metrics  {:progress (:progress final) :collision (:collision final)
                  :min-clearance (:min-clearance final) :jerk-rms jerk-rms}]
    {:steps (:steps final) :metrics metrics :reward (reward-fn metrics scenario)}))

(def kami-engine "wadachi-sim")
(def adr "ADR-2606010600")
