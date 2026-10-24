(ns audio.synth
  "KAMI Audio synthesis primitives (Wave 2, ADR-2607121400 `com-junkawasaki/root`).

  Pure functions over plain sample buffers (vectors of doubles in
  [-1.0, 1.0]) and integer sample counts — no device/callback code,
  matching `audio`'s existing pure-function discipline. Oscillators are
  plain (non band-limited) waveform generators; ADSR produces a
  gain-multiplier curve to be elementwise-multiplied against a buffer
  via `apply-envelope`.

  Time is expressed either as sample counts (exact, integer) or as
  seconds + `sample-rate` (converted to an integer sample count via
  `Math/round` at the boundary) — never as a bare float sample index,
  so envelope breakpoints land on an exact sample.")

(def two-pi (* 2.0 Math/PI))

(defn- phase-inc [freq sample-rate]
  (/ (* two-pi freq) sample-rate))

(defn sine-wave
  "n samples of a sine wave at `freq` Hz, sample-rate `sr`, unit amplitude."
  [freq sr n]
  (let [inc (phase-inc freq sr)]
    (mapv (fn [i] (Math/sin (* inc i))) (range n))))

(defn square-wave
  "n samples of a square wave: +1.0 for the first half-cycle, -1.0 for
  the second, per period `sr/freq` samples."
  [freq sr n]
  (let [period (/ sr freq)]
    (mapv (fn [i] (if (< (mod i period) (/ period 2.0)) 1.0 -1.0)) (range n))))

(defn saw-wave
  "n samples of a rising sawtooth in [-1.0, 1.0), period `sr/freq` samples."
  [freq sr n]
  (let [period (/ sr freq)]
    (mapv (fn [i] (- (* 2.0 (/ (mod i period) period)) 1.0)) (range n))))

(defn triangle-wave
  "n samples of a triangle wave in [-1.0, 1.0], period `sr/freq` samples."
  [freq sr n]
  (let [period (/ sr freq)]
    (mapv (fn [i]
            (let [phase (/ (mod i period) period)]
              (if (< phase 0.5)
                (- (* 4.0 phase) 1.0)
                (- 3.0 (* 4.0 phase)))))
          (range n))))

(defn seconds->samples
  "Exact integer sample count for `seconds` at `sr` (rounded once, at
  the seconds->samples boundary, so downstream indexing stays exact)."
  [seconds sr]
  (long (Math/round (* (double seconds) sr))))

(defn adsr
  "ADSR gain-multiplier curve of `n` samples. `params` (all times in
  seconds, converted internally via `seconds->samples`):
    :attack       time to rise 0 -> 1
    :decay        time to fall 1 -> sustain-level
    :sustain      sustain gain level (0.0-1.0), held until release begins
    :release      time to fall sustain-level -> 0, starting at :gate-off
    :gate-off     sample index (integer) at which the note is released;
                  defaults to n (i.e. release never starts within the buffer)
    :sample-rate  sr, required for the seconds->samples conversion"
  [{:keys [attack decay sustain release gate-off sample-rate]
    :or {sustain 1.0}}
   n]
  (let [sr sample-rate
        a (seconds->samples attack sr)
        d (seconds->samples decay sr)
        r (seconds->samples release sr)
        gate-off (or gate-off n)]
    (mapv
     (fn [i]
       (cond
         (< i a)
         (if (zero? a) 1.0 (/ (double i) a))

         (< i (+ a d))
         (let [t (/ (double (- i a)) (max d 1))]
           (+ 1.0 (* t (- sustain 1.0))))

         (< i gate-off)
         sustain

         (< i (+ gate-off r))
         (let [t (/ (double (- i gate-off)) (max r 1))]
           (* sustain (- 1.0 t)))

         :else 0.0))
     (range n))))

(defn apply-envelope
  "Elementwise-multiply `buffer` by `envelope` (equal length)."
  [buffer envelope]
  (mapv * buffer envelope))
