(ns motor.bldc
  "Small BLDC motor sizing (:rom-bldc), CALIBRATED against published motors
  rather than extrapolated.

  `motor.solver` sizes a traction motor from air-gap shear. Applied to a
  multirotor it is being asked about machines two orders of magnitude smaller
  than anything it was written for, and it does not say so. Measured 2026-08-30
  against T-MOTOR's own published figures, it returns 114 g for a motor that
  really weighs about 82 g — it is roughly 40% HEAVY at drone scale, not light.

  So this namespace does not model a motor. It fits one number from motors that
  exist:

      mass_g = a * P_W^b     fitted in log space over `reference-motors`

  The fit is derived from the table at call time, not baked in as a literal, so
  adding a motor to the table changes the answer and no constant can drift away
  from the data it came from.

  `:power-basis` is the manufacturer's short-burst rating (180 s), which is the
  right basis for sizing to PEAK thrust and the wrong one for continuous cruise.
  A caller sizing for continuous duty is using the wrong number here.

  What this does NOT capture: KV. Motor mass tracks torque more closely than
  power, and torque is power over speed, so two motors of equal power and
  different KV are not the same machine. The table spans KV 100-400 and the fit
  averages over that, which is a real part of the residual below. Pinning it
  down needs rpm at max power, which these datasheets do not state."
  (:require [datom.core :as d]
            [cae.solver :as cae]))

(def reference-motors
  "Published figures, retrieved 2026-08-30 from T-MOTOR's own store pages.
  Mass is INCLUDING cable except where the vendor gave only one figure; power is
  the vendor's `max power / 180 s` rating.

  Catalogue data, not measurement by us. Two families are mixed on purpose —
  restricting to one would fit better and describe less."
  [{:model "MN2806" :kv 400 :mass-g 46.0  :max-power-W 216.0  :max-thrust-kg 1.1
    :family :antigravity
    :source "https://store.tmotor.com/product/mn2806-motor-antigravity-type.html"}
   {:model "MN4006" :kv 380 :mass-g 68.0  :max-power-W 380.0  :max-thrust-kg 2.309
    :family :antigravity
    :source "https://store.tmotor.com/product/mn4006-kv380-motor-antigravity-type.html"}
   {:model "MN5208" :kv 340 :mass-g 196.0 :max-power-W 850.0  :max-thrust-kg 4.125
    :family :navigator
    :source "https://store.tmotor.com/product/mn5208-motor-navigator-type.html"}
   {:model "MN8012" :kv 100 :mass-g 351.0 :max-power-W 1873.0 :max-thrust-kg 11.8
    :family :antigravity
    :source "https://store.tmotor.com/product/mn8012-motor-antigravity-type.html"}
   {:model "MN8017" :kv 120 :mass-g 453.0 :max-power-W 3180.0 :max-thrust-kg 16.8
    :family :antigravity
    :source "https://store.tmotor.com/product/mn8017-motor-antigravity-type.html"}])

(defn fit
  "Least-squares fit of log(mass_g) on log(P_W) over `motors`. Returns
  {:a :b :r2 :worst-residual :n :domain-W}. Refuses fewer than three motors —
  two points fit any power law exactly and report nothing about the fit."
  ([] (fit reference-motors))
  ([motors]
   (when (< (count motors) 3)
     (throw (ex-info "a power-law fit needs at least three motors"
                     {:n (count motors)})))
   (let [xs (mapv #(Math/log (:max-power-W %)) motors)
         ys (mapv #(Math/log (:mass-g %)) motors)
         n  (count xs)
         mx (/ (reduce + xs) n)
         my (/ (reduce + ys) n)
         sxy (reduce + (map (fn [x y] (* (- x mx) (- y my))) xs ys))
         sxx (reduce + (map (fn [x] (let [d (- x mx)] (* d d))) xs))
         b  (/ sxy sxx)
         a  (Math/exp (- my (* b mx)))
         pred (fn [p] (* a (Math/pow p b)))
         ssr (reduce + (map (fn [m] (let [e (- (Math/log (:mass-g m))
                                               (Math/log (pred (:max-power-W m))))]
                                      (* e e)))
                            motors))
         sst (reduce + (map (fn [y] (let [d (- y my)] (* d d))) ys))
         worst (reduce max (map (fn [m] (Math/abs (/ (- (pred (:max-power-W m))
                                                        (:mass-g m))
                                                     (:mass-g m))))
                                motors))]
     {:a a :b b :r2 (- 1.0 (/ ssr sst)) :worst-residual worst :n n
      :domain-W [(reduce min (map :max-power-W motors))
                 (reduce max (map :max-power-W motors))]})))

(defn solve
  "Mass of a small BLDC motor for `:p-peak-W` of ELECTRICAL input at peak.

  Reports `:extrapolated?` when the request is outside the fitted domain rather
  than returning a number that looks the same as an interpolated one, and
  carries `:worst-residual` so the caller sees the error bar the data supports
  instead of inventing confidence."
  [{:keys [p-peak-W motors] :or {motors reference-motors} :as case}]
  (when-not (and (number? p-peak-W) (pos? p-peak-W))
    (throw (ex-info "bldc solve needs a positive peak power"
                    {:key :p-peak-W :value p-peak-W})))
  (let [{:keys [a b r2 worst-residual n domain-W]} (fit motors)
        [lo hi] domain-W
        mass-g (* a (Math/pow p-peak-W b))]
    {:p-peak-W p-peak-W
     :mass-kg (/ mass-g 1000.0) :mass-g mass-g
     :W-per-g (/ p-peak-W mass-g)
     :fit {:a a :b b :r2 r2 :n n :domain-W domain-W}
     :worst-residual worst-residual
     :extrapolated? (or (< p-peak-W lo) (> p-peak-W hi))
     :power-basis :vendor-max-180s
     :solver :rom-bldc
     :case-id (:case/id case)}))

(defmethod cae/solve :rom-bldc [case] (solve case))

(defn run
  [case]
  (let [r   (solve case)
        cid (or (:case/id case) "bldc-0")
        ent (d/entity "motor" :BldcRun cid
                      {:peakW  (Math/round (double (:p-peak-W r)))
                       :massG  (Math/round (double (:mass-g r)))
                       :WperG  (Math/round (* 100.0 (:W-per-g r)))
                       :extrap (if (:extrapolated? r) 1 0)})
        led (d/log [ent])]
    (assoc r :datoms (:datoms led) :datom-count (:count led))))
