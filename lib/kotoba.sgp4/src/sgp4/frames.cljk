(ns sgp4.frames
  "TEME -> ECEF -> geodetic, which is what turns a propagator result into a
  point on a globe.

  ## Two ellipsoids, on purpose

  SGP4 runs on **WGS-72** because that is the fit the TLEs were produced
  against (see `sgp4.core`). The geodetic conversion here uses **WGS-84**
  because that is the datum every map, tile scheme and GNSS receiver is in.

  Mixing them is not a mistake -- it is the correct pair. `sgp4.core`
  returns a *physical position in an inertial frame*, in kilometres; the
  ellipsoid used to fit the orbit does not travel with that position.
  Re-using WGS-72 here would put the sub-satellite point about 100 m off
  from where every basemap says it is.

  ## What is deliberately not modelled

  Polar motion (TEME/PEF -> ITRF, `x_p`/`y_p`) is skipped. It displaces a
  ground point by under 15 m. A TLE's own along-track error is a kilometre
  at epoch and grows; correcting 15 m under that is false precision, and it
  would make this namespace need an Earth-orientation feed it otherwise
  does not.

  This is a statement about magnitudes, not an apology: if a caller ever
  needs metre-level ground truth, SGP4 is the wrong propagator, not this
  the wrong rotation."
  (:require [sgp4.time :as t]))

(def ^{:doc "WGS-84 semi-major axis, km."} wgs84-a 6378.137)
(def ^{:doc "WGS-84 flattening."} wgs84-f (/ 1.0 298.257223563))
(def ^{:doc "WGS-84 first eccentricity squared, f(2-f)."}
  wgs84-e2 (* wgs84-f (- 2.0 wgs84-f)))

(def ^{:doc "Earth rotation rate, rad/s (IERS nominal mean sidereal)."}
  omega-earth 7.292115146706979e-5)

(def rad->deg (/ 180.0 Math/PI))
(def deg->rad (/ Math/PI 180.0))

(defn teme->ecef
  "Rotate a TEME position (and optionally velocity) into an Earth-fixed
  frame, given Greenwich Mean Sidereal Time `gmst` in radians.

  The velocity gets the transport term `-omega x r`; without it a
  ground-relative speed is wrong by up to 0.46 km/s at the equator, which
  is a third of an ISS ground track."
  ([r gmst] (:r (teme->ecef r nil gmst)))
  ([[x y z] v gmst]
   (let [c (Math/cos gmst) s (Math/sin gmst)
         xe (+ (* c x) (* s y))
         ye (+ (* (- s) x) (* c y))]
     (cond-> {:r [xe ye z]}
       v (assoc :v (let [[vx vy vz] v
                         vxe (+ (* c vx) (* s vy))
                         vye (+ (* (- s) vx) (* c vy))]
                     [(+ vxe (* omega-earth ye))
                      (- vye (* omega-earth xe))
                      vz]))))))

(defn ecef->geodetic
  "ECEF kilometres -> `{:lat-deg :lon-deg :alt-km}` on WGS-84.

  Bowring-style fixed point on the reduced latitude, iterated to
  convergence rather than to a fixed count: near the poles the first-order
  form needs more steps than it does at the equator, and a hard-coded four
  iterations is the kind of constant that is right on the test case and
  wrong on the orbit.

  The polar singularity (`r == 0`, i.e. exactly on the spin axis) is a real
  point, not an error: latitude is +/-90 and longitude is undefined. It is
  reported as longitude 0 rather than NaN, because a NaN here propagates
  into a renderer and disappears."
  [[x y z]]
  (let [r (Math/sqrt (+ (* x x) (* y y)))
        lon (if (and (zero? r) (zero? y) (zero? x)) 0.0 (Math/atan2 y x))]
    (if (< r 1.0e-12)
      {:lat-deg (if (neg? z) -90.0 90.0)
       :lon-deg 0.0
       :alt-km (- (Math/abs z) (* wgs84-a (- 1.0 wgs84-f)))}
      (loop [lat (Math/atan2 z (* r (- 1.0 wgs84-e2)))
             n 0]
        (let [sl (Math/sin lat)
              nn (/ wgs84-a (Math/sqrt (- 1.0 (* wgs84-e2 sl sl))))
              alt (- (/ r (Math/cos lat)) nn)
              lat' (Math/atan2 z (* r (- 1.0 (* wgs84-e2 (/ nn (+ nn alt))))))]
          (if (or (< (Math/abs (- lat' lat)) 1.0e-13) (>= n 20))
            (let [sl (Math/sin lat')
                  nn (/ wgs84-a (Math/sqrt (- 1.0 (* wgs84-e2 sl sl))))]
              {:lat-deg (* lat' rad->deg)
               :lon-deg (* lon rad->deg)
               ;; Away from the poles `r/cos(lat)` is stable; within a
               ;; degree of them it is not, so the |z| form takes over.
               :alt-km (if (> (Math/abs (Math/cos lat')) 0.017)
                         (- (/ r (Math/cos lat')) nn)
                         (- (/ (Math/abs z) (Math/abs (Math/sin lat')))
                            (* nn (- 1.0 wgs84-e2))))})
            (recur lat' (inc n))))))))

(defn geodetic->ecef
  "`{:lat-deg :lon-deg :alt-km}` -> ECEF km. The exact inverse of
  `ecef->geodetic`, and the reason the round trip is testable."
  [{:keys [lat-deg lon-deg alt-km]}]
  (let [lat (* lat-deg deg->rad) lon (* lon-deg deg->rad)
        sl (Math/sin lat) cl (Math/cos lat)
        n (/ wgs84-a (Math/sqrt (- 1.0 (* wgs84-e2 sl sl))))]
    [(* (+ n (or alt-km 0.0)) cl (Math/cos lon))
     (* (+ n (or alt-km 0.0)) cl (Math/sin lon))
     (* (+ (* n (- 1.0 wgs84-e2)) (or alt-km 0.0)) sl)]))

(defn subpoint
  "The full chain: a `sgp4.core/propagate` result plus the Julian date it
  was propagated to, into `{:lat-deg :lon-deg :alt-km :speed-km-s}`.

  `jd`/`frac` must be the *absolute* date, not `tsince` -- GMST is a
  function of the clock, not of time since epoch. Passing epoch here and
  propagating hours ahead is the mistake this signature is shaped to make
  hard: there is nowhere to put a `tsince`."
  [{:keys [r v]} jd frac]
  (let [gmst (t/gstime (+ jd frac))
        {re :r ve :v} (teme->ecef r v gmst)]
    (assoc (ecef->geodetic re)
           :ecef-km re
           :speed-km-s (when ve (Math/sqrt (reduce + (map * ve ve)))))))
