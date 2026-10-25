(ns kotoba.live.lighting
  "Lighting designer.

  Stage lighting is a function of the beat. Fixtures live at fixed truss
  positions; the designer owns a stack of lighting cues and per-tick resolves
  a `LightingFrame` (color + intensity + aim direction per fixture) that the
  renderer consumes."
  (:require [kotoba.live.mathx :as mathx]))

(def fixtures [:front-par :back-par :spot :blinder :laser :strobe])

(defn new-designer [] {:cues [] :laser-phase 0.0})

(defn push
  "Push a cue `{:fixture :color :intensity :envelope :bars}` starting at
  `start-bar`."
  [designer cue start-bar]
  (update designer :cues conj [cue start-bar]))

(defn on-event
  "Advance internal state from a beat-grid event (see `kotoba.live.beat`).
  The laser sweep direction is driven deterministically by eighth-note
  events so every viewer sees the same beam direction."
  [designer ev]
  (if (= :eighth (:type ev))
    (assoc designer :laser-phase (mod (* (:eighth-index ev) 0.37) mathx/tau))
    designer))

(defn prune
  "Drop cues expired as of `current-bar`."
  [designer current-bar]
  (update designer :cues
          (fn [cues] (vec (filter (fn [[c start]] (< current-bar (+ start (:bars c)))) cues)))))

(defn- envelope-amp [env phase start-bar bars]
  (case (:kind env)
    :hold 1.0
    :pulse (mathx/exp (* (- (:decay env)) (:beat-frac phase)))
    :breathe (let [t (* (:bar-frac phase) mathx/tau)] (+ 0.5 (* 0.5 (mathx/sin t))))
    :strobe (let [frac (mod (* (:bar-frac phase) 8.0) 1.0)] (if (< frac (:duty env)) 1.0 0.0))
    :ramp (let [total (max 1 bars)
                elapsed (+ (max 0 (- (:bar phase) start-bar)) (:bar-frac phase))]
            (max 0.0 (min 1.0 (/ elapsed total))))
    1.0))

(defn- default-aim [fixture laser-phase]
  (case fixture
    :front-par [0.0 -0.2 -1.0]
    :back-par [0.0 -0.2 1.0]
    :spot [0.0 -1.0 0.0]
    :blinder [0.0 0.0 -1.0]
    :strobe [0.0 -0.5 -1.0]
    :laser (let [s (mathx/sin laser-phase) c (mathx/cos laser-phase)]
             [(* s 0.7) -0.6 (- c)])
    [0.0 -1.0 0.0]))

(defn resolve-frames
  "Resolve to one `LightingFrame` per fixture for `phase`. The latest
  matching cue wins; fixtures with no active cue get a dim ambient."
  [designer phase]
  (let [laser-phase (:laser-phase designer)]
    (mapv
     (fn [fx]
       (let [cue (->> (:cues designer)
                       reverse
                       (filter (fn [[c start]]
                                 (and (= (:fixture c) fx)
                                      (>= (:bar phase) start)
                                      (< (:bar phase) (+ start (:bars c))))))
                       first)]
         (if (nil? cue)
           {:fixture fx :color [0.05 0.05 0.07] :intensity 0.05 :aim (default-aim fx laser-phase)}
           (let [[c start] cue
                 amp (envelope-amp (:envelope c) phase start (:bars c))]
             {:fixture fx :color (:color c) :intensity (* (:intensity c) amp)
              :aim (default-aim fx laser-phase)}))))
     fixtures)))
