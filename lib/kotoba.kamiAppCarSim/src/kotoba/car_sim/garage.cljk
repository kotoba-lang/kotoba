(ns kotoba.car-sim.garage
  "Vehicle garage — preset library of buildable vehicles, ported from
  `kami-app-car-sim`'s public demo and the shared
  `kami-vehicle-scene/data/garage.edn` CONFIG (ADR-2607010000).

  Scope: this namespace owns the DATA-DRIVEN assembly/config-selection
  layer only — the 6 garage vehicle specs, the engine/gearbox/tire preset
  tables, and `spec-for` (id -> fully-resolved spec with per-kind
  overrides applied, the pure counterpart of Rust `garage::build_from_edn`
  / `garage::build`). It does NOT generate the soft-body node/beam mesh or
  run Pacejka/powertrain solver math — that is core vehicle physics and
  belongs to the separate, now-restored `kotoba-lang/kami-vehicle` CLJC physics repo;
  a resolved spec from `spec-for` is exactly the input that crate/repo
  would need to instantiate a real `Vehicle`.

  Pure data in, pure data out: no network, no I/O. Portable across
  JVM / ClojureScript / SCI / GraalVM."
  (:require [kotoba.lang.text :as str]))

;; ── Engines ─────────────────────────────────────────────────────────────────
;; id -> {:idle-rpm .. :max-rpm .. :inertia .. :friction .. :torque-curve [[rpm nm] ..]}

(def engines
  {:na-2-0-gasoline
   {:idle-rpm 850.0 :max-rpm 7000.0 :inertia 0.18 :friction 35.0
    :torque-curve [[800.0 130.0] [1500.0 160.0] [2500.0 185.0] [3500.0 200.0]
                   [4500.0 200.0] [5500.0 185.0] [6500.0 150.0] [7000.0 0.0]]}
   :turbo-2-0
   {:idle-rpm 850.0 :max-rpm 7000.0 :inertia 0.18 :friction 35.0
    :torque-curve [[800.0 150.0] [1500.0 280.0] [2500.0 370.0] [3000.0 380.0]
                   [4500.0 370.0] [5500.0 320.0] [6500.0 220.0] [7000.0 0.0]]}
   :pickup-v6
   {:idle-rpm 850.0 :max-rpm 6000.0 :inertia 0.18 :friction 35.0
    :torque-curve [[800.0 280.0] [1500.0 380.0] [2500.0 480.0] [3500.0 470.0]
                   [4500.0 380.0] [5500.0 250.0] [6000.0 0.0]]}
   :bus-diesel
   {:idle-rpm 850.0 :max-rpm 3600.0 :inertia 0.18 :friction 35.0
    :torque-curve [[600.0 600.0] [1200.0 1100.0] [1800.0 1200.0] [2400.0 1100.0]
                   [3000.0 800.0] [3600.0 0.0]]}})

;; ── Gearboxes ───────────────────────────────────────────────────────────────

(def gearboxes
  {:manual-6
   {:ratios [3.50 0.0 3.50 1.95 1.30 1.00 0.80 0.65]
    :final-drive 4.10 :inertia 0.05 :shift-time 0.35}})

;; ── Tires (Pacejka magic-formula presets) ────────────────────────────────────

(def tires
  {:road-dry
   {:b-long 10.0 :c-long 1.65 :d-long 1.0  :e-long 0.97
    :b-lat   8.5 :c-lat  1.30 :d-lat  1.0  :e-lat  0.97}
   :road-wet
   {:b-long  8.0 :c-long 1.65 :d-long 0.70 :e-long 0.95
    :b-lat   7.0 :c-lat  1.30 :d-lat  0.70 :e-lat  0.95}})

;; ── Garage: 6 vehicle specs ──────────────────────────────────────────────────
;; :max-rpm 0.0 / absent = "keep the engine preset's own max_rpm" (sentinel,
;; mirrors the Rust EDN authoring convention). :tire-d-long/:tire-d-lat are
;; per-kind sticky-tire overrides (sports only).

(def garage
  {:sedan
   {:display-name "Sedan (4-door, FWD, 2.0L NA)"
    :wheelbase 2.70 :track-width 1.55 :ride-height 0.55 :roof-height 1.00
    :overhang-front 0.95 :overhang-rear 1.10
    :mass-chassis 820.0 :mass-engine 260.0 :mass-cabin 540.0
    :wheel-radius 0.32 :wheel-width 0.22
    :layout :fwd :turbo false
    :engine :na-2-0-gasoline :gearbox :manual-6 :final-drive 4.10 :diff :open
    :tire :road-dry}

   :hatchback
   {:display-name "Hatchback (compact, FWD, 1.5L)"
    :wheelbase 2.45 :track-width 1.50 :ride-height 0.50 :roof-height 1.05
    :overhang-front 0.85 :overhang-rear 0.55
    :mass-chassis 700.0 :mass-engine 180.0 :mass-cabin 420.0
    :wheel-radius 0.30 :wheel-width 0.20
    :layout :fwd :turbo false
    :engine :na-2-0-gasoline :gearbox :manual-6 :final-drive 4.30 :diff :open
    :tire :road-dry :max-rpm 6800.0}

   :suv
   {:display-name "SUV (tall, AWD, turbo 2.0L)"
    :wheelbase 2.85 :track-width 1.65 :ride-height 0.65 :roof-height 1.15
    :overhang-front 1.00 :overhang-rear 1.05
    :mass-chassis 1100.0 :mass-engine 300.0 :mass-cabin 700.0
    :wheel-radius 0.36 :wheel-width 0.25
    :layout {:awd {:front-split 0.45}} :turbo true
    :engine :turbo-2-0 :gearbox :manual-6 :final-drive 4.50 :diff :open
    :tire :road-dry}

   :sports
   {:display-name "Sports (low, RWD, turbo 2.0L)"
    :wheelbase 2.55 :track-width 1.62 :ride-height 0.42 :roof-height 0.85
    :overhang-front 0.85 :overhang-rear 0.85
    :mass-chassis 720.0 :mass-engine 240.0 :mass-cabin 380.0
    :wheel-radius 0.34 :wheel-width 0.26
    :layout :rwd :turbo true
    :engine :turbo-2-0 :gearbox :manual-6 :final-drive 3.85 :diff :open
    :tire :road-dry :max-rpm 7800.0 :tire-d-long 1.20 :tire-d-lat 1.20}

   :pickup
   {:display-name "Pickup (long, RWD, V6)"
    :wheelbase 3.20 :track-width 1.70 :ride-height 0.60 :roof-height 1.20
    :overhang-front 1.00 :overhang-rear 1.30
    :mass-chassis 1200.0 :mass-engine 320.0 :mass-cabin 480.0
    :wheel-radius 0.38 :wheel-width 0.27
    :layout :rwd :turbo false
    :engine :pickup-v6 :gearbox :manual-6 :final-drive 4.80 :diff :open
    :tire :road-dry}

   :bus
   {:display-name "Bus (heavy, RWD, diesel)"
    :wheelbase 4.50 :track-width 1.90 :ride-height 0.60 :roof-height 2.40
    :overhang-front 0.80 :overhang-rear 1.50
    :mass-chassis 1900.0 :mass-engine 480.0 :mass-cabin 1200.0
    :wheel-radius 0.42 :wheel-width 0.30
    :layout :rwd :turbo false
    :engine :bus-diesel :gearbox :manual-6 :final-drive 5.50 :diff :open
    :tire :road-dry}})

(def vehicle-kinds
  "All 6 garage vehicle kinds, in `garage.rs::ALL_VEHICLE_KINDS` order."
  [:sedan :hatchback :suv :sports :pickup :bus])

(defn vehicle-kind
  "Resolve any of a keyword, hyphenated string, or underscored string to a
  canonical vehicle-kind keyword. Unknown ids fall back to `:sedan`
  (mirrors Rust `VehicleKind::from_id`)."
  [id]
  (let [kw (cond
             (keyword? id) id
             (string? id) (keyword (str/replace id "_" "-"))
             :else nil)]
    (if (contains? garage kw) kw :sedan)))

(defn display-name [kind] (:display-name (get garage (vehicle-kind kind))))

(defn spec-for
  "Resolve garage vehicle `kind` (any id form accepted by `vehicle-kind`)
  into a fully-applied spec: the base `garage` entry merged with its
  resolved `:engine`/`:gearbox`/`:tire` preset tables and per-kind
  overrides — the pure counterpart of Rust `garage::build_from_spec` minus
  the actual soft-body/Pacejka instantiation (out of scope here; hand this
  map to a `kami-vehicle`-equivalent physics builder).

  Effective-value resolution mirrors `build_from_spec` exactly:
    * `:effective-max-rpm` = spec `:max-rpm` when authored (non-zero/non-nil),
      else the engine preset's own `:max-rpm`.
    * `:tire` is the base preset merged with `:tire-d-long`/`:tire-d-lat`
      overrides applied only when authored (sports only)."
  [kind]
  (let [k (vehicle-kind kind)
        spec (get garage k)
        engine (get engines (:engine spec))
        gearbox (get gearboxes (:gearbox spec))
        base-tire (get tires (:tire spec))
        max-rpm (:max-rpm spec)
        effective-max-rpm (if (and max-rpm (pos? max-rpm)) max-rpm (:max-rpm engine))
        effective-tire (cond-> base-tire
                          (:tire-d-long spec) (assoc :d-long (:tire-d-long spec))
                          (:tire-d-lat spec) (assoc :d-lat (:tire-d-lat spec)))]
    (assoc spec
           :kind k
           :engine-spec (assoc engine :torque-curve (:torque-curve engine))
           :gearbox-spec (assoc gearbox :final-drive (:final-drive spec))
           :tire-spec effective-tire
           :effective-max-rpm effective-max-rpm)))
