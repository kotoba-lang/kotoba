(ns dcs.pid
  "A pure, host-independent PID algorithm: positional form with clamped
  anti-windup and bumpless auto/manual transfer. No I/O — `dcs.execute`
  calls this once per :auto loop per scan cycle.")

(defn init-state
  "A fresh PID state: zero integral, no prior error/output."
  []
  {:dcs/integral 0.0 :dcs/prev-error nil :dcs/prev-output nil})

(defn- clamp [[lo hi] v]
  (cond (nil? v) v (< v lo) lo (> v hi) hi :else v))

(defn step
  "One PID execution. `tuning` is {:kp :ki :kd}; `state` is as returned by
  this fn (or `init-state`); `output-limits` is [lo hi]. Returns {:dcs/output
  out :dcs/state' state'}.

  Anti-windup: the integral term only accumulates when the unclamped output
  would stay within `output-limits` (clamped/conditional integration), so a
  saturated output never winds the integral further."
  [tuning state pv sp dt output-limits]
  (let [{:keys [kp ki kd]} tuning
        error       (- sp pv)
        prev-error  (:dcs/prev-error state)
        derivative  (if (and prev-error (pos? dt)) (/ (- error prev-error) dt) 0.0)
        p-term      (* kp error)
        d-term      (* kd derivative)
        candidate-i (+ (:dcs/integral state) (* ki error dt))
        raw-output  (+ p-term candidate-i d-term)
        clamped     (clamp output-limits raw-output)
        saturated?  (not= clamped raw-output)
        integral'   (if saturated? (:dcs/integral state) candidate-i)]
    {:dcs/output clamped
     :dcs/state' {:dcs/integral integral' :dcs/prev-error error :dcs/prev-output clamped}}))

(defn transfer-to-auto
  "Bumpless transfer: derive a PID state whose next `step` starts the output
  at `manual-output` (the value the loop was last holding in :manual mode),
  given the loop's `tuning` and the pv/sp at the moment of transfer. Call
  this once, at the :manual -> :auto edge, before the next `step`."
  [tuning pv sp manual-output]
  (let [{:keys [kp]} tuning
        error (- sp pv)]
    {:dcs/integral (- manual-output (* kp error))
     :dcs/prev-error error
     :dcs/prev-output manual-output}))
