(ns floorplan-lab.sonar
  "Chirp-echo acoustic sonar: emit a chirp, record the echo, cross-
  correlate transmitted-vs-recorded to find the round-trip delay, convert
  to a wall distance via time-of-flight at the speed of sound. Part of
  the indoor floorplan-lab (ADR-2607140600 Phase 3a device-capability
  bridge) -- SOFTWARE ONLY, no real AVAudioEngine involved; buffers are
  either `floorplan-lab.sensing-bridge`-adapted driver output (fixed-
  point-decoded to float) or, in this lab's tests, synthetic data.

  CONTRACT: `estimate-wall-distance-m` assumes RECORDED started capturing
  at the same instant TRANSMITTED began playing -- this matches
  `kotoba.sensing-host`'s op shape (`audio-play`/`audio-record` are
  separate calls with no shared clock parameter documented, so a real
  driver MUST start record-then-play or play-then-record with a known,
  accounted-for offset; this lab's synthetic tests always construct
  RECORDED with TRANSMITTED's start at sample 0 of the recording window).

  METHOD: direct (non-FFT) cross-correlation of TRANSMITTED against
  RECORDED, argmax lag = the echo's round-trip delay in samples. This is
  O(n*m) -- fine at the sample counts this lab's synthetic tests use; a
  real-time implementation would use an FFT-based matched filter (future
  work, see README).")

(def speed-of-sound-m-per-s
  "Standard dry-air speed of sound at ~20C. A production estimator would
  vary this with measured/estimated air temperature (~0.6 m/s per
  degree C) -- fixed here for simplicity (future work, see README)."
  343.0)

;; ---------- portable math ----------

#?(:clj (defn- sin ^double [^double x] (Math/sin x))
   :cljs (defn- sin [x] (js/Math.sin x)))

(def ^:private pi 3.141592653589793)

(defn generate-chirp
  "A linear frequency-sweep chirp from FREQ-START-HZ to FREQ-END-HZ over
  DURATION-S seconds at SAMPLE-RATE-HZ, amplitude 1.0, as a vector of
  floats. Pure sine, no amplitude windowing at the edges (a real
  implementation would window to reduce spectral leakage -- future
  work)."
  [freq-start-hz freq-end-hz duration-s sample-rate-hz]
  (let [n (long (* duration-s sample-rate-hz))
        k (/ (- freq-end-hz freq-start-hz) (double duration-s))]
    (vec
     (for [i (range n)]
       (let [t (/ i (double sample-rate-hz))
             phase (* 2 pi (+ (* freq-start-hz t) (* 0.5 k t t)))]
         (sin phase))))))

(defn- dot [a b] (reduce + (map * a b)))

(defn cross-correlate
  "Cross-correlation of TEMPLATE against SIGNAL at every lag where the
  whole template fits inside signal (lag in [0, (count signal) - (count
  template)]). Returns a vector indexed by lag (empty if TEMPLATE doesn't
  fit inside SIGNAL at all)."
  [template signal]
  (let [template (vec template)
        signal (vec signal)
        tn (count template)
        sn (count signal)
        max-lag (- sn tn)]
    (if (neg? max-lag)
      []
      (vec (for [lag (range (inc max-lag))]
             (dot template (subvec signal lag (+ lag tn))))))))

(defn- argmax [xs]
  (first (reduce (fn [[best-i best-v] [i v]]
                    (if (> v best-v) [i v] [best-i best-v]))
                  [0 (first xs)]
                  (map-indexed vector xs))))

(defn estimate-wall-distance-m
  "Estimate the distance to a reflecting wall from a TRANSMITTED chirp
  (as `generate-chirp` produces) and a RECORDED buffer captured per this
  namespace's docstring CONTRACT. SAMPLE-RATE-HZ must match both.
  Cross-correlates TRANSMITTED against RECORDED, takes the argmax lag as
  the echo's round-trip delay in samples, and halves the time-of-flight
  distance (the pulse travels source -> wall -> mic, so distance =
  round-trip-time * speed-of-sound / 2). Returns nil if RECORDED is too
  short to contain a full TRANSMITTED-length window anywhere (no
  measurement possible)."
  ([transmitted recorded sample-rate-hz]
   (estimate-wall-distance-m transmitted recorded sample-rate-hz speed-of-sound-m-per-s))
  ([transmitted recorded sample-rate-hz speed-of-sound]
   (let [corr (cross-correlate transmitted recorded)]
     (when (seq corr)
       (let [lag (argmax corr)
             rtt-s (/ lag (double sample-rate-hz))]
         (/ (* rtt-s speed-of-sound) 2.0))))))
