(ns etzhayyim.ie-flow.control
  "etzhayyim.ie-flow.control — CAPTURE + CONTROL of the information-energy flow, as numbers.
  ADR-2606211200 + 2606212200.

  `etzhayyim.ie-flow.dynamics` captures the flow as accumulated-order STOCKS (open-loop: a fixed
  input schedule rolled forward). This namespace closes the loop: a deterministic PI CONTROLLER
  drives a stock to a TARGET by modulating its actuating input, and reports the control numbers the
  org actually wants — settling time, overshoot, steady-state error, control effort. So 'エネルギー流
  の把握と制御' yields measurable figures, not just a trajectory.

  Pure + deterministic (no wall clock, no randomness) — a control run is content-addressable and a
  tournament reproducible. Stdlib only."
  (:refer-clojure :exclude [pi]))

(defn pi-control
  "Closed-loop control of ONE accumulated-order stock toward `target`. The plant is an integrator
  with a KNOWN net inflow (base−drain), so the correct, windup-free controller is FEEDFORWARD (cancel
  the known disturbance) + proportional (+ optional integral for unmodelled error):
     e        = target − stock                       (error)
     ff       = drain − base                         (feedforward: cancels the known net inflow)
     integral += e (anti-windup clamped)             (residual accumulation, default Ki 0)
     u        = ff + Kp·e + Ki·integral              (control effort on the actuating input)
     stock'   = max(0, stock + base + u − drain)     (⇒ stock + Kp·e + Ki·integral: pure integrator)

  P-control on an integrator already has ZERO steady-state error, so it converges with no overshoot;
  the integral is opt-in. Returns the control READOUT (all numbers):
    {:trajectory [..] :final :final-error :overshoot-pct :settling-step :effort :u-final :settled?
     :steps :target}. Pure. `opts`: :target :steps(24) :Kp(0.5) :Ki(0) :x0(0) :base(0) :drain(0)
    :band(0.02 = ±2% settling band)."
  [{:keys [target steps Kp Ki x0 base drain band]
    :or {steps 24 Kp 0.5 Ki 0.0 x0 0 base 0 drain 0 band 0.02}}]
  (let [tgt (double target)
        tol (* (max 1.0 (Math/abs tgt)) (double band))
        ff (- (double drain) (double base))                 ; feedforward
        imax (/ (max 1.0 (Math/abs tgt)) (max 1.0e-6 (double Ki)))]  ; anti-windup bound
    (loop [t 0 stock (double x0) integral 0.0 traj [(double x0)]
           effort 0.0 peak (double x0) settle nil u-last 0.0]
      (if (>= t steps)
        (let [err (- tgt stock)
              over (if (> peak tgt) (* 100.0 (/ (- peak tgt) (max 1.0 (Math/abs tgt)))) 0.0)]
          {:steps steps :target tgt :final stock :final-error err
           :overshoot-pct over :settling-step settle :effort effort :u-final u-last
           :settled? (<= (Math/abs err) tol) :trajectory traj})
        (let [e (- tgt stock)
              integral' (max (- imax) (min imax (+ integral e)))
              u (+ ff (* (double Kp) e) (* (double Ki) integral'))
              stock' (max 0.0 (+ stock (double base) u (- (double drain))))
              settle' (or settle (when (<= (Math/abs (- tgt stock')) tol) (inc t)))]
          (recur (inc t) stock' integral' (conj traj stock')
                 (+ effort (Math/abs u)) (max peak stock') settle' u))))))

(defn control-stock
  "Convenience: control an actor's RESERVES stock from its system-dynamics params toward a target
  (default = 1.5× the open-loop terminal reserves), modulating revenue. Returns the pi-control
  readout. `sd` = {:init {..} :inp {..} :steps n} (etzhayyim.ie-flow.organism/sd-params shape)."
  ([sd] (control-stock sd nil))
  ([{:keys [init inp steps] :or {steps 24}} target]
   (let [x0 (double (get init "reserves" (get init :reserves 0)))
         base (double (get inp "revenue" (get inp :revenue 0)))
         drain (double (get inp "cost" (get inp :cost 0)))
         open-terminal (max 1.0 (+ x0 (* steps (- base drain))))
         tgt (double (or target (* 1.5 open-terminal)))]
     (pi-control {:target tgt :steps steps :x0 x0 :base base :drain drain}))))
