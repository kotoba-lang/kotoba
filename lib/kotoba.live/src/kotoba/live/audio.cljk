(ns kotoba.live.audio
  "Audio — Web Audio synthesis driven by the beat grid.

  Per-track `AudioPattern`s describe the music **declaratively**: a 16-step
  drum pattern + a bass line. The show emits `AudioCue`s on each beat/eighth
  so a host's Web Audio bridge can fire synth calls — nothing here references
  samples; every cue is a (slot, midi, duration) triple a synth fabricates
  from oscillators. Sound *recipes* (`SoundCue` — `{:wave :freq :to :dur
  :gain}`) mirror the `kami.audio` EDN shape used by `:dance/audio :bank`."
  (:require [kotoba.live.mathx :as mathx]))

(def drum-slots [:kick :snare :closed-hat :open-hat :clap :crash :tom :rim])

(defn empty-drum-pattern []
  {:steps (vec (repeat 8 (vec (repeat 8 0.0))))})

(defn- slot-index [slot]
  (loop [i 0 xs drum-slots]
    (cond
      (empty? xs) -1
      (= slot (first xs)) i
      :else (recur (inc i) (rest xs)))))

(defn set-step
  "Set `slot`'s velocity (clamped [0,1]) at 8th-note `step` (0..7)."
  [pattern slot step velocity]
  (let [s (min 7 (max 0 step))
        i (slot-index slot)
        v (max 0.0 (min 1.0 velocity))]
    (update pattern :steps update i assoc s v)))

(defn four-on-floor
  "Four-on-floor kick + back-beat snare + 8th hats — the default groove."
  []
  (reduce (fn [p s]
            (cond-> p
              (even? s) (set-step :kick s 1.0)
              true (set-step :closed-hat s 0.6)))
          (-> (empty-drum-pattern)
              (set-step :snare 2 0.95)
              (set-step :snare 6 0.95))
          (range 8)))

(defn ballad
  "Sparser ballad pattern: kick + clap on backbeat, no hats."
  []
  (-> (empty-drum-pattern)
      (set-step :kick 0 0.9)
      (set-step :kick 4 0.9)
      (set-step :clap 2 0.85)
      (set-step :clap 6 0.85)))

(defn pumping
  "Fast K-pop / EDM: kick on every step + open hat on offbeats."
  []
  (reduce (fn [p s]
            (if (even? s)
              (set-step p :kick s 1.0)
              (set-step p :open-hat s 0.7)))
          (-> (empty-drum-pattern)
              (set-step :snare 2 1.0)
              (set-step :snare 6 1.0))
          (range 8)))

(defn hits-at
  "`[[slot velocity] ...]` active at 8th-step `step` (0..7)."
  [pattern step]
  (let [s (mod step 8)]
    (vec (keep (fn [slot]
                 (let [v (get-in (:steps pattern) [(slot-index slot) s])]
                   (when (pos? v) [slot v])))
               drum-slots))))

;; ── bass ─────────────────────────────────────────────────────────────────

(defn bass-note [at-beat pitch-midi length-beats velocity]
  {:at-beat at-beat :pitch-midi pitch-midi :length-beats length-beats :velocity velocity})

(defn root-pattern-c-minor
  "Default I-V-vi-IV root pattern in C minor — a placeholder bass for any
  4/4 track (Cm-Gm-Abmaj-Fm root motion, held half a bar short of a full
  bar each)."
  []
  (let [pitches [36 43 44 41]]
    {:notes (vec (for [bar (range 4)]
                   (bass-note (* bar 4) (nth pitches (mod bar (count pitches))) 3.5 0.85)))}))

(defn empty-bass-line [] {:notes []})

(defn notes-between
  "Notes whose `:at-beat` falls within `(prev-beat, cur-beat]`."
  [bass-line prev-beat cur-beat]
  (filterv #(and (> (:at-beat %) prev-beat) (<= (:at-beat %) cur-beat)) (:notes bass-line)))

;; ── per-track program + presets ─────────────────────────────────────────────

(defn audio-pattern [& {:keys [drums bass lead-arp pad-chord]}]
  {:drums drums :bass bass :lead-arp (vec (or lead-arp [])) :pad-chord (vec (or pad-chord []))})

(defn opener []
  (audio-pattern :drums (four-on-floor) :bass (root-pattern-c-minor)
                 :lead-arp [60 63 67 70] :pad-chord [60 63 67 70 74]))

(defn ballad-pattern []
  (audio-pattern :drums (ballad) :bass (root-pattern-c-minor)
                 :lead-arp [] :pad-chord [55 60 63 67]))

(defn encore []
  (audio-pattern :drums (pumping) :bass (root-pattern-c-minor)
                 :lead-arp [60 67 72 67 63 67 70 67] :pad-chord [60 63 67 70 75]))

;; ── misc ─────────────────────────────────────────────────────────────────

(defn midi->hz
  "MIDI note to Hz (12-TET, A4=440)."
  [midi]
  (* 440.0 (mathx/pow 2.0 (/ (- midi 69.0) 12.0))))

(defn bank-name
  "The sound-bank entry name for a drum slot."
  [slot]
  (case slot
    :kick "kick" :snare "snare" :closed-hat "closed-hat" :open-hat "open-hat"
    :clap "clap" :crash "crash" :tom "tom" :rim "rim"))

(defn sound-cue [wave freq to dur gain] {:wave wave :freq freq :to to :dur dur :gain gain})
