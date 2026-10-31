(ns motor.envelope
  "Torque–speed envelope on top of a `motor.solver` sized motor (:rom-motor-envelope).

  `motor.solver` answers one question at one speed: how much torque does this
  rotor deliver at `:rpm-base`? A vehicle energy-flow plane needs the answer at
  every speed the drive will visit — the ESC/motor pair works constant-torque
  up to base speed and constant-power (field-weakening) above it.

  Above base speed this contract uses ONLY the mechanical identity P = T·ω,
  so torque above base is exactly T0·(ω_base/ω) for the SAME peak power. That
  is a definition, not a measured magnet/inductance model — real field
  weakening gives LESS than ideal constant power as speed rises, and this
  contract does not pretend to know how much less. `:weakening-eff-unmodeled?`
  is carried on every above-base point so a downstream consumer cannot mistake
  the ideal line for a calibrated one.

  `:rpm-max` is REQUIRED from the caller. Rotor burst speed is a mechanical
  limit of the actual rotor/bandaging design; nothing in this library measures
  it, so there is no default to invent. Below base speed the torque is the
  sized torque (thermal limits are not modeled)."
  (:require [datom.core :as d]
            [cae.solver :as cae]
            [motor.solver :as solver]))

(def ^:const two-pi-over-60 (/ (* 2.0 solver/pi) 60.0))

(defn- require-num
  [m key]
  (let [v (get m key)]
    (when-not (and (number? v) (pos? v))
      (throw (ex-info (str "envelope needs a positive number for " (name key))
                      {:key key :value v})))
    (double v)))

(defn envelope
  "Build the envelope of an already-sized motor.

  `motor` is a `motor.solver/solve` (or `size-for-power`) result carrying
  `:torque-Nm`. `case` must carry `:rpm-base` (unless the sized result carries
  it) and `:rpm-max` — the caller's speeds; no default is provided (see ns doc)."
  [motor case]
  (when-not (and (map? motor) (contains? motor :torque-Nm))
    (throw (ex-info "envelope needs a sized motor result with :torque-Nm"
                    {:motor motor})))
  (let [t0     (require-num motor :torque-Nm)
        rpm-b  (require-num (if (contains? motor :rpm-base) motor case) :rpm-base)
        rpm-m  (require-num case :rpm-max)]
    (when (< rpm-m rpm-b)
      (throw (ex-info ":rpm-max must be >= :rpm-base"
                      {:rpm-base rpm-b :rpm-max rpm-m})))
    (let [w-b (* rpm-b two-pi-over-60)
          p-kw (/ (* t0 w-b) 1000.0)]
      {:torque-Nm t0 :rpm-base rpm-b :rpm-max rpm-m
       :p-peak-kW p-kw
       :sized-for-kW (:p-peak-kW motor)
       :magnet (:magnet motor)
       :weakening-eff-unmodeled? true
       :solver :rom-motor-envelope})))

(defn torque-at
  "Torque (N·m) available at `rpm`. Constant torque up to base speed, ideal
  constant power (T0·ω_base/ω) above it. Throws beyond :rpm-max."
  [{:keys [torque-Nm rpm-base rpm-max]} rpm]
  (let [rpm (double rpm)]
    (cond (not (and (number? rpm) (pos? rpm)))
          (throw (ex-info "torque-at needs a positive rpm" {:rpm rpm}))
          (> rpm rpm-max)
          (throw (ex-info "rpm beyond :rpm-max — no envelope claim here"
                          {:rpm rpm :rpm-max rpm-max}))
          (<= rpm rpm-base) torque-Nm
          :else (* torque-Nm (/ rpm-base rpm)))))

(defn power-at
  "Shaft power (kW) at `rpm` from the same envelope (P = T·ω)."
  [env rpm]
  (/ (* (torque-at env rpm) (* (double rpm) two-pi-over-60)) 1000.0))

(defn sample
  "Envelope points at the given rpms. Each point carries its region
  (:constant-torque / :constant-power) and the unmodeled-weakening flag."
  [env rpms]
  (mapv (fn [rpm]
          (let [t (torque-at env rpm)]
            {:rpm rpm :torque-Nm t
             :p-kW (power-at env rpm)
             :region (if (<= rpm (:rpm-base env)) :constant-torque :constant-power)
             :weakening-eff-unmodeled? (> rpm (:rpm-base env))}))
        rpms))

(defmethod cae/solve :rom-motor-envelope [case]
  (envelope (:motor case) case))

(defn run
  "Record an envelope summary as datoms, mirroring `motor.solver/run`."
  [motor case]
  (let [r   (envelope motor case)
        cid (or (:case/id case) "motor-envelope-0")
        ent (d/entity "motor" :MotorEnvelope cid
                      {:torqueNm (Math/round (double (:torque-Nm r)))
                       :rpmBase  (long (:rpm-base r))
                       :rpmMax   (long (:rpm-max r))
                       :pkW      (Math/round (* 100.0 (:p-peak-kW r)))})
        led (d/log [ent])]
    (assoc r :datoms (:datoms led) :datom-count (:count led))))
