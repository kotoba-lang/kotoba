(ns vehicle.ground
  "Ground contact resolution.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930.

   `Ground` is a Rust trait implemented by `FlatGround`, `ClosureGround`, and
   `MapGround`. Here it becomes a plain protocol-free convention: any
   ground value is a map with a `:sample-fn` of `(fn [ground x z] -> sample)`,
   dispatched via `ground-sample`."
  (:require [vehicle.vec3 :as v3]))

;; ---- SurfaceKind ----

(def surface-ids
  {:asphalt-dry "asphalt_dry" :asphalt-wet "asphalt_wet" :gravel "gravel"
   :sand "sand" :snow "snow" :ice "ice" :mud "mud" :grass "grass"})

(defn surface-id [k] (get surface-ids k))

(defn surface-from-id [s]
  (case s
    "asphalt_wet" :asphalt-wet
    "gravel" :gravel
    "sand" :sand
    "snow" :snow
    "ice" :ice
    "mud" :mud
    "grass" :grass
    :asphalt-dry))

(def surface-display-names
  {:asphalt-dry "Dry Asphalt" :asphalt-wet "Wet Asphalt" :gravel "Gravel"
   :sand "Sand" :snow "Snow" :ice "Ice" :mud "Mud" :grass "Grass"})

(defn surface-display-name [k] (get surface-display-names k))

(def surface-coefficients
  ;; [friction_mu grip_modifier]
  {:asphalt-dry [1.00 1.00]
   :asphalt-wet [0.70 0.70]
   :gravel [0.55 0.55]
   :sand [0.40 0.45]
   :snow [0.30 0.35]
   :ice [0.10 0.10]
   :mud [0.35 0.40]
   :grass [0.55 0.60]})

(defn surface-coeffs [k] (get surface-coefficients k))

(def surface-tints
  {:asphalt-dry [0.20 0.20 0.22]
   :asphalt-wet [0.16 0.18 0.24]
   :gravel [0.45 0.42 0.38]
   :sand [0.85 0.75 0.55]
   :snow [0.95 0.95 0.98]
   :ice [0.75 0.85 0.95]
   :mud [0.30 0.22 0.15]
   :grass [0.30 0.55 0.25]})

(defn surface-tint [k] (get surface-tints k))

;; ---- GroundSample ----
;; {:normal v3 :height f :friction-mu f :grip-modifier f}

;; ---- Ground dispatch ----

(defn ground-sample [ground x z]
  ((:sample-fn ground) ground x z))

;; ---- FlatGround ----

(defn flat-ground
  ([height] (flat-ground height :asphalt-dry))
  ([height surface]
   (let [[mu grip] (surface-coeffs surface)]
     {:kind :flat
      :height height
      :friction-mu mu
      :grip-modifier grip
      :surface surface
      :sample-fn (fn [g _x _z]
                    {:normal v3/unit-y :height (:height g)
                     :friction-mu (:friction-mu g) :grip-modifier (:grip-modifier g)})})))

;; ---- ClosureGround ----

(defn closure-ground [f]
  {:kind :closure :f f :sample-fn (fn [g x z] ((:f g) x z))})

;; ---- MapGround ----

(defn surface-zone [x-min x-max z-min z-max surface]
  {:x-min x-min :x-max x-max :z-min z-min :z-max z-max :surface surface})

(defn demo-circuit []
  {:default :grass
   :zones
   [(surface-zone -4.0 4.0 -100.0 100.0 :asphalt-dry)
    (surface-zone -4.0 4.0 8.0 20.0 :asphalt-wet)
    (surface-zone -4.0 4.0 30.0 42.0 :ice)
    (surface-zone -4.0 4.0 55.0 75.0 :snow)
    (surface-zone 8.0 30.0 -20.0 20.0 :sand)
    (surface-zone 8.0 30.0 25.0 60.0 :gravel)
    (surface-zone -30.0 -8.0 -20.0 20.0 :mud)
    (surface-zone -30.0 -8.0 25.0 60.0 :snow)
    (surface-zone -4.0 4.0 -45.0 -30.0 :mud)]})

(defn surface-at [map-ground x z]
  (or (some (fn [zone]
              (when (and (>= x (:x-min zone)) (<= x (:x-max zone))
                         (>= z (:z-min zone)) (<= z (:z-max zone)))
                (:surface zone)))
            (:zones map-ground))
      (:default map-ground)))

(defn map-ground [demo]
  (assoc demo
         :kind :map
         :sample-fn (fn [g x z]
                       (let [surface (surface-at g x z)
                             [mu grip] (surface-coeffs surface)]
                         {:normal v3/unit-y :height 0.0
                          :friction-mu mu :grip-modifier grip}))))

(defn map-ground-demo-circuit [] (map-ground (demo-circuit)))
