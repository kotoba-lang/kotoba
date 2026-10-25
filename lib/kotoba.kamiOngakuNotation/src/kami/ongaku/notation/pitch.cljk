(ns kami.ongaku.notation.pitch
  "Pitch model: MIDI note number <-> scientific pitch notation <-> step/
  alter/octave (the MusicXML shape). :pitch/step + :pitch/alter is the
  spelling of record (kept separate from enharmonic equivalence); MIDI is
  a derived value, never the source of truth for a written score.

  Portable .cljc — no platform-specific calls."
  (:require [kotoba.lang.text :as str]))

(def step->semitone {:C 0 :D 2 :E 4 :F 5 :G 7 :A 9 :B 11})
(def steps (vec (keys step->semitone)))

(defn valid-step? [s] (contains? step->semitone s))
(defn valid-alter? [a] (and (integer? a) (<= -2 a 2)))
(defn valid-octave? [o] (and (integer? o) (<= 0 o 9)))

(defn pitch
  "Construct a pitch record from raw {:step :alter :octave} (alter defaults
  to 0/natural). Returns nil when any field is missing or out of range."
  [{:keys [step alter octave] :or {alter 0}}]
  (when (and (valid-step? step) (valid-alter? alter) (valid-octave? octave))
    {:pitch/step step :pitch/alter alter :pitch/octave octave}))

(defn coerce
  "Accept either a raw {:step :alter :octave} map or an already-built
  namespaced pitch record ({:pitch/step ...}); returns a normalized
  namespaced pitch, or nil if invalid. Lets callers that already hold a
  pitch record re-validate/pass it through without re-keying by hand."
  [p]
  (if (contains? p :pitch/step)
    (pitch {:step (:pitch/step p) :alter (:pitch/alter p 0) :octave (:pitch/octave p)})
    (pitch p)))

(defn pitch->midi
  [{:pitch/keys [step alter octave]}]
  (+ (* 12 (inc octave)) (step->semitone step) alter))

;; Default spelling table for the MIDI -> pitch direction (sharps; no
;; double-accidentals produced by this direction). Scores authored directly
;; as pitch records keep whatever spelling the caller chose.
(def ^:private pitch-class->default-spelling
  {0 [:C 0] 1 [:C 1] 2 [:D 0] 3 [:D 1] 4 [:E 0] 5 [:F 0] 6 [:F 1]
   7 [:G 0] 8 [:G 1] 9 [:A 0] 10 [:A 1] 11 [:B 0]})

(defn midi->pitch
  [midi]
  (when (and (integer? midi) (<= 0 midi 127))
    (let [[step alter] (pitch-class->default-spelling (mod midi 12))
          octave (dec (quot midi 12))]
      {:pitch/step step :pitch/alter alter :pitch/octave octave})))

(def ^:private alter->suffix {-2 "bb" -1 "b" 0 "" 1 "#" 2 "x"})
(def ^:private suffix->alter {"bb" -2 "b" -1 "" 0 "#" 1 "x" 2})

(defn pitch->scientific
  "{:pitch/step :C :pitch/alter 1 :pitch/octave 4} => \"C#4\""
  [{:pitch/keys [step alter octave]}]
  (str (name step) (alter->suffix alter) octave))

(defn- parse-int [s]
  #?(:clj (Long/parseLong s)
     :cljs (js/parseInt s 10)))

(defn scientific->pitch
  "Parse \"C#4\", \"Bb3\", \"Fx5\", \"C4\" (case-insensitive step letter)."
  [s]
  (when-let [[_ step-str acc-str octave-str]
             (re-matches #"(?i)([A-G])(bb|b|#|x)?(-?\d+)" s)]
    (pitch {:step (keyword (str/upper step-str))
            :alter (get suffix->alter (or acc-str ""))
            :octave (parse-int octave-str)})))
