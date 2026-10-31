(ns vehicle.powertrain
  "Powertrain -- Engine + Clutch + Gearbox + Differential + Driveline.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930."
  )

;; ---- TorqueCurve ----

(defn na-2-0-gasoline []
  {:points [[800.0 130.0] [1500.0 160.0] [2500.0 185.0] [3500.0 200.0]
            [4500.0 200.0] [5500.0 185.0] [6500.0 150.0] [7000.0 0.0]]})

(defn turbo-2-0 []
  {:points [[800.0 150.0] [1500.0 280.0] [2500.0 370.0] [3000.0 380.0]
            [4500.0 370.0] [5500.0 320.0] [6500.0 220.0] [7000.0 0.0]]})

(defn torque-curve-lookup [curve rpm]
  (let [pts (:points curve)]
    (if (empty? pts)
      0.0
      (let [[r0 t0] (first pts)
            [rl tl] (last pts)]
        (cond
          (<= rpm r0) t0
          (>= rpm rl) tl
          :else
          (loop [ps pts]
            (if (< (count ps) 2)
              0.0
              (let [[ra ta] (first ps)
                    [rb tb] (second ps)]
                (if (<= rpm rb)
                  (let [f (/ (- rpm ra) (- rb ra))]
                    (+ ta (* (- tb ta) f)))
                  (recur (rest ps)))))))))))

;; ---- Engine ----

(def tau (* 2.0 Math/PI))
(defn rpm->rad [rpm] (/ (* rpm tau) 60.0))
(defn rad->rpm [omega] (/ (* omega 60.0) tau))

(defn new-engine [curve]
  {:torque-curve curve
   :idle-rpm 850.0
   :max-rpm 7000.0
   :inertia 0.18
   :friction 35.0
   :omega (rpm->rad 850.0)
   :running true})

(defn engine-rpm [engine] (rad->rpm (:omega engine)))

(defn- clamp [v lo hi] (min hi (max lo v)))

(defn net-torque [engine throttle]
  (if-not (:running engine)
    (- (min (:friction engine) (* (Math/abs (:omega engine)) 0.05)))
    (let [rpm (engine-rpm engine)
          raw (torque-curve-lookup (:torque-curve engine) rpm)
          cut (if (>= rpm (:max-rpm engine)) 0.0 1.0)
          combustion (* raw (clamp throttle 0.0 1.0) cut)
          idle (if (and (< throttle 0.05) (< rpm (:idle-rpm engine)))
                 (* (/ (- (:idle-rpm engine) rpm) (:idle-rpm engine)) 30.0)
                 0.0)
          friction (* (:friction engine) (clamp (/ rpm (:max-rpm engine)) 0.05 1.5))]
      (+ combustion idle (- friction)))))

;; ---- Clutch ----

(defn new-clutch [max-torque]
  {:engagement 1.0 :max-torque max-torque :slip 0.0})

(defn- copysign [mag sign] (if (neg? sign) (- (Math/abs mag)) (Math/abs mag)))

(defn clutch-transmit
  "Returns `[clutch' transmitted-torque]`."
  [clutch engine-omega gearbox-input-omega requested]
  (let [slip (- engine-omega gearbox-input-omega)
        cap (* (:max-torque clutch) (clamp (:engagement clutch) 0.0 1.0))
        transmitted (if (<= (Math/abs requested) cap) requested (copysign cap requested))]
    [(assoc clutch :slip slip) transmitted]))

;; ---- Gearbox ----

(defn manual-6 []
  {:ratios [3.50 0.0 3.50 1.95 1.30 1.00 0.80 0.65]
   :current-gear 0
   :final-drive 4.10
   :inertia 0.05
   :shift-time 0.35
   :shift-progress 1.0})

(defn gearbox-ratio [gearbox]
  (let [g (:current-gear gearbox)]
    (if (zero? g)
      0.0
      (let [idx (if (neg? g) 0 (inc g))
            ratios (:ratios gearbox)]
        (if (>= idx (count ratios))
          0.0
          (let [sign (if (neg? g) -1.0 1.0)]
            (* sign (nth ratios idx))))))))

(defn gearbox-total-ratio [gearbox]
  (let [r (gearbox-ratio gearbox)]
    (if (zero? r) 0.0 (* r (:final-drive gearbox)))))

(defn shift-to [gearbox gear]
  (if (= gear (:current-gear gearbox))
    gearbox
    (assoc gearbox :current-gear gear :shift-progress 0.0)))

(defn gearbox-tick [gearbox dt]
  (if (< (:shift-progress gearbox) 1.0)
    (update gearbox :shift-progress #(min 1.0 (+ % (/ dt (:shift-time gearbox)))))
    gearbox))

(defn automatic-shift
  "Select a forward gear using RPM and road-speed hysteresis. Requiring both
  high RPM and the current gear's minimum road speed prevents clutch/free-rev
  gear hunting. Shifts only after the previous shift has completed.

  Options: `:speed-kph`, `:up-rpm` (6200), `:down-rpm` (2200), and authored
  `:upshift-kph` / `:downshift-kph` vectors."
  ([gearbox rpm] (automatic-shift gearbox rpm {}))
  ([gearbox rpm {:keys [speed-kph up-rpm down-rpm upshift-kph downshift-kph]
                 :or {speed-kph 0.0 up-rpm 6200.0 down-rpm 2200.0
                      ;; Conservative defaults for the restored soft-body demo:
                      ;; its tire/chassis losses are much higher than a rigid-body car.
                      upshift-kph [8.0 14.0 24.0 38.0 58.0]
                      downshift-kph [6.0 11.0 19.0 31.0 48.0]}}]
   (let [gear (:current-gear gearbox)
         max-forward (- (count (:ratios gearbox)) 2)
         up-speed (nth upshift-kph (max 0 (dec gear)) ##Inf)
         down-speed (nth downshift-kph (max 0 (- gear 2)) 0.0)]
     (if (< (:shift-progress gearbox) 1.0)
       gearbox
       (cond
         (and (>= gear 1) (< gear max-forward)
              (>= rpm up-rpm) (>= speed-kph up-speed))
         (shift-to gearbox (inc gear))

         (and (> gear 1) (or (<= rpm down-rpm) (< speed-kph down-speed)))
         (shift-to gearbox (dec gear))

         :else gearbox)))))

;; ---- Differential ----
;; kind: {:kind :open} | {:kind :locked} | {:kind :lsd :lock-factor f}

(defn diff-open [] {:kind :open})
(defn diff-lsd [lock-factor] {:kind :lsd :lock-factor (clamp lock-factor 0.0 1.0)})

(defn diff-split
  "Returns `[t-left t-right]`."
  [diff total omega-l omega-r]
  (case (:kind diff)
    :open [(* total 0.5) (* total 0.5)]
    :locked (let [mismatch (- omega-r omega-l)
                  clamp-t (* mismatch 50.0)]
              [(+ (* total 0.5) clamp-t) (- (* total 0.5) clamp-t)])
    :lsd (let [mismatch (- omega-r omega-l)
               clamp-t (* mismatch 30.0 (:lock-factor diff))]
           [(+ (* total 0.5) clamp-t) (- (* total 0.5) clamp-t)])))

;; ---- Driveline layout ----
;; {:kind :fwd} | {:kind :rwd} | {:kind :awd :front-split f}

(defn layout-fwd [] {:kind :fwd})
(defn layout-rwd [] {:kind :rwd})
(defn layout-awd [front-split] {:kind :awd :front-split front-split})

;; ---- Powertrain ----

(defn sedan-powertrain []
  {:engine (new-engine (na-2-0-gasoline))
   :clutch (new-clutch 420.0)
   :gearbox (manual-6)
   :front-diff (diff-open)
   :rear-diff (diff-open)
   :layout (layout-fwd)})

(defn distribute
  "wheel-omegas = [[front-l front-r] [rear-l rear-r]].
   Returns [[front-l front-r] [rear-l rear-r]]."
  [powertrain shaft-torque wheel-omegas]
  (let [layout (:layout powertrain)
        [front-share rear-share]
        (case (:kind layout)
          :fwd [1.0 0.0]
          :rwd [0.0 1.0]
          :awd [(:front-split layout) (- 1.0 (:front-split layout))])
        [[fl-omega fr-omega] [rl-omega rr-omega]] wheel-omegas
        front (diff-split (:front-diff powertrain) (* shaft-torque front-share) fl-omega fr-omega)
        rear (diff-split (:rear-diff powertrain) (* shaft-torque rear-share) rl-omega rr-omega)]
    [front rear]))
