(ns audio.filter
  "KAMI Audio one-pole filters (Wave 2, ADR-2607121400 `com-junkawasaki/root`).

  Standard one-pole RC-equivalent digital filters, derived from the
  analog RC low-pass with cutoff `fc = 1/(2*pi*RC)`, discretized via
  the backward-difference (bilinear-ish, exact for the one-pole case)
  approximation with `dt = 1/sample-rate`:

    alpha = dt / (RC + dt)                        (low-pass)
    y[n]  = y[n-1] + alpha * (x[n] - y[n-1])

  The high-pass is the complementary one-pole filter (same alpha
  derivation, `alpha' = RC / (RC + dt)`):

    y[n]  = alpha' * (y[n-1] + x[n] - x[n-1])

  Both are first-order (6 dB/octave) filters — adequate for v0 tone
  shaping, not a substitute for a proper biquad/SVF when steeper
  slopes are needed (a later wave can add one without changing this
  namespace's contract).")

(defn- alpha-lp [cutoff-hz sr]
  (let [rc (/ 1.0 (* 2.0 Math/PI cutoff-hz))
        dt (/ 1.0 (double sr))]
    (/ dt (+ rc dt))))

(defn- alpha-hp [cutoff-hz sr]
  (let [rc (/ 1.0 (* 2.0 Math/PI cutoff-hz))
        dt (/ 1.0 (double sr))]
    (/ rc (+ rc dt))))

(defn low-pass
  "One-pole low-pass `buffer` at `cutoff-hz`, sample-rate `sr`."
  [buffer cutoff-hz sr]
  (let [a (alpha-lp cutoff-hz sr)]
    (loop [xs buffer, y-prev 0.0, out (transient [])]
      (if (empty? xs)
        (persistent! out)
        (let [x (first xs)
              y (+ y-prev (* a (- x y-prev)))]
          (recur (rest xs) y (conj! out y)))))))

(defn high-pass
  "One-pole high-pass `buffer` at `cutoff-hz`, sample-rate `sr`."
  [buffer cutoff-hz sr]
  (let [a (alpha-hp cutoff-hz sr)]
    (loop [xs buffer, x-prev 0.0, y-prev 0.0, out (transient [])]
      (if (empty? xs)
        (persistent! out)
        (let [x (first xs)
              y (* a (+ y-prev (- x x-prev)))]
          (recur (rest xs) x y (conj! out y)))))))
