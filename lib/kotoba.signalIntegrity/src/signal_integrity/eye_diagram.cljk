(ns signal-integrity.eye-diagram
  "Eye diagram generation and metrics extraction for serial link
  analysis. Ported from kami-si's `eye_diagram.rs`
  (kotoba-lang/kami-engine, retired Rust crate, ADR-2607010000).
  No network, no I/O.

  Sample/noise/jitter generation is deterministic given the same
  inputs, but the PRNG differs by platform — see the `next-rand`
  docstring and README \"Portability notes\": the JVM uses the exact
  Rust LCG (bit-identical wraparound arithmetic on a primitive `long`);
  cljs, which has no 64-bit integer primitive, substitutes a 32-bit
  xorshift PRNG. Both are deterministic and produce plausible bounded
  noise/jitter, but the two platforms do not produce byte-identical
  waveforms — the Rust test suite itself only asserts on structural
  properties (eye height positive, samples non-empty, width bounded by
  the bit period), never exact sample values, so this does not weaken
  the ported parity tests."
  (:require [signal-integrity.constants :as constants]
            [signal-integrity.math :as math]))

(def ^:private samples-per-bit (:eye/samples-per-bit constants/constants))
(def ^:private center-window-start (:eye/center-window-start constants/constants))
(def ^:private center-window-end (:eye/center-window-end constants/constants))
(def ^:private sigma-multiplier (:eye/sigma-multiplier constants/constants))
(def ^:private jitter-pp-multiplier (:eye/jitter-pp-multiplier constants/constants))
(def ^:private default-q-factor (:eye/default-q-factor constants/constants))

#?(:clj
   (def ^:private lcg-mul (long (:eye/lcg-multiplier constants/constants))))
#?(:clj
   (def ^:private lcg-add (long (:eye/lcg-increment constants/constants))))
#?(:clj
   (def ^:private lcg-seed0 (long (:eye/lcg-seed constants/constants))))

#?(:cljs
   (def ^:private xorshift32-seed0 (:eye/xorshift32-seed constants/constants)))

#?(:clj
   (defn- u64->double
     "Convert a long representing an unsigned 64-bit bit pattern to a
     double, matching Rust's `u64 as f64` cast."
     ^double [^long x]
     (if (>= x 0)
       (double x)
       (+ (* 2.0 (double (unsigned-bit-shift-right x 1)))
          (double (bit-and x 1))))))

#?(:clj (def ^:private u64-max-d (u64->double -1)))

(defn- next-rand
  "Deterministic PRNG step. Returns `[state' r]` where `r` is uniform in
  `[-1.0, 1.0]`.

  On the JVM: Knuth's MMIX-style 64-bit LCG, exactly matching the Rust
  port's inline `next_rand` closure (multiplier `6364136223846793005`,
  increment `1442695040888963407`, seed `0xDEAD_BEEF_CAFE_1234`) —
  wraparound multiply/add on a primitive `long` is bit-identical to
  Rust's `u64::wrapping_mul`/`wrapping_add` regardless of whether the
  64 bits are read as signed or unsigned.

  In cljs (no native 64-bit integers): a 32-bit xorshift PRNG, seeded
  from `:eye/xorshift32-seed`. Not bit-compatible with the JVM/Rust
  LCG — see the namespace docstring."
  [state]
  #?(:clj
     (let [state' (unchecked-add (unchecked-multiply (long state) lcg-mul) lcg-add)
           r (- (* (/ (u64->double state') u64-max-d) 2.0) 1.0)]
       [state' r])
     :cljs
     (let [x0 (bit-xor state (bit-shift-left state 13))
           x1 (bit-xor x0 (unsigned-bit-shift-right x0 17))
           state' (bit-xor x1 (bit-shift-left x1 5))
           u (unsigned-bit-shift-right state' 0)
           r (- (* (/ u 4294967295.0) 2.0) 1.0)]
       [state' r])))

(defn- initial-seed []
  #?(:clj lcg-seed0 :cljs xorshift32-seed0))

(defn eye-metrics
  "Build an eye-diagram metrics map."
  [{:keys [eye-height-mv eye-width-ps jitter-rms-ps jitter-pp-ps ber-estimate]}]
  {:eye/height-mv eye-height-mv
   :eye/width-ps eye-width-ps
   :eye/jitter-rms-ps jitter-rms-ps
   :eye/jitter-pp-ps jitter-pp-ps
   :eye/ber-estimate ber-estimate})

(defn- mean [xs] (/ (reduce + 0.0 xs) (count xs)))

(defn- sample-stddev
  "Sample standard deviation (n-1 divisor), matching the Rust port."
  [xs m]
  (math/sqrt (/ (reduce + 0.0 (map #(let [d (- % m)] (* d d)) xs))
                (dec (count xs)))))

(defn generate-eye-data
  "Generate eye diagram data for a serial link.

  Produces overlaid bit-period waveform samples with noise and jitter,
  then computes eye opening metrics.

  `bit-rate-gbps`/`amplitude-mv`/`rise-time-ps`/`noise-rms-mv`/
  `jitter-rms-ps`/`num-bits` mirror the Rust port's positional
  arguments. Returns `{:eye/samples [[time-ps voltage-mv] ...]
  :eye/metrics {...}}`."
  [{:keys [bit-rate-gbps amplitude-mv rise-time-ps noise-rms-mv jitter-rms-ps num-bits]}]
  (let [bit-period-ps (/ 1000.0 bit-rate-gbps)
        dt (/ bit-period-ps samples-per-bit)
        half-amp (/ amplitude-mv 2.0)
        ;; Rise/fall time constant for exponential edges.
        tau (/ rise-time-ps 2.2)]
    (loop [bit-idx 0
           seed (initial-seed)
           prev-level 1.0
           samples (transient [])]
      (if (>= bit-idx num-bits)
        (let [samples (persistent! samples)
              center-start (* bit-period-ps center-window-start)
              center-end (* bit-period-ps center-window-end)
              center-samples (into [] (comp (filter (fn [[t _]] (and (>= t center-start) (<= t center-end))))
                                             (map second))
                                    samples)
              high-samples (filterv pos? center-samples)
              low-samples (filterv (complement pos?) center-samples)
              high-mean (if (empty? high-samples) half-amp (mean high-samples))
              low-mean (if (empty? low-samples) (- half-amp) (mean low-samples))
              high-sigma (if (> (count high-samples) 1) (sample-stddev high-samples high-mean) noise-rms-mv)
              low-sigma (if (> (count low-samples) 1) (sample-stddev low-samples low-mean) noise-rms-mv)
              eye-height (- (- high-mean (* sigma-multiplier high-sigma))
                            (+ low-mean (* sigma-multiplier low-sigma)))
              eye-width (- bit-period-ps (* jitter-pp-multiplier jitter-rms-ps))
              jitter-pp (* jitter-rms-ps jitter-pp-multiplier)
              ;; BER estimate from Q-factor.
              q (if (> (+ high-sigma low-sigma) 0.0)
                  (/ (- high-mean low-mean) (+ high-sigma low-sigma))
                  default-q-factor)
              ber (* 0.5 (math/exp (/ (- (* q q)) 2.0)))]
          {:eye/samples samples
           :eye/metrics (eye-metrics {:eye-height-mv (max eye-height 0.0)
                                       :eye-width-ps (max eye-width 0.0)
                                       :jitter-rms-ps jitter-rms-ps
                                       :jitter-pp-ps jitter-pp
                                       :ber-estimate ber})})
        (let [;; Pseudo-random bit pattern.
              bit-val (if (zero? (mod (bit-xor (* bit-idx 7) (* bit-idx 13)) 3)) -1.0 1.0)
              [seed1 jrand] (next-rand seed)
              jitter-offset (* jrand jitter-rms-ps)
              [seed2 samples2]
              (loop [s 0
                     seed' seed1
                     samps samples]
                (if (>= s samples-per-bit)
                  [seed' samps]
                  (let [t (+ (* s dt) jitter-offset)
                        t-wrapped (mod t bit-period-ps)
                        ;; Transition model: exponential rise/fall.
                        transition (if (> (math/abs (- bit-val prev-level)) 0.5)
                                     (let [alpha (- 1.0 (math/exp (- (/ t-wrapped tau))))]
                                       (+ prev-level (* (- bit-val prev-level) alpha)))
                                     bit-val)
                        [seed'' nrand] (next-rand seed')
                        noise (* nrand noise-rms-mv)
                        voltage (+ (* transition half-amp) noise)]
                    (recur (inc s) seed'' (conj! samps [t-wrapped voltage])))))]
          (recur (inc bit-idx) seed2 bit-val samples2))))))
