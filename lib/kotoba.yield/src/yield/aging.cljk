(ns yield.aging
  "Aging and degradation mechanisms estimation (NBTI, PBTI, HCI, TDDB,
  EM). Restored from kami-yield's `aging` module (deleted PR #82).")

(def aging-mechanisms #{:nbti :pbti :hci :tddb :em})

(defn aging-result [mechanism parameter-name degradation-percent time-years pass]
  {:mechanism mechanism :parameter-name parameter-name :degradation-percent degradation-percent
   :time-years time-years :pass pass})

(def ^:private k-b 8.617e-5) ; Boltzmann constant, eV/K

(defn estimate-aging
  "Estimate aging degradation using Arrhenius-based models. Each
  mechanism has empirical activation energy and voltage acceleration
  factors; the degradation percentage is estimated for the given
  operating conditions and `time-years` duration."
  [mechanism voltage temperature-c time-years]
  (let [temp-k (+ temperature-c 273.15)
        time-hours (* time-years 8766.0)
        [param-name degradation limit]
        (case mechanism
          :nbti (let [ea 0.5 gamma 3.0 n 0.25 a 1e-3
                      deg (* a (Math/exp (/ (- ea) (* k-b temp-k)))
                             (Math/pow voltage gamma) (Math/pow time-hours n) 100.0)]
                  ["Vth_shift" deg 10.0])
          :pbti (let [ea 0.4 gamma 4.0 n 0.2 a 5e-4
                      deg (* a (Math/exp (/ (- ea) (* k-b temp-k)))
                             (Math/pow voltage gamma) (Math/pow time-hours n) 100.0)]
                  ["Vth_shift" deg 10.0])
          :hci (let [ea 0.3 m 5.0 a 2e-4
                     deg (* a (Math/exp (/ (- ea) (* k-b temp-k)))
                            (Math/pow (/ voltage 0.9) m) (Math/sqrt time-hours) 100.0)]
                 ["Idsat_degradation" deg 10.0])
          :tddb (let [ea 0.7 gamma-v 3.5 a 1e-6
                      deg (* a (Math/exp (/ (- ea) (* k-b temp-k)))
                             (Math/exp (* gamma-v voltage)) (Math/pow time-hours 0.3) 100.0)]
                  ["dielectric_integrity" deg 5.0])
          :em (let [ea 0.7 n 2.0 a 1e-8
                    current-density (* voltage 1e6)
                    deg (* a (Math/pow current-density n) (Math/exp (/ (- ea) (* k-b temp-k)))
                           time-hours 100.0)]
                ["metal_void_growth" deg 20.0]))]
    (aging-result mechanism param-name degradation time-years (<= degradation limit))))
