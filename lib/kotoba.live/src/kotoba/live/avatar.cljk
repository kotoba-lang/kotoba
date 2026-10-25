(ns kotoba.live.avatar
  "How a VRM avatar is bound to the performer (`:dance/avatar`), and the
  show->expression / show->mouth drives that animate its face. The actual
  mesh/skinning load is the host's job; this module only resolves the
  *intent* (which avatar, where it stands, which features) and the
  deterministic per-frame signal->weight math."
  (:require [kotoba.live.mathx :as mathx]))

(def expr-sources #{:cheer :beat :blink})
(def vowels #{:a :i :u :e :o})

(defn vrm-expr
  "The VRM expression name a vowel drives: a->aa i->ih u->ou e->ee o->oh."
  [vowel]
  (case vowel :a "aa" :i "ih" :u "ou" :e "ee" :o "oh"))

(defn vowel-by-name [s]
  (case s
    ("a" "aa") :a
    ("i" "ih") :i
    ("u" "ou") :u
    ("e" "ee") :e
    ("o" "oh") :o
    nil))

(defn phoneme [at-beat vowel dur] {:at-beat at-beat :vowel vowel :dur dur})

(defn new-voice-line [phonemes] {:phonemes (vec phonemes)})

(defn vowel-weight
  "The active vowel's `[vrm-expr-name weight]` at a continuous `beat`, with a
  short attack/release so syllables open and close. `nil` between
  syllables (mouth closed)."
  [voice beat]
  (let [phonemes (:phonemes voice)]
    (when (seq phonemes)
      (let [span (reduce max 0.0 (map #(+ (:at-beat %) (:dur %)) phonemes))
            beat (if (> span 1e-3) (- beat (* span (mathx/floor (/ beat span)))) beat)]
        (some (fn [p]
                (when (and (>= beat (:at-beat p)) (< beat (+ (:at-beat p) (:dur p))))
                  (let [t (- beat (:at-beat p))
                        edge (min 0.15 (* (:dur p) 0.25))
                        w (cond
                            (<= edge 0.0) 1.0
                            (< t edge) (/ t edge)
                            (> t (- (:dur p) edge)) (/ (- (:dur p) t) edge)
                            :else 1.0)]
                    [(vrm-expr (:vowel p)) (max 0.0 (min 1.0 w))])))
              phonemes)))))

(defn default-expressions []
  [{:name "happy" :source :cheer :gain 0.025}
   {:name "aa" :source :beat :gain 1.0}
   {:name "blink" :source :blink :gain 1.0}])

(defn default-binding []
  {:vrm "" :home nil :scale 1.0 :look-at true :spring-bones true :clip nil
   :spring nil :look-at-target nil :expressions (default-expressions) :voice nil :vmd nil})

(defn expression-weights
  "Resolve every drive in `avatar` against this frame's show signals ->
  `{name weight}` in [0,1] (`name` is the drive's string name). Zero-weight
  entries are omitted."
  [avatar cheer-loudness beat-frac time]
  (let [tau mathx/tau]
    (into {}
          (keep (fn [d]
                  (let [w (case (:source d)
                            :cheer (max 0.0 (min 1.0 (* cheer-loudness (:gain d))))
                            :beat (max 0.0 (min 1.0 (* (- 1.0 (mathx/cos (* beat-frac tau))) 0.5 (:gain d))))
                            :blink (let [m (- time (* 3.0 (mathx/floor (/ time 3.0))))]
                                     (if (< m 0.12)
                                       (max 0.0 (min 1.0 (- 1.0 (min 1.0 (mathx/abs (- (/ m 0.06) 1.0))))))
                                       0.0))
                            0.0)]
                    (when (pos? w) [(:name d) w])))
                (:expressions avatar)))))
