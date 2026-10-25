(ns kami-ui-sdk.engine-audio
  "Ported from kami-engine's live `kami-ui-sdk/kami-engine-audio.js`
   (JS, not deleted Rust — see `kami-ui-sdk` root docstring).
   ADR-2607010930.

   `kami-engine-audio.js` is a physically-modelled internal-combustion-
   engine synthesizer (car-sim demo): a bandlimited-sawtooth harmonic
   stack + exhaust delay-line + induction/tire noise buses, all driven
   per-frame from `window.__carsim_hud` (`rpm`/`throttle`/`speed_kmh`/
   `grounded_wheels`/`brake`) and `window.__carsim_steer`. The Web
   Audio graph itself is stateful and browser-only, but the *parameter
   formulas* that map HUD state to synthesis parameters each frame
   (`_tick`'s math) are pure.

   Ported (pure, portable):
   - Engine constants (`CYLINDERS`, `FIRINGS-PER-REV`, `IDLE-RPM`,
     `REDLINE-RPM`, `HARMONIC-COUNT`).
   - `fundamental-freq` — `(rpm/60) * firings-per-rev`.
   - `harmonic-params` — per-harmonic `{:freq :gain}` (1/h falloff,
     throttle-driven bloom).
   - `lowpass-cutoff` — RPM-linear cutoff (600 Hz idle -> ~4 kHz
     redline).
   - `engine-loudness` — load-following engine-bus volume formula.
   - `induction-params` — throttle/RPM-driven induction-noise
     bandpass center + gain.
   - `tire-params` — speed/brake/steer-driven tire-noise gain +
     bandpass center.
   - `hud->synth-params` — aggregates all of the above into one
     per-frame parameter bundle, the pure core of `_tick()` (HUD state
     in, synthesis parameters out — no node writes).
   - `impact-envelope-at` — pure port of `impact()`'s decaying-noise
     envelope (`exp(-n*30/len)`) and the one-shot gain ramp
     (`intensity*0.6` -> `0.001` over 0.30s).
   - `clamp` — the `Math.max(lo, Math.min(hi, v))` idiom used
     throughout `_tick`.

   Excluded (Web Audio-only, no CLJC equivalent):
   - `_ensureCtx`/`_buildEngineGraph`/`_buildInductionNoise`/
     `_buildTireNoise` (constructs oscillators, delay lines, biquad
     filters, noise buffers).
   - `_tick`'s actual `requestAnimationFrame` loop, `window.__carsim_*`
     global reads, and `setTargetAtTime` node writes — only the
     formulas that compute the *target values* were ported.
   - `impact()`'s live buffer synthesis and node scheduling.
   - `init`/`start`/`stop`/`setVolume` (graph lifecycle + live
     `GainNode` mutation).

   Relationship to `kotoba-lang/audio`: distinct domain — that
   restoration is a 3D positional mixer (source/listener/rolloff,
   binaural ITD/ILD), this file is procedural engine-sound synthesis
   parameter math. No shared logic to reuse; noted for completeness.")

;; ─── Constants ───────────────────────────────────────────────────

(def CYLINDERS 4)
(def FIRINGS-PER-REV (/ CYLINDERS 2)) ;; 4-stroke
(def IDLE-RPM 800)
(def REDLINE-RPM 7200)
(def HARMONIC-COUNT 5)

(defn clamp [lo hi v] (max lo (min hi v)))

;; ─── Per-frame parameter formulas (pure port of `_tick`) ──────────

(defn fundamental-freq
  "`(rpm/60) * firings-per-rev` — the engine's fundamental frequency."
  [rpm]
  (* (/ rpm 60.0) FIRINGS-PER-REV))

(defn harmonic-params
  "Per-harmonic `{:freq :gain}` for harmonic `h` (1-indexed) given the
   fundamental and throttle (0-1). 1/h falloff, throttle-driven bloom
   (`0.4 + 0.6*throttle`)."
  [fundamental throttle h]
  {:freq (* fundamental h)
   :gain (* (/ 1.0 h) (+ 0.4 (* 0.6 throttle)))})

(defn lowpass-cutoff
  "RPM-linear lowpass cutoff: 600 Hz at idle -> 4000 Hz at redline."
  [rpm]
  (+ 600 (* (/ rpm REDLINE-RPM) 3400)))

(defn engine-loudness
  "Load-following engine-bus gain target (already includes the JS's
   final `* 0.6` scale)."
  [rpm throttle]
  (* (+ 0.10 (* 0.45 (/ rpm REDLINE-RPM)) (* 0.25 throttle)) 0.6))

(defn induction-params
  "Induction-noise bandpass `{:freq :gain}` — center tracks RPM
   slightly, gain scales with throttle."
  [rpm throttle]
  {:freq (+ 180 (* (/ rpm REDLINE-RPM) 600))
   :gain (* throttle 0.18)})

(defn tire-params
  "Tire-noise `{:gain :freq}` — louder with speed (when grounded),
   brighter/higher-pitched under brake/steer."
  [grounded speed-kmh brake steer]
  (let [base (if (zero? grounded) 0 (min 1 (/ speed-kmh 80.0)))
        gain (* base (+ 0.10 (* 0.35 (+ brake steer))))
        freq (+ 800 (* 1800 (+ (* brake 0.6) (* steer 0.4))))]
    {:gain gain :freq freq}))

(defn hud->synth-params
  "Aggregates the whole per-frame parameter bundle from a HUD map
   `{:rpm :throttle :speed-kmh :grounded-wheels :brake}` and `steer`
   (`|__carsim_steer|`), clamping the same way `_tick` does. This is
   the pure core of `_tick()` minus the actual AudioParam writes."
  [{:keys [rpm throttle speed-kmh grounded-wheels brake]
    :or {rpm IDLE-RPM throttle 0 speed-kmh 0 grounded-wheels 0 brake 0}}
   steer]
  (let [rpm (clamp IDLE-RPM REDLINE-RPM rpm)
        throttle (clamp 0 1 throttle)
        speed-kmh (max 0 speed-kmh)
        grounded (clamp 0 4 grounded-wheels)
        brake (clamp 0 1 brake)
        steer (Math/abs (double (or steer 0)))
        fundamental (fundamental-freq rpm)]
    {:fundamental fundamental
     :harmonics (mapv #(harmonic-params fundamental throttle %) (range 1 (inc HARMONIC-COUNT)))
     :lowpass-cutoff (lowpass-cutoff rpm)
     :engine-loudness (engine-loudness rpm throttle)
     :induction (induction-params rpm throttle)
     :tire (tire-params grounded speed-kmh brake steer)}))

;; ─── Impact ──────────────────────────────────────────────────────

(defn impact-envelope-at
  "Pure port of `impact()`'s decaying-noise sample envelope:
   `exp(-n*30/len)` for sample index `n` of `len` total."
  [n len]
  (Math/exp (/ (* n -30.0) len)))

(defn impact-gain-at
  "Pure port of `impact()`'s one-shot gain ramp: exponential decay from
   `intensity*0.6` to 0.001 over `duration` (0.30s in the JS), given
   elapsed time `t`. `intensity` is clamped to [0,1] as in the JS."
  [intensity t duration]
  (let [i (clamp 0 1 intensity)
        start (* i 0.6)
        frac (clamp 0 1 (/ t duration))]
    (if (zero? start)
      0.0
      (* start (Math/pow (/ 0.001 start) frac)))))
