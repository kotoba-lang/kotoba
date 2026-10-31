(ns kotoba.swarm-choreo.validate
  "Offline verification of a `kotoba.swarm-choreo.show` show *before* it is
  ever armed: whole-timeline pairwise minimum separation (the
  `autodrive.fleet/min-separation` idea, applied to a precomputed timeline
  instead of one reactive tick), per-performer max-speed/max-accel against
  `autodrive.classes/limits`, and geofence containment. A show that fails
  validation must not have a `kotoba.swarm-choreo.gate` action proposed
  for it.

  ## Honest limits

  This is a discrete-time approximation, not a continuous-time proof: two
  trajectories can in principle pass closer than any sampled instant
  between two samples (e.g. two straight paths crossing between two
  default-spaced samples). `min-separation`/`separation-violations` accept
  a `:sample-dt` to trade validation cost for a finer time grid; neither
  claims exactness at any resolution. Nor does *any* check here account
  for real-world RTK GPS drift, wind, clock sync, or radio range — a real
  operator must still carry independent safety margins (ADR-2607052300's
  Consequences).

  A **missing geofence is treated as a validation failure**, not a
  silently unconstrained show — flying a real multirotor fleet with
  nothing checking flight-area containment is exactly the kind of gap
  this namespace exists to catch before a `kotoba.swarm-choreo.gate`
  action is even proposed.

  Pure data in, pure data out: no network, no I/O, no clock (a `t` in
  seconds since show start always comes from the show's own waypoints,
  never a wall clock). Portable `.cljc`."
  (:require [autodrive.geom :as g]
            [autodrive.classes :as classes]
            [kotoba.swarm-choreo.show :as show]))

;; ---------------------------------------------------------------------------
;; Interpolation
;; ---------------------------------------------------------------------------

(defn- clamp01 [x] (min 1.0 (max 0.0 x)))

(defn- lerp3
  "3D linear interpolation between `{:x :y :z}` maps `a`/`b` at `frac`
  [0,1]. Not exposed by `autodrive.geom` (only `lerp2` is) — a small local
  helper built from its existing `add3`/`sub3`/`scale3`, so this namespace
  extends nothing in `kami-autodrive` itself."
  [a b frac]
  (g/add3 a (g/scale3 (g/sub3 b a) frac)))

(defn- abs-val [x] (if (neg? x) (- x) x))

(defn interpolate-position
  "Performer `p`'s position at time `t` (seconds since show start): linear
  interpolation between the two trajectory waypoints bracketing `t`; holds
  the first waypoint's position for `t` before the trajectory starts and
  the last waypoint's position for `t` after it ends. `nil` for a performer
  with an empty trajectory."
  [p t]
  (let [wps (:performer/trajectory p)]
    (when (seq wps)
      (cond
        (<= t (:waypoint/t (first wps))) (:waypoint/pos (first wps))
        (>= t (:waypoint/t (last wps))) (:waypoint/pos (last wps))
        :else
        (loop [[a b & more] wps]
          (if (and b (<= (:waypoint/t a) t) (<= t (:waypoint/t b)))
            (let [span (- (:waypoint/t b) (:waypoint/t a))
                  frac (if (pos? span) (clamp01 (/ (- t (:waypoint/t a)) span)) 0.0)]
              (lerp3 (:waypoint/pos a) (:waypoint/pos b) frac))
            (recur (cons b more))))))))

(defn positions-at
  "`{performer-id position}` for every performer in `show` at time `t`."
  [s t]
  (into {}
        (keep (fn [p]
                (when-let [pos (interpolate-position p t)]
                  [(:performer/id p) pos])))
        (:show/performers s)))

(defn- sample-times
  "Sample instants for a whole-timeline sweep: every performer's own
  waypoint timestamps, plus a `sample-dt`-spaced grid across the show's
  duration (see the namespace docstring's discrete-time-approximation
  caveat)."
  [s sample-dt]
  (let [dur (show/duration s)
        grid (range 0.0 (+ dur sample-dt) sample-dt)
        waypoint-times (for [p (:show/performers s) w (:performer/trajectory p)]
                          (:waypoint/t w))]
    (sort (distinct (concat grid waypoint-times)))))

;; ---------------------------------------------------------------------------
;; Pairwise separation
;; ---------------------------------------------------------------------------

(defn- footprint-radius [p] (:footprint-radius (classes/limits (:performer/class p))))

(defn min-separation
  "Smallest interpolated surface-to-surface gap between any two performers
  across the whole show, at the `sample-times` sampling (default
  `:sample-dt` 0.5s). Negative => the two performers' footprints overlap
  at that sample. `##Inf` for a show with fewer than two performers."
  [s & {:keys [sample-dt] :or {sample-dt 0.5}}]
  (let [performers (:show/performers s)]
    (apply min ##Inf
           (for [t (sample-times s sample-dt)
                 :let [positions (positions-at s t)]
                 i (range (count performers))
                 j (range (inc i) (count performers))
                 :let [pa (nth performers i) pb (nth performers j)
                       posa (get positions (:performer/id pa))
                       posb (get positions (:performer/id pb))]
                 :when (and posa posb)]
             (- (g/distance3 posa posb) (footprint-radius pa) (footprint-radius pb))))))

(defn separation-violations
  "Every `(performer-a, performer-b, t, gap)` sample where the interpolated
  gap is negative, at the same sampling as `min-separation`."
  [s & {:keys [sample-dt] :or {sample-dt 0.5}}]
  (let [performers (:show/performers s)]
    (vec
     (for [t (sample-times s sample-dt)
           :let [positions (positions-at s t)]
           i (range (count performers))
           j (range (inc i) (count performers))
           :let [pa (nth performers i) pb (nth performers j)
                 posa (get positions (:performer/id pa))
                 posb (get positions (:performer/id pb))]
           :when (and posa posb)
           :let [gap (- (g/distance3 posa posb) (footprint-radius pa) (footprint-radius pb))]
           :when (neg? gap)]
       {:violation/kind :separation
        :violation/performers [(:performer/id pa) (:performer/id pb)]
        :violation/t t
        :violation/gap gap}))))

;; ---------------------------------------------------------------------------
;; Speed / accel
;; ---------------------------------------------------------------------------

(defn speed-violations
  "Every trajectory segment whose average speed exceeds its performer's
  `autodrive.classes/limits` `:max-speed`."
  [s]
  (vec
   (for [p (:show/performers s)
         :let [limit (:max-speed (classes/limits (:performer/class p)))
               wps (:performer/trajectory p)]
         [a b] (partition 2 1 wps)
         :let [dt (- (:waypoint/t b) (:waypoint/t a))]
         :when (pos? dt)
         :let [speed (/ (g/distance3 (:waypoint/pos a) (:waypoint/pos b)) dt)]
         :when (> speed limit)]
     {:violation/kind :speed
      :violation/performer (:performer/id p)
      :violation/t (:waypoint/t b)
      :violation/speed speed
      :violation/limit limit})))

(defn accel-violations
  "Every consecutive segment-pair whose average acceleration (the change in
  segment speed over the pair's combined half-durations) exceeds its
  performer's `:max-accel` (speeding up) or `:max-decel` (slowing down)."
  [s]
  (vec
   (for [p (:show/performers s)
         :let [limits (classes/limits (:performer/class p))
               wps (:performer/trajectory p)]
         [[a b] [_ c]] (partition 2 1 (partition 2 1 wps))
         :let [dt0 (- (:waypoint/t b) (:waypoint/t a))
               dt1 (- (:waypoint/t c) (:waypoint/t b))]
         :when (and (pos? dt0) (pos? dt1))
         :let [v0 (/ (g/distance3 (:waypoint/pos a) (:waypoint/pos b)) dt0)
               v1 (/ (g/distance3 (:waypoint/pos b) (:waypoint/pos c)) dt1)
               accel (/ (- v1 v0) (/ (+ dt0 dt1) 2.0))
               limit (if (pos? accel) (:max-accel limits) (:max-decel limits))]
         :when (> (abs-val accel) limit)]
     {:violation/kind :accel
      :violation/performer (:performer/id p)
      :violation/t (:waypoint/t b)
      :violation/accel accel
      :violation/limit limit})))

;; ---------------------------------------------------------------------------
;; Geofence — a vertical cylinder
;; ---------------------------------------------------------------------------

(defn geofence-violations
  "Every waypoint (of every performer) outside `s`'s `:show/geofence` — a
  vertical cylinder `{:geofence/center-x _ :geofence/center-y _
  :geofence/radius _ :geofence/min-alt _ :geofence/max-alt _}`. A show
  with no geofence at all yields a single `:geofence-missing` violation
  (see the namespace docstring) instead of silently skipping the check."
  [s]
  (if-let [gf (:show/geofence s)]
    (let [center (g/v2 (:geofence/center-x gf) (:geofence/center-y gf))]
      (vec
       (for [p (:show/performers s)
             w (:performer/trajectory p)
             :let [pos (:waypoint/pos w)
                   horiz (g/distance2 (g/v2 (:x pos) (:y pos)) center)]
             :when (or (> horiz (:geofence/radius gf))
                       (< (:z pos) (:geofence/min-alt gf))
                       (> (:z pos) (:geofence/max-alt gf)))]
         {:violation/kind :geofence
          :violation/performer (:performer/id p)
          :violation/t (:waypoint/t w)
          :violation/pos pos})))
    [{:violation/kind :geofence-missing}]))

;; ---------------------------------------------------------------------------
;; Top-level validate
;; ---------------------------------------------------------------------------

(defn validate
  "Validate `s` before it is ever armed. Returns `{:valid? bool :violations
  [...]}` — combines `separation-violations`, `speed-violations`,
  `accel-violations`, and `geofence-violations`. Any non-empty result makes
  `:valid?` false."
  [s & {:keys [sample-dt] :or {sample-dt 0.5}}]
  (let [violations (vec (concat (separation-violations s :sample-dt sample-dt)
                                 (speed-violations s)
                                 (accel-violations s)
                                 (geofence-violations s)))]
    {:valid? (empty? violations) :violations violations}))
