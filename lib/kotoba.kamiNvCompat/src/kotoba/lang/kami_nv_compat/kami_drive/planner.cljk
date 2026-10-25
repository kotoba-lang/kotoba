(ns kotoba.lang.kami-nv-compat.kami-drive.planner
  "Clean-room reasoning planner (michibiki 導き) — JVM port of
  src/kami-drive/planner.ts. The canonical planner behind the alpamayo VLA
  facade: given the ego state, a navigation command, and perceived agents (ego
  frame), produces (a) a dynamic-action sequence rolled out to an Alpamayo-
  format trajectory and (b) a Chain-of-Causation trace. Deterministic +
  auditable; NO actuation — returns a recommended trajectory only. Wave 9 of
  ADR-2607020130."
  (:require [kotoba.lang.text :as str]
            [kotoba.lang.kami-nv-compat.kami-drive.coc :as coc]
            [kotoba.lang.kami-nv-compat.kami-drive.unicycle :as u]))

(def default-planner
  "Default planner config (Alpamayo: 6.4 s horizon at 10 Hz = 64 waypoints)."
  {:horizon-s       6.4
   :hz              10
   :comfort-accel   1.5
   :turn-curvature  0.05
   :look-ahead      60      ; real AV perception ranges past stopping distance
   :lane-half-width 1.5
   :safe-gap        5
   :max-speed       u/default-max-speed})

(def ^:private stop-words  ["stop" "halt" "brake" "止ま" "停止"])
(def ^:private left-words  ["left" "左"])
(def ^:private right-words ["right" "右"])

(defn command-from-instruction
  "Map a free-text instruction to a navigation command (nil if none)."
  [text]
  (let [t (str/lower text)]
    (cond
      (some #(str/includes? t %) stop-words)                                   "stop"
      (and (some #(str/includes? t %) left-words)  (str/includes? t "turn"))   "turn_left"
      (and (some #(str/includes? t %) right-words) (str/includes? t "turn"))   "turn_right"
      (some #(str/includes? t %) left-words)                                   "turn_left"
      (some #(str/includes? t %) right-words)                                  "turn_right"
      :else                                                                    nil)))

(defn- clamp-abs [v m]
  (cond (> v m) m (< v (- m)) (- m) :else v))

(defn- label-kind [k]
  (condp = k "pedestrian" "Pedestrian" "cyclist" "Cyclist" "vehicle" "Vehicle" "Object"))

(defn- fmt
  "Fixed-decimal string, e.g. (fmt 1.5 1) => \"1.5\"."
  [x decimals]
  #?(:clj  (String/format java.util.Locale/US (str "%." decimals "f") (to-array [(double x)]))
     :cljs (.toFixed (double x) decimals)))

;; ── yield reasoning ───────────────────────────────────────────────────────

(defn- yield-check
  "Find the most constraining in-path agent + the speed it allows. An agent is
  in-path when it is ahead (x>0) within the look-ahead and its lateral offset
  is within the corridor (accounting for its lateral motion)."
  [obs cfg]
  (let [{:keys [look-ahead lane-half-width safe-gap comfort-accel max-speed]} cfg]
    (reduce
      (fn [decision a]
        (if (or (<= (:x a) 0) (> (:x a) look-ahead))
          decision
          (let [y-now        (:y a)
                y-soon       (+ y-now (* (:vy a) 1.0))
                in-corridor? (or (<= (min (Math/abs y-now) (Math/abs y-soon)) lane-half-width)
                                 (< (* y-now y-soon) 0))]   ; crossed centerline within 1 s
            (if (not in-corridor?)
              decision
              (let [gap (- (:x a) safe-gap)
                    vru? (or (= (:kind a) "pedestrian") (= (:kind a) "cyclist"))
                    allowed (if vru?
                              0
                              (max 0 (min max-speed (+ (:vx a) (Math/sqrt (* 2 comfort-accel (max 0 gap)))))))]
                (if (< allowed (:target-speed decision))
                  {:target-speed allowed :agent a :gap gap}
                  decision))))))
      {:target-speed max-speed :agent nil :gap #?(:clj Double/POSITIVE_INFINITY :cljs js/Infinity)}
      (:agents obs))))

;; ── plan ──────────────────────────────────────────────────────────────────

(defn plan
  "Produce a recommended trajectory + Chain-of-Causation for an observation.
  `obs` = {:ego :command :agents :instruction? :speed-limit?}; `config` is an
  optional partial override of default-planner. Returns
  {:trajectory :reasoning :actions}."
  ([obs]
   (plan obs nil))
  ([obs config]
   (let [cfg     (merge default-planner config)
         steps   (max 1 (long (Math/round (double (* (:horizon-s cfg) (:hz cfg))))))
         dt      (/ 1.0 (:hz cfg))
         command (if-let [instr (:instruction obs)]
                   (or (command-from-instruction instr) (:command obs))
                   (:command obs))
         builder (coc/causation-builder "nominal")
         added?  (volatile! false)
         add!    (fn [observation inference action kf]
                   (coc/add-step! builder observation inference action kf)
                   (vreset! added? true))
         st      (atom {:cluster "nominal"
                        :target-curvature 0
                        :target-speed (if (= command "stop") 0 (min (:max-speed cfg) (:speed-limit obs (:max-speed cfg))))})]
     ;; ── lateral target from the command ──
     (case command
       "turn_left"  (do (swap! st assoc :target-curvature (:turn-curvature cfg) :cluster "intersection")
                        (add! "Navigation command is turn-left"
                              "the ego is approaching a left turn"
                              (str "steer left at curvature " (fmt (:turn-curvature cfg) 3) " /m")
                              0))
       "turn_right" (do (swap! st assoc :target-curvature (- (:turn-curvature cfg)) :cluster "intersection")
                        (add! "Navigation command is turn-right"
                              "the ego is approaching a right turn"
                              (str "steer right at curvature " (fmt (:turn-curvature cfg) 3) " /m")
                              0))
       nil)

     ;; ── longitudinal target from the command + posted limit ──
     (when (= command "stop")
       (swap! st assoc :cluster "stop")
       (add! "Navigation command is stop"
             "the ego must come to a controlled halt"
             "decelerate to zero speed"
             0))

     ;; ── yield reasoning against perceived agents ──
     (let [yld (yield-check obs cfg)
           target-speed (:target-speed @st)]
       (if (and (:agent yld) (< (:target-speed yld) target-speed))
         (let [a (:agent yld)
               vru? (or (= (:kind a) "pedestrian") (= (:kind a) "cyclist"))
               kf (min steps (max 1 (long (Math/round (double (* (/ (:x a) (max 0.1 (:speed (:ego obs)))) (:hz cfg)))))))]
           (swap! st assoc :target-speed (:target-speed yld) :cluster (if vru? "vru_interaction" "yield"))
           (add! (str (label-kind (:kind a)) " " (fmt (:x a) 1) " m ahead within the ego corridor")
                 (if vru? "must yield to a vulnerable road user" "must keep a safe following gap")
                 (if (zero? (:target-speed yld))
                   "decelerate to a stop"
                   (str "reduce speed to " (fmt (:target-speed yld) 1) " m/s"))
                 kf))
         (when (and (pos? steps) (= command "keep_lane") (not @added?))
           (add! "Lane is clear ahead"
                 "nominal cruising conditions hold"
                 (str "maintain target speed " (fmt (:target-speed @st) 1) " m/s")
                 0))))

     ;; ── action sequence: P-control toward target speed + curvature ──
     (let [target-speed     (:target-speed @st)
           target-curvature (:target-curvature @st)
           actions (loop [i 0 speed (:speed (:ego obs)) out []]
                     (if (>= i steps)
                       out
                       (let [speed-err (- target-speed speed)
                             accel     (clamp-abs (/ speed-err dt) (:comfort-accel cfg))
                             ramp      (min 1.0 (* i dt))           ; ease curvature in over the 1st second
                             curvature (if (> speed 0.1) (* target-curvature ramp) 0)
                             speed'    (min (:max-speed cfg) (max 0 (+ speed (* accel dt))))]
                         (recur (inc i) speed' (conj out {:accel accel :curvature curvature})))))
           trajectory (u/rollout-trajectory
                        {:x 0 :y 0 :yaw 0 :speed (:speed (:ego obs))}
                        actions dt (:max-speed cfg))
           reasoning (coc/build (coc/set-cluster! builder (:cluster @st)))]
       {:trajectory trajectory :reasoning reasoning :actions actions}))))
