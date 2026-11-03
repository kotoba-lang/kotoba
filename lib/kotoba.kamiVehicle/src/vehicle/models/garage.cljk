(ns vehicle.models.garage
  "Vehicle garage -- preset library of buildable vehicles.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930."
  (:require [vehicle.powertrain :as pt]
            [vehicle.vehicle :as veh]
            [vehicle.wheel :as wheel]
            [vehicle.models.sedan :as sedan]))

;; VehicleKind: :sedan | :hatchback | :suv | :sports | :pickup | :bus

(def kind-ids
  {:sedan "sedan" :hatchback "hatchback" :suv "suv" :sports "sports"
   :pickup "pickup" :bus "bus"})

(defn kind-id [k] (get kind-ids k))

(defn kind-from-id [s]
  (case s
    "hatchback" :hatchback
    "suv" :suv
    "sports" :sports
    "pickup" :pickup
    "bus" :bus
    :sedan))

(def kind-display-names
  {:sedan "Sedan (4-door, FWD, 2.0L NA)"
   :hatchback "Hatchback (compact, FWD, 1.5L)"
   :suv "SUV (tall, AWD, turbo 2.0L)"
   :sports "Sports (low, RWD, turbo 2.0L)"
   :pickup "Pickup (long, RWD, V6)"
   :bus "Bus (heavy, RWD, diesel)"})

(defn kind-display-name [k] (get kind-display-names k))

(defn kind-spec [k]
  (case k
    :sedan (sedan/default-spec)
    :hatchback {:wheelbase 2.45 :track-width 1.50 :ride-height 0.50 :roof-height 1.05
                :overhang-front 0.85 :overhang-rear 0.55
                :mass-chassis 700.0 :mass-engine 180.0 :mass-cabin 420.0
                :wheel-radius 0.30 :wheel-width 0.20 :layout (pt/layout-fwd) :turbo false}
    :suv {:wheelbase 2.85 :track-width 1.65 :ride-height 0.65 :roof-height 1.15
          :overhang-front 1.00 :overhang-rear 1.05
          :mass-chassis 1100.0 :mass-engine 300.0 :mass-cabin 700.0
          :wheel-radius 0.36 :wheel-width 0.25 :layout (pt/layout-awd 0.45) :turbo true}
    :sports {:wheelbase 2.55 :track-width 1.62 :ride-height 0.42 :roof-height 0.85
             :overhang-front 0.85 :overhang-rear 0.85
             :mass-chassis 720.0 :mass-engine 240.0 :mass-cabin 380.0
             :wheel-radius 0.34 :wheel-width 0.26 :layout (pt/layout-rwd) :turbo true}
    :pickup {:wheelbase 3.20 :track-width 1.70 :ride-height 0.60 :roof-height 1.20
             :overhang-front 1.00 :overhang-rear 1.30
             :mass-chassis 1200.0 :mass-engine 320.0 :mass-cabin 480.0
             :wheel-radius 0.38 :wheel-width 0.27 :layout (pt/layout-rwd) :turbo false}
    :bus {:wheelbase 4.50 :track-width 1.90 :ride-height 0.60 :roof-height 2.40
          :overhang-front 0.80 :overhang-rear 1.50
          :mass-chassis 1900.0 :mass-engine 480.0 :mass-cabin 1200.0
          :wheel-radius 0.42 :wheel-width 0.30 :layout (pt/layout-rwd) :turbo false}))

(defn build [kind]
  (let [v (sedan/sedan (kind-spec kind))
        v (assoc v :name (kind-id kind))
        v (veh/enable-rigid-chassis v)]
    (case kind
      :sports
      (let [v (-> v
                  (assoc-in [:powertrain :engine :torque-curve] (pt/turbo-2-0))
                  (assoc-in [:powertrain :engine :max-rpm] 7800.0)
                  (assoc-in [:powertrain :gearbox :final-drive] 3.85))]
        (update v :wheels
                (fn [ws] (mapv (fn [w] (assoc w :tire (assoc (wheel/pacejka-road-dry) :d-long 1.20 :d-lat 1.20))) ws))))

      :suv
      (-> v
          (assoc-in [:powertrain :engine :torque-curve] (pt/turbo-2-0))
          (assoc-in [:powertrain :gearbox :final-drive] 4.50))

      :hatchback
      (-> v
          (assoc-in [:powertrain :engine :max-rpm] 6800.0)
          (assoc-in [:powertrain :gearbox :final-drive] 4.30))

      :pickup
      (-> v
          (assoc-in [:powertrain :engine :torque-curve]
                     {:points [[800.0 280.0] [1500.0 380.0] [2500.0 480.0] [3500.0 470.0]
                               [4500.0 380.0] [5500.0 250.0] [6000.0 0.0]]})
          (assoc-in [:powertrain :engine :max-rpm] 6000.0)
          (assoc-in [:powertrain :gearbox :final-drive] 4.80))

      :bus
      (-> v
          (assoc-in [:powertrain :engine :torque-curve]
                     {:points [[600.0 600.0] [1200.0 1100.0] [1800.0 1200.0] [2400.0 1100.0]
                               [3000.0 800.0] [3600.0 0.0]]})
          (assoc-in [:powertrain :engine :max-rpm] 3600.0)
          (assoc-in [:powertrain :gearbox :final-drive] 5.50))

      v)))
