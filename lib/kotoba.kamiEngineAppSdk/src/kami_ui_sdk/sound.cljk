(ns kami-ui-sdk.sound
  "Ported from kami-engine's live `kami-ui-sdk/kami-sound.js` (JS, not
   deleted Rust — see `kami-ui-sdk` root docstring). ADR-2607010930.

   `kami-sound.js` synthesizes UI sound effects (click/hover/select/
   success/error/.../coin/tick) procedurally via the Web Audio API —
   no audio files. Each preset is a short sequence of oscillator/noise
   'notes' (`_osc`/`_noise` calls) with an attack/sustain/release gain
   envelope and, optionally, a frequency sweep.

   Ported (pure, portable):
   - `presets` — every preset (`click`, `hover`, `select`, `success`,
     `error`, `warning`, `pop`, `whoosh`, `coin`, `navigate`,
     `zoom-in`, `zoom-out`, `reset`, `loaded`) re-expressed as *pure
     declarative data*: a vector of note specs `{:kind :type :freq
     :duration :volume :delay :release :freq-to :attack}` instead of
     imperative `_osc`/`_noise` calls. `tick` (random frequency jitter)
     is represented with `:freq :random-range` instead of a live
     `Math.random()` call, so preset *data* stays deterministic; a
     caller picks the frequency.
   - `envelope-at` — pure port of `_osc`'s gain-envelope math
     (`linearRampToValueAtTime` attack, sustain plateau,
     `exponentialRampToValueAtTime` release) as `(spec t) -> gain`,
     `t` being seconds since the note's `:delay`.
   - `freq-at` — pure port of the optional `exponentialRampToValueAtTime`
     frequency sweep (`:freq` -> `:freq-to` over `:duration`), as
     `(spec t) -> freq`.
   - `list-presets` — pure port of `list()` (preset name lookup).

   Excluded (Web Audio-only, no CLJC equivalent):
   - `_ensureCtx` (constructs `AudioContext`/`GainNode`).
   - `_osc`/`_noise`'s actual `OscillatorNode`/`AudioBufferSourceNode`/
     `BiquadFilterNode` graph construction and scheduling
     (`osc.start`/`gain.gain.setValueAtTime`/...).
   - `init()` (context resume on user gesture), `setVolume`,
     `setEnabled` (mutate live `GainNode`/module state).
   - `register()` (registers a live closure, not data).

   Relationship to `kotoba-lang/audio`: `kotoba-lang/audio` is a 3D
   *positional audio mixer* (source/listener/rolloff, binaural ITD/ILD,
   WAV encoding) restored from the Rust `kami-audio` crate — a
   different domain (spatial mixing math) from this file's procedural
   *UI-sound-effect synthesis* (oscillator envelopes/sweeps). There is
   no shared math to reuse; both restorations are independent and
   documented here only to make the boundary explicit.")

;; ─── Preset data ─────────────────────────────────────────────────

(defn- note
  ([type freq duration] (note type freq duration {}))
  ([type freq duration opts]
   (merge {:kind :osc :type type :freq freq :duration duration
           :volume 0.5 :delay 0 :attack 0.01 :release (* duration 0.3)}
          opts)))

(def presets
  "Pure data port of every preset in the JS `presets` object. Each
   value is a vector of note specs (see namespace docstring)."
  {:click [(note :sine 800 0.08 {:volume 0.3 :release 0.04})]
   :hover [(note :sine 1200 0.05 {:volume 0.12 :release 0.03})]
   :select [(note :sine 660 0.1 {:volume 0.25 :release 0.05})
            (note :sine 880 0.12 {:volume 0.25 :delay 0.08 :release 0.06})]
   :success [(note :sine 523 0.12 {:volume 0.25})
             (note :sine 659 0.12 {:volume 0.25 :delay 0.1})
             (note :sine 784 0.18 {:volume 0.3 :delay 0.2})]
   :error [(note :square 300 0.15 {:volume 0.2 :freq-to 200})
           (note :square 250 0.2 {:volume 0.15 :delay 0.12 :freq-to 150})]
   :warning [(note :triangle 400 0.15 {:volume 0.2})
             (note :triangle 350 0.15 {:volume 0.2 :delay 0.15})]
   :pop [(note :sine 600 0.06 {:volume 0.3 :freq-to 1200 :release 0.03})]
   :whoosh [{:kind :noise :duration 0.2 :volume 0.1
             :filter {:type :bandpass :freq 3000 :Q 2}}
            (note :sine 400 0.15 {:volume 0.08 :freq-to 1600})]
   :coin [(note :square 988 0.08 {:volume 0.2})
          (note :square 1319 0.3 {:volume 0.2 :delay 0.08})]
   :navigate [(note :sine 500 0.04 {:volume 0.1 :freq-to 600 :release 0.02})]
   :zoom-in [(note :sine 400 0.1 {:volume 0.12 :freq-to 800 :release 0.05})]
   :zoom-out [(note :sine 800 0.1 {:volume 0.12 :freq-to 400 :release 0.05})]
   :reset [(note :sine 880 0.08 {:volume 0.2 :freq-to 440})
           (note :sine 660 0.12 {:volume 0.15 :delay 0.06})]
   :loaded [(note :sine 587 0.1 {:volume 0.2})
            (note :sine 698 0.1 {:volume 0.2 :delay 0.08})
            (note :sine 880 0.1 {:volume 0.2 :delay 0.16})
            (note :sine 1175 0.25 {:volume 0.25 :delay 0.24})]
   :tick [(note :square 2000 0.02 {:volume 0.06 :release 0.01
                                     :random-range [0 1000]})]})

(defn list-presets
  "Pure port of `list()`: preset names."
  []
  (vec (keys presets)))

;; ─── Envelope / sweep math ───────────────────────────────────────

(defn envelope-at
  "Pure port of `_osc`'s gain-envelope: given a note spec and `t`
   (seconds since the note's own `:delay`, i.e. already offset), returns
   the instantaneous gain. Matches the JS ADSR-lite shape: linear
   attack 0 -> volume, sustain plateau at volume, then an exponential
   release toward ~0 starting at `duration - release`."
  [{:keys [duration volume attack release] :or {volume 0.5 attack 0.01}} t]
  (let [release (or release (* duration 0.3))
        sustain-start attack
        release-start (- duration release)]
    (cond
      (< t 0) 0
      (< t sustain-start) (* volume (/ t attack))
      (< t release-start) volume
      (>= t duration) 0.001
      :else
      ;; exponential decay from volume to 0.001 over [release-start, duration]
      (let [frac (/ (- t release-start) (- duration release-start))]
        (* volume (Math/pow (/ 0.001 volume) frac))))))

(defn freq-at
  "Pure port of the optional exponential frequency sweep: `:freq` ->
   `:freq-to` over `:duration`, clamped at 20 Hz (as in the JS
   `Math.max(opts.freqTo, 20)`). Returns `:freq` unchanged when no
   `:freq-to` is present."
  [{:keys [freq freq-to duration]} t]
  (if (nil? freq-to)
    freq
    (let [target (max freq-to 20)
          frac (min (max (/ t duration) 0) 1)]
      (* freq (Math/pow (/ target freq) frac)))))
