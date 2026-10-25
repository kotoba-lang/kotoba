(ns kotoba.live.performer
  "Performer — the dancer on stage.

  A small library of dance moves, each a deterministic pose function
  `f(beat-frac, bar-frac) -> pose`. The actual VRM skeleton drive is
  host-side; this module emits target poses a renderer blends into the rig."
  (:require [kotoba.live.mathx :as mathx]
            [kotoba.live.vec3 :as v3]))

(def dance-moves
  #{:idle :four-on-floor :wota :kpop-point :shuffle :hold :bounce :sway :spin
    :headbang :clap})

(defn rest-pose []
  {:root-translation v3/zero :root-yaw 0.0 :vertical-bob 0.0 :arms-up 0.0 :spine-sway 0.0})

(defn move-by-name
  "Look up a dance move by name (string or keyword). Unknown -> `:idle`."
  [name]
  (let [k (keyword (clojure.core/name name))]
    (if (contains? dance-moves k) k :idle)))

(defn pose-at
  "The pose for dance move `move` at `beat-frac`/`bar-frac` (each clamped to
  [0,1] where applicable). Pure function of the move + phase."
  [move beat-frac bar-frac]
  (let [bf (max 0.0 (min 1.0 beat-frac))
        tau mathx/tau
        sin mathx/sin
        cos mathx/cos
        abs mathx/abs
        pow mathx/pow]
    (case move
      :idle (assoc (rest-pose) :vertical-bob (* 0.04 (sin (* bf tau))))
      :four-on-floor (assoc (rest-pose)
                             :vertical-bob (* -0.12 (- 1.0 (pow (- 1.0 bf) 2)))
                             :arms-up 0.2)
      :wota (assoc (rest-pose)
                    :vertical-bob (* 0.05 (sin (* bar-frac tau 2.0)))
                    :arms-up (if (< bar-frac 0.25) 0.95 0.4)
                    :root-translation [(* 0.15 (sin (* bar-frac tau))) 0.0 0.0])
      :kpop-point (let [arms (if (< bf 0.4) 0.9 0.4)
                        yaw (* 0.3 (sin (* bar-frac tau)))]
                    (assoc (rest-pose)
                           :arms-up arms
                           :root-yaw yaw
                           :spine-sway (* 0.05 (cos (* bf tau)))))
      :shuffle (assoc (rest-pose)
                       :root-translation [(* 0.4 (sin (* bar-frac tau))) 0.0 0.0]
                       :vertical-bob (* 0.03 (sin (* bf tau 2.0))))
      :hold (rest-pose)
      :bounce (assoc (rest-pose)
                      :vertical-bob (* -0.12 (abs (sin (* bf mathx/pi))))
                      :arms-up 0.3)
      :sway (assoc (rest-pose)
                    :root-translation [(* 0.22 (sin (* bar-frac tau))) 0.0 0.0]
                    :spine-sway (* 0.16 (sin (* bar-frac tau)))
                    :vertical-bob (* 0.03 (sin (* bf tau))))
      :spin (assoc (rest-pose)
                    :root-yaw (* bar-frac tau)
                    :arms-up 0.5
                    :vertical-bob (* 0.04 (sin (* bf tau))))
      :headbang (assoc (rest-pose)
                        :vertical-bob (* -0.16 (- 1.0 (pow (- 1.0 bf) 3)))
                        :arms-up 0.15)
      :clap (assoc (rest-pose)
                    :arms-up (+ 0.5 (* 0.45 (abs (sin (* bf tau 2.0)))))
                    :vertical-bob (* 0.03 (sin (* bf tau))))
      (recur :idle beat-frac bar-frac))))

(defn new-performer [name home]
  {:name name :current :idle :home home})

(defn set-move [performer move] (assoc performer :current move))

(defn pose
  "Resolve the pose for a phase; adds the performer's `:home` translation."
  [performer beat-frac bar-frac]
  (let [p (pose-at (:current performer) beat-frac bar-frac)]
    (update p :root-translation v3/v+ (:home performer))))
