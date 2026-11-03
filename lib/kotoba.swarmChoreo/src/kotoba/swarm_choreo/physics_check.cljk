(ns kotoba.swarm-choreo.physics-check
  "Physics-integration feasibility check: does `kami-autodrive`'s *real*
  closed-loop `:drone` autopilot + multirotor plant — not
  `kotoba.swarm-choreo.validate`'s idealized straight-line finite-
  difference approximation — actually reach a show segment's target
  within its scheduled time budget?

  This does not replace `kotoba.swarm-choreo.validate`; it is a stronger,
  slower, closed-loop check to run on segments `validate` already passed,
  the same relationship `autodrive.fleet`'s own reactive simulation has to
  a purely-kinematic distance/speed sanity check.

  ## Honest scope

  `kami-autodrive`'s `Plant`/autopilot stack is a horizontal, ground-
  projected 2D simulation (x, y, yaw) for every vehicle class, *including*
  `:drone` (`autodrive.classes`' own \"ground-projected agile multirotor\"
  note) — it has no altitude/climb-rate channel at all. This namespace
  therefore checks each segment's **horizontal** (x,y) feasibility through
  the real autopilot/plant (`horizontal-segment-feasible?`), and checks
  the **vertical** (z) rate separately via simple arithmetic against
  `default-vertical-speed-limit` — swarm-choreo's own conservative
  assumption, not sourced from `kami-autodrive` (which models no vertical
  dynamics to check a climb rate against at all).

  Pure data in, pure data out — the simulation loop is deterministic given
  its inputs (fixed `sim-dt`, no wall clock, no I/O). Portable `.cljc`."
  (:require [autodrive.geom :as g]
            [autodrive.types :as t]
            [autodrive.classes :as classes]
            [autodrive.dynamics :as dynamics]
            [autodrive.autopilot :as ap]
            [autodrive.plant :as plant]))

(defn- abs-val [x] (if (neg? x) (- x) x))

;; ---------------------------------------------------------------------------
;; Vertical (swarm-choreo's own assumption -- kami-autodrive models no
;; altitude channel at all, so there is nothing in kami-autodrive to check
;; a climb rate against)
;; ---------------------------------------------------------------------------

(def default-vertical-speed-limit
  "swarm-choreo's own conservative default vertical (climb/descent) speed
  limit for a `:drone` performer, metres/second."
  5.0)

(defn vertical-feasible?
  "True when the altitude change from `z0` to `z1` over `dt` seconds implies
  a climb/descent rate at or under `limit` (default
  `default-vertical-speed-limit`). `dt` <= 0 is always feasible (a
  degenerate/zero-duration segment is `kotoba.swarm-choreo.validate`'s
  concern, not this namespace's)."
  [z0 z1 dt & {:keys [limit] :or {limit default-vertical-speed-limit}}]
  (or (<= dt 0)
      (<= (/ (abs-val (- z1 z0)) dt) limit)))

;; ---------------------------------------------------------------------------
;; Horizontal -- the real closed-loop autopilot + multirotor plant
;; ---------------------------------------------------------------------------

(defn horizontal-segment-feasible?
  "Simulate `kami-autodrive`'s real closed-loop `:drone` autopilot +
  `autodrive.dynamics/multirotor` plant, starting at rest at `start-pos`
  (a `{:x :y ...}` map — `:z` is ignored) facing `start-yaw`, commanded to
  `goal-pos` (same shape), in an open world — an empty lidar sweep every
  tick, since a show segment's own feasibility is what is under test, not
  obstacle avoidance (an empty return list leaves `autodrive.perception`'s
  occupancy grid entirely free, per its own default-0/free cell state).

  Returns true if the autopilot reports `:arrived` within
  `(* budget-factor (max dt-budget sim-dt))` seconds of simulated flight.
  `budget-factor` (default 1.5) is deliberate slack over the show's own
  scheduled `dt-budget`: the autopilot's pure-pursuit/PID speed profile
  does not exactly match a straight-line interpolation, so this checks
  feasibility within a margin, not exact time-matching (see the namespace
  docstring). `sim-dt` (default 1/30s) is the simulation step; it has no
  relationship to the show's own waypoint timestamps."
  [start-pos start-yaw goal-pos dt-budget
   & {:keys [sim-dt budget-factor] :or {sim-dt (/ 1.0 30) budget-factor 1.5}}]
  (let [limits (classes/limits :drone)
        start-pose (t/pose2 (:x start-pos) (:y start-pos) start-yaw)
        goal-xy (g/v2 (:x goal-pos) (:y goal-pos))
        cfg (ap/autopilot-config :drone limits)
        max-elapsed (* budget-factor (max dt-budget sim-dt))]
    (loop [pl (dynamics/multirotor start-pose limits)
           auto (ap/set-goal (ap/new-autopilot cfg start-pose) goal-xy)
           elapsed 0.0]
      (cond
        (:arrived auto) true
        (> elapsed max-elapsed) false
        :else
        (let [pose (plant/pose pl)
              [auto' cmd] (ap/step auto pose (plant/speed pl) [] pose sim-dt)
              pl' (plant/step pl cmd sim-dt)]
          (recur pl' auto' (+ elapsed sim-dt)))))))

;; ---------------------------------------------------------------------------
;; Whole-show sweep
;; ---------------------------------------------------------------------------

(defn show-segments-feasible
  "For every performer/segment in `s` (a `kotoba.swarm-choreo.show` show),
  runs `horizontal-segment-feasible?` (real autopilot+plant) and
  `vertical-feasible?` (swarm-choreo's own vertical-rate assumption).
  Returns a vector of `{:performer :segment-index :horizontal? :vertical?}`
  — one entry per trajectory segment with a positive duration. Callers
  decide what counts as a failure, e.g. `(remove (every-pred :horizontal?
  :vertical?) (show-segments-feasible s))`. `opts` are passed through to
  `horizontal-segment-feasible?` (`:sim-dt`/`:budget-factor`) and
  `vertical-feasible?` (`:limit`)."
  [s & opts]
  (vec
   (for [p (:show/performers s)
         [i [a b]] (map-indexed vector (partition 2 1 (:performer/trajectory p)))
         :let [dt (- (:waypoint/t b) (:waypoint/t a))]
         :when (pos? dt)]
     {:performer (:performer/id p)
      :segment-index i
      :horizontal? (apply horizontal-segment-feasible?
                           (:waypoint/pos a) (:waypoint/yaw a) (:waypoint/pos b) dt opts)
      :vertical? (apply vertical-feasible?
                         (:z (:waypoint/pos a)) (:z (:waypoint/pos b)) dt opts)})))
