(ns kotoba.live.stage
  "Stage geometry — the physical layout of the venue.

  A stage is a small bag of zones (`:performer` / `:pit` / `:floor` /
  `:wings` / `:balcony`) plus fixture mount points. Geometry is
  venue-agnostic: plain `[x y z]` vectors so any renderer can place meshes by
  zone. `Y` is up; `-Z` is \"into the audience\".")

(def zones #{:performer :pit :floor :wings :balcony})
(def fixtures #{:front-par :back-par :spot :blinder :laser :strobe})
(def presets #{:club :hall :festival})

(defn zone-box [centre half-size] {:centre centre :half-size half-size})

(defn- abs* [x] (if (neg? x) (- x) x))

(defn box-contains?
  "Is world point `p` inside axis-aligned box `b`?"
  [b p]
  (let [d (mapv (fn [pc bc] (abs* (- pc bc))) p (:centre b))]
    (every? true? (map <= d (:half-size b)))))

(defn zone
  "The `ZoneBox` for `kind`, or `nil`."
  [stage kind]
  (get (:zones stage) kind))

(defn- meter [x y z] [(double x) (double y) (double z)])

(defn build-preset
  "Build a default stage for `preset` (`:club` / `:hall` / `:festival`)."
  [preset]
  (let [[stage-w stage-d _ceil floor-w floor-d pit-d]
        (case preset
          :club [6.0 4.0 4.0 8.0 10.0 4.0]
          :festival [24.0 10.0 14.0 40.0 60.0 20.0]
          [12.0 6.0 8.0 16.0 20.0 8.0]) ;; :hall default
        ceil (case preset :club 4.0 :festival 14.0 8.0)
        stage-y (case preset :club 0.6 :festival 1.8 1.2)
        perf-centre (meter 0.0 stage-y 0.0)
        zones {:performer (zone-box perf-centre (meter (* stage-w 0.5) 0.5 (* stage-d 0.5)))
               :pit (zone-box (meter 0.0 0.0 (- (+ (* pit-d 0.5) (* stage-d 0.5))))
                               (meter (* floor-w 0.5) 1.0 (* pit-d 0.5)))
               :floor (zone-box (meter 0.0 0.0 (- (+ (* floor-d 0.5) (* stage-d 0.5))))
                                 (meter (* floor-w 0.5) 1.0 (* floor-d 0.5)))
               :wings (zone-box (meter (+ (* stage-w 0.5) 1.5) stage-y 0.0)
                                 (meter 2.0 2.5 (* stage-d 0.5)))
               :balcony (zone-box (meter 0.0 (* ceil 0.5) (- (+ floor-d (* stage-d 0.5))))
                                   (meter (* floor-w 0.4) 1.0 4.0))}
        truss-y (- ceil 0.5)
        front-back (for [x [(* stage-w -0.4) 0.0 (* stage-w 0.4)]]
                     [{:fixture :front-par :position (meter x truss-y -0.5)}
                      {:fixture :back-par :position (meter x truss-y (- (* stage-d 0.5) 0.2))}])
        spot [{:fixture :spot :position (meter 0.0 truss-y 0.0)}]
        strobe [{:fixture :strobe :position (meter 0.0 truss-y -1.0)}]
        side (for [x [(* stage-w -0.45) (* stage-w 0.45)]]
               [{:fixture :blinder :position (meter x (+ stage-y 1.2) -0.2)}
                {:fixture :laser :position (meter x (- truss-y 0.3) 0.0)}])
        fixtures-vec (vec (concat (apply concat front-back) spot strobe (apply concat side)))
        led-wall (zone-box (meter 0.0 (+ stage-y 2.5) (+ (* stage-d 0.5) 0.05))
                            (meter (* stage-w 0.45) 2.0 0.05))]
    {:zones zones :fixtures fixtures-vec :led-wall led-wall}))
