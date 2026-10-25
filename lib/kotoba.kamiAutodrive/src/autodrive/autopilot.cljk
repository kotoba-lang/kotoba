(ns autodrive.autopilot
  "The autopilot: closes perception -> planning -> control into one `step`
  and runs a small driving state machine.

  Restored from the deleted `kami-autodrive` Rust crate
  (kotoba-lang/kami-engine, PR #82), ADR-2607010930.

  `Autopilot` is a plain immutable map; `step`/`step-multimodal` are pure
  functions `autopilot -> [autopilot' command]` rather than in-place
  mutation, the idiomatic CLJC equivalent of the original `&mut self`
  methods."
  (:require [autodrive.geom :as g]
            [autodrive.types :as t]
            [autodrive.control :as ctl]
            [autodrive.perception :as perc]
            [autodrive.planner :as planner]))

;; ─────────────────────────────── Config ───────────────────────────────

(defn autopilot-config
  "Tunable autopilot parameters for `class` (see `autodrive.classes`)."
  [class limits]
  {:limits limits
   :grid-half-extent 60.0
   :grid-res 0.5
   ;; Lidar sensor-frame height band kept as obstacles (m).
   :z-band [-1.0 1.5]
   :replan-period 20
   :goal-tol (max 1.0 (:footprint-radius limits))
   :emergency-cone 0.35
   :lateral-accel 3.0
   :brake-margin 1.6
   :dynamic-obstacles true
   ;; World-frame height band (m above ground) kept from depth-camera
   ;; back-projection.
   :camera-z-band [0.3 2.5]
   :stuck-limit 0 ; recovery off by default (opt-in)
   :recovery-ticks 60
   ;; A fixed-wing can't hover or capture a point inside its turn radius — it
   ;; loiters over the waypoint instead.
   :loiter-radius (when (= class :aircraft) 200.0)})

;; ─────────────────────────────── Autopilot ───────────────────────────────

(defn new-autopilot
  "One autopilot instance driving a single vehicle from `start`."
  [cfg start]
  {:cfg cfg
   :state :idle
   :grid (perc/centered (t/pos start) (:grid-half-extent cfg) (:grid-res cfg))
   :home (t/pos start)
   :path []
   :goal nil
   :arrived false
   :pursuit (ctl/pure-pursuit 4.0 0.4 (:turn-radius-ref (:limits cfg)))
   :speed-ctl (ctl/speed-controller 0.6 0.05 0.02)
   :steps-since-replan ##Inf
   :stuck-ticks 0
   :recovery-ticks 0
   :recovery-steer 0.0
   :best-dist ##Inf
   :recoveries-since-progress 0
   :last-pose start
   :last-target-speed 0.0
   :last-cross-track 0.0})

(defn set-goal
  "Size the occupancy grid to cover the whole home->goal corridor plus a
  margin, so the planner can always reach the goal cell and route laterally
  around obstacles."
  [ap goal]
  (let [cfg (:cfg ap)
        home (:home ap)
        center (g/scale2 (g/add2 home goal) 0.5)
        margin (+ (* (:footprint-radius (:limits cfg)) 4.0) 10.0)
        half (max (:grid-half-extent cfg) (+ (* (g/distance2 home goal) 0.5) margin))]
    (assoc ap
           :grid (perc/centered center half (:grid-res cfg))
           :goal goal
           :arrived false
           :steps-since-replan ##Inf
           :stuck-ticks 0
           :recovery-ticks 0
           :best-dist ##Inf
           :recoveries-since-progress 0
           :state :cruise)))

(defn path [ap] (:path ap))
(defn grid [ap] (:grid ap))

(defn telemetry
  "Read-only status snapshot from the most recent tick."
  [ap]
  (let [distance-to-goal (if-let [goal (:goal ap)]
                            (g/distance2 (t/pos (:last-pose ap)) goal)
                            ##Inf)]
    {:state (:state ap)
     :distance-to-goal distance-to-goal
     :cross-track-error (:last-cross-track ap)
     :target-speed (:last-target-speed ap)
     :path-waypoints (count (:path ap))}))

;; ─────────────────────────────── Helpers ───────────────────────────────

(defn- point-segment-distance [p a b]
  (let [ab (g/sub2 b a)
        len2 (g/length-sq2 ab)]
    (if (< len2 1e-9)
      (g/distance2 p a)
      (let [tt (min 1.0 (max 0.0 (/ (g/dot2 (g/sub2 p a) ab) len2)))]
        (g/distance2 p (g/add2 a (g/scale2 ab tt)))))))

(defn- cross-track-error
  "Lateral deviation of `p` from a path polyline = min point-to-segment
  distance over its segments (0 for a path with fewer than 2 points)."
  [p path]
  (if (< (count path) 2)
    0.0
    (apply min (map (fn [[a b]] (point-segment-distance p a b))
                     (map vector path (rest path))))))

(defn- braking-distance
  "Kinematic stopping distance v^2 / (2*d_max) with a safety margin."
  [ap speed]
  (* (:brake-margin (:cfg ap))
     (/ (* speed speed) (* 2.0 (max 0.1 (:max-decel (:limits (:cfg ap))))))))

(defn- fwd-clearance
  "Nearest forward obstacle range fused over the lidar cone and every depth
  camera (min of all available sources), or nil if nothing is ahead."
  [ap lidar cameras cone]
  (let [z-band (:z-band (:cfg ap))
        best (perc/forward-clearance lidar cone z-band)]
    (reduce (fn [best [depth cam]]
              (if-let [c (perc/forward-clearance-camera depth cam cone (:camera-z-band (:cfg ap)))]
                (if best (min best c) c)
                best))
            best cameras)))

(defn- open-side-steer
  "Pick the reverse steer that swings the nose toward the more-open side.
  Compares nearest obstacle range in the left vs right forward quadrants;
  reversing with the returned steer rotates the nose toward open space."
  [ap lidar]
  (let [[lo hi] (:z-band (:cfg ap))]
    (loop [rs lidar left-min ##Inf right-min ##Inf]
      (if (empty? rs)
        (if (>= left-min right-min) -1.0 1.0)
        (let [r (first rs) rng (:range r)]
          (if (or (nil? rng) (not (g/finite? rng)))
            (recur (rest rs) left-min right-min)
            (let [p (:point-sensor r)]
              (if (or (< (:z p) lo) (> (:z p) hi))
                (recur (rest rs) left-min right-min)
                (let [az (Math/atan2 (:y p) (:x p))
                      gr (Math/sqrt (+ (* (:x p) (:x p)) (* (:y p) (:y p))))]
                  (cond
                    (and (>= az 0.2) (< az 1.4)) (recur (rest rs) (min left-min gr) right-min)
                    (and (>= az -1.4) (< az -0.2)) (recur (rest rs) left-min (min right-min gr))
                    :else (recur (rest rs) left-min right-min)))))))))))

(defn- register-stuck
  "Count a stuck tick (emergency-stop or no route). Once `stuck-limit`
  consecutive stuck ticks accrue, kick off a reverse K-turn toward the
  more-open side; otherwise just hold a stop."
  [ap lidar]
  (let [stuck-ticks (inc (:stuck-ticks ap))
        exhausted (>= (:recoveries-since-progress ap) 4)]
    (if (and (pos? (:stuck-limit (:cfg ap))) (>= stuck-ticks (:stuck-limit (:cfg ap))) (not exhausted))
      (let [recovery-steer (open-side-steer ap lidar)]
        [(assoc ap
                :recovery-steer recovery-steer
                :recovery-ticks (dec (:recovery-ticks (:cfg ap)))
                :recoveries-since-progress (inc (:recoveries-since-progress ap))
                :stuck-ticks 0
                :state :recovering)
         (t/reverse-with 0.6 recovery-steer)])
      [(assoc ap :stuck-ticks stuck-ticks :state :blocked) (t/stop)])))

(defn- loiter-step
  "Guidance for a non-stopping vehicle: fly straight to the waypoint until
  near the loiter ring, then orbit it (chase a carrot that leads around the
  circle). Counts the waypoint reached once established within ~1.5*r."
  [ap pose speed goal r dt]
  (let [d (g/distance2 (t/pos pose) goal)
        arrived (or (:arrived ap) (<= d (* 1.2 r)))
        [target speed-frac] (if (> d (* 2.0 r))
                              [goal 1.0]
                              (let [from (g/sub2 (t/pos pose) goal)
                                    ang (+ (Math/atan2 (:y from) (:x from)) 0.5)]
                                [(g/add2 goal (g/scale2 (g/v2 (Math/cos ang) (Math/sin ang)) r)) 0.6]))
        [steer-val _] (ctl/steer (:pursuit ap) pose speed [(t/pos pose) target])
        state (if arrived :arrived :loitering)
        target-speed (* (:max-speed (:limits (:cfg ap))) speed-frac)
        cross-track (Math/abs (- d r))
        [sc' throttle brake] (ctl/update-speed (:speed-ctl ap) target-speed speed dt)
        cmd (t/clamp-cmd (t/command :throttle throttle :brake brake :steer steer-val))]
    [(assoc ap :arrived arrived :state state :last-target-speed target-speed
            :last-cross-track cross-track :speed-ctl sc')
     cmd]))

;; ─────────────────────────────── Step ───────────────────────────────

(declare step-multimodal)

(defn step
  "One control tick. `pose`/`speed` are the plant's current state; `lidar` is
  this tick's sweep with the sensor at `sensor` (planar pose). Returns
  `[autopilot' command]`."
  [ap pose speed lidar sensor dt]
  (step-multimodal ap pose speed lidar [] sensor dt))

(defn step-multimodal
  "Multi-modal control tick: fuse the lidar sweep and zero or more pinhole
  depth cameras into the occupancy map this tick. Reactive emergency braking
  still uses the lidar forward cone, so a camera-only configuration
  plans/routes but has no sub-planner reflex — pair a camera with at least a
  forward lidar for the reactive layer. Returns `[autopilot' command]`."
  [ap pose speed lidar cameras sensor dt]
  (let [ap (assoc ap :last-pose pose)
        cfg (:cfg ap)
        goal (:goal ap)]
    (cond
      (nil? goal)
      [(assoc ap :state :idle) (t/stop)]

      (:loiter-radius cfg)
      (loiter-step ap pose speed goal (:loiter-radius cfg) dt)

      (or (:arrived ap) (<= (g/distance2 (t/pos pose) goal) (:goal-tol cfg)))
      [(assoc ap :arrived true :state :arrived) (t/stop)]

      (pos? (:recovery-ticks ap))
      (let [recovery-ticks (dec (:recovery-ticks ap))
            ap (assoc ap :recovery-ticks recovery-ticks :state :recovering)
            ap (if (zero? recovery-ticks)
                 (assoc ap :stuck-ticks 0 :path [] :steps-since-replan ##Inf)
                 ap)]
        [ap (t/reverse-with 0.6 (:recovery-steer ap))])

      :else
      (let [;; 1. Perception.
            grid0 (if (:dynamic-obstacles cfg) (perc/clear (:grid ap)) (:grid ap))
            grid1 (perc/ingest-lidar grid0 lidar sensor (:z-band cfg))
            grid2 (reduce (fn [g [depth cam]] (perc/ingest-camera-depth g depth cam (:camera-z-band cfg)))
                           grid1 cameras)
            ap (assoc ap :grid grid2)

            ;; 2. Reactive emergency stop.
            stop-dist (braking-distance ap speed)
            clear (fwd-clearance ap lidar cameras (:emergency-cone cfg))]
        (if (and clear (<= clear (+ stop-dist (:footprint-radius (:limits cfg)))))
          (let [ap (assoc ap :speed-ctl (ctl/reset-speed-controller (:speed-ctl ap)))]
            (register-stuck ap lidar))
          ;; 3. (Re)plan if needed.
          (let [steps-since-replan (inc (:steps-since-replan ap))
                path (:path ap)
                path-blocked (and (>= (count path) 2)
                                   (some (fn [[a b]] (not (perc/line-clear? (:grid ap) a b)))
                                         (map vector path (rest path))))
                need-replan (or (< (count path) 2) path-blocked
                                 (>= steps-since-replan (:replan-period cfg)))
                ap (assoc ap :steps-since-replan steps-since-replan)
                [ap blocked-out]
                (if need-replan
                  ;; Plan with a small extra cushion (`planning-margin`) beyond
                  ;; the raw footprint radius, so a route through a tight gap
                  ;; keeps clearance strictly greater than the reactive
                  ;; emergency-stop's own `footprint-radius` threshold (below).
                  ;; Without this cushion a route that just grazes the exact
                  ;; footprint-radius margin can trip the reactive stop the
                  ;; instant the vehicle reaches that point and — since
                  ;; `stuck-limit` is 0 (recovery off) by default — latch a
                  ;; permanent stop. This is a deliberate, documented
                  ;; port-time addition (see the README); it does not change
                  ;; `autodrive.perception/inflated`'s own contract/tests.
                  (let [inflated (perc/inflated (:grid ap) (+ (:footprint-radius (:limits cfg)) 0.3))
                        new-path (planner/plan inflated (t/pos pose) goal)]
                    (if (and new-path (>= (count new-path) 2))
                      [(assoc ap :path new-path :steps-since-replan 0) nil]
                      (if (or (< (count path) 2) path-blocked)
                        (let [[ap' cmd'] (register-stuck ap lidar)]
                          [ap' cmd'])
                        [ap nil])))
                  [ap nil])]
            (if blocked-out
              [ap blocked-out]
              ;; 4. Lateral: pure pursuit.
              (let [[steer-val target-idx] (ctl/steer (:pursuit ap) pose speed (:path ap))
                    ;; 5. Longitudinal.
                    max-speed (:max-speed (:limits cfg))
                    ts (min max-speed (ctl/curvature-speed-limit (:path ap) target-idx (:lateral-accel cfg)))
                    d-goal (g/distance2 (t/pos pose) goal)
                    ts (min ts (Math/sqrt (* 2.0 (:max-decel (:limits cfg)) d-goal)))
                    clear2 (fwd-clearance ap lidar cameras (* 2.0 (:emergency-cone cfg)))
                    ts (if clear2
                         (let [near (braking-distance ap max-speed)
                               tt (min 1.0 (max 0.0 (/ (- clear2 stop-dist) (+ near 1e-3))))]
                           (min ts (* tt max-speed)))
                         ts)
                    state (if (< ts (* max-speed 0.6)) :slow :cruise)
                    best-dist (:best-dist ap)
                    [best-dist recoveries-since-progress]
                    (if (< d-goal (- best-dist 2.0))
                      [d-goal 0]
                      [best-dist (:recoveries-since-progress ap)])
                    [sc' throttle brake] (ctl/update-speed (:speed-ctl ap) ts speed dt)
                    cmd (t/clamp-cmd (t/command :throttle throttle :brake brake :steer steer-val))]
                [(assoc ap
                        :state state
                        :last-target-speed ts
                        :last-cross-track (cross-track-error (t/pos pose) (:path ap))
                        :stuck-ticks 0
                        :best-dist best-dist
                        :recoveries-since-progress recoveries-since-progress
                        :speed-ctl sc')
                 cmd]))))))))
