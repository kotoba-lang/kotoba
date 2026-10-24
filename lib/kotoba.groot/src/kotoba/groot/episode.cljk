(ns kotoba.groot.episode
  "Clean-room LeRobot-shaped episode / teleop record format for imitation
  fine-tuning. The schema is mirrored; the codec is plain EDN — no NVIDIA
  or HuggingFace dataset binary is required. Ported from
  kami-groot/src/episode.rs."
  (:refer-clojure :exclude [empty?]))

(defn episode-step
  "One recorded control tick: the observation state, the executed
  `[n-dof]` joint targets (chunk step 0), and the active instruction."
  [state action language]
  {:step/state    (vec state)
   :step/action   (vec action)
   :step/language language})

(defn episode
  "A teleop / imitation episode over one embodiment."
  [embodiment-name]
  {:episode/embodiment embodiment-name
   :episode/steps       []})

(defn push
  "Append a recorded step."
  [ep state action language]
  (update ep :episode/steps conj (episode-step state action language)))

(defn step-count
  [ep]
  (count (:episode/steps ep)))

(defn empty?
  [ep]
  (clojure.core/empty? (:episode/steps ep)))
