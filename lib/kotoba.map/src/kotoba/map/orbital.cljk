(ns kotoba.map.orbital
  "Orbital / celestial scene-scale math for the Cosmic projection mode.

  Ported 1:1 from the free functions at the bottom of `kami-map/src/lib.rs`
  (Rust, kotoba-lang/kami-engine), per ADR-2607010930 (clj-wgsl migration
  Phase 4): `scene_cislunar_orbit_radius`, `scene_solar_orbit_radius`,
  `orbital_phase_angle`, `orbital_scene_position`, `equatorial_anchor`,
  `display_body_radius`. Pure math — no GPU calls, no I/O.

  NOT ported: `tle_scene_position_from_cache` / `KamiMap::tle_scene_position`
  (SGP4 TLE orbit propagation) — depends on the external `sgp4` crate's
  numerical propagator, out of scope for this domain-logic port. See the
  map repo README."
  (:require [kotoba.map.constants :as k]))

(defn scene-cislunar-orbit-radius
  "Scene-scale render radius for a cislunar-distance orbit, compressing the
  huge real semi-major-axis range into a visually usable scale around
  `globe-radius`."
  [semi-major-axis-m]
  (let [ratio (max 1.0 (/ semi-major-axis-m k/earth-radius-m))]
    (* k/globe-radius 0.95 (Math/pow ratio 0.25))))

(defn scene-solar-orbit-radius
  "Scene-scale render radius for a solar-system-distance orbit, relative to
  `earth-axis-m` (1 AU) mapped onto `solar-radius`."
  [semi-major-axis-m earth-axis-m solar-radius]
  (let [au-ratio (max 0.05 (/ semi-major-axis-m (max 1.0 earth-axis-m)))]
    (* solar-radius (Math/pow au-ratio (/ 1.0 3.0)))))

(defn orbital-phase-angle
  "Current orbital phase angle (radians) for a body with `period-s` orbital
  period and `mean-longitude-deg` epoch mean longitude, at time `now-s`.
  Bodies with `period-s <= 1.0` (unspecified period) are treated as
  stationary at their mean longitude."
  [period-s mean-longitude-deg now-s]
  (let [phase (if (> period-s 1.0)
                (/ (* now-s 2.0 Math/PI) period-s)
                0.0)]
    (+ (k/to-radians mean-longitude-deg) phase)))

(defn orbital-scene-position
  "3D scene position (`[x y z]`) on a Keplerian-ish ellipse of semi-major
  `radius`, `eccentricity` (clamped `[0, 0.98]`), `inclination-deg` tilt,
  at orbital `phase` (radians)."
  [radius eccentricity inclination-deg phase]
  (let [e (max 0.0 (min 0.98 eccentricity))
        r (/ (* radius (- 1.0 (* e e)))
             (max 0.2 (+ 1.0 (* e (Math/cos phase)))))
        incl (k/to-radians inclination-deg)]
    [(* r (Math/cos phase))
     (* r (Math/sin phase) (Math/sin incl))
     (* r (Math/sin phase) (Math/cos incl))]))

(defn equatorial-anchor
  "3D position at `radius` for an equatorial-coordinate `ra-deg`/`dec-deg`
  (right ascension / declination) anchor — e.g. a star/deep-sky-object
  placement on the celestial sphere."
  [ra-deg dec-deg radius]
  (let [ra (k/to-radians ra-deg)
        dec (k/to-radians dec-deg)]
    [(* radius (Math/cos dec) (Math/cos ra))
     (* radius (Math/sin dec))
     (* radius (Math/cos dec) (Math/sin ra))]))

(defn display-body-radius
  "Visually-compressed display radius for an orbital body, clamped to
  `[min-radius, max-radius]`. `body` is a map possibly containing
  `:render-radius-m` and `:body-kind`; `body-id` `\"orbital-body:sun\"` and
  `:body-kind \"station\"` get bespoke compression curves, matching the
  Rust source's special-cases."
  [body body-id fallback min-radius max-radius]
  (if-let [radius-m (:render-radius-m body)]
    (let [ratio (max 0.00001 (/ radius-m k/earth-radius-m))
          compressed (cond
                       (= body-id "orbital-body:sun")
                       (* k/globe-radius 0.18 (Math/pow ratio 0.18))

                       (= (:body-kind body) "station")
                       (max min-radius fallback)

                       :else
                       (* k/globe-radius (Math/pow ratio 0.35)))]
      (max min-radius (min max-radius compressed)))
    fallback))
