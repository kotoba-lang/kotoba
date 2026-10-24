(ns audio.effects
  "KAMI Audio delay + dynamics effects (Wave 2, ADR-2607121400 `com-junkawasaki/root`).

  Pure functions over plain sample buffers, matching `audio`'s existing
  discipline (no device/callback code).")

(defn delay-line
  "Feedback delay line. `opts`:
    :delay-samples  integer delay length (exact — this is what makes
                     an impulse round-trip land on a precise sample)
    :feedback       0.0-1.0, gain fed back into the delay buffer
    :wet-dry        0.0 (fully dry) - 1.0 (fully wet) mix
  Returns a buffer the same length as `buffer`."
  [buffer {:keys [delay-samples feedback wet-dry]
           :or {feedback 0.0 wet-dry 0.5}}]
  (let [n (count buffer)
        line (double-array (max delay-samples 1) 0.0)]
    (loop [i 0, write-pos 0, out (transient [])]
      (if (>= i n)
        (persistent! out)
        (let [x (double (nth buffer i))
              delayed (aget line write-pos)
              wet delayed
              y (+ (* x (- 1.0 wet-dry)) (* wet wet-dry))]
          (aset line write-pos (double (+ x (* delayed feedback))))
          (recur (inc i)
                 (mod (inc write-pos) (alength line))
                 (conj! out y)))))))

(defn- db->linear [db] (Math/pow 10.0 (/ db 20.0)))
(defn- linear->db [lin] (* 20.0 (/ (Math/log (max lin 1e-9)) (Math/log 10.0))))

(defn compressor
  "Feed-forward compressor with a one-pole envelope follower. `opts`:
    :threshold-db   level above which gain reduction begins
    :ratio          e.g. 4.0 means 4:1 reduction above threshold
    :attack         envelope rise time constant, seconds
    :release        envelope fall time constant, seconds
    :sample-rate    sr, required for the attack/release coefficients
  Returns a buffer the same length as `buffer`."
  [buffer {:keys [threshold-db ratio attack release sample-rate]}]
  (let [sr (double sample-rate)
        a-coef (Math/exp (/ -1.0 (* attack sr)))
        r-coef (Math/exp (/ -1.0 (* release sr)))]
    (loop [xs buffer, env 0.0, out (transient [])]
      (if (empty? xs)
        (persistent! out)
        (let [x (double (first xs))
              level (Math/abs x)
              coef (if (> level env) a-coef r-coef)
              env' (+ (* coef env) (* (- 1.0 coef) level))
              level-db (linear->db env')
              over-db (max 0.0 (- level-db threshold-db))
              gain-reduction-db (* over-db (- 1.0 (/ 1.0 ratio)))
              gain (db->linear (- gain-reduction-db))]
          (recur (rest xs) env' (conj! out (* x gain))))))))
