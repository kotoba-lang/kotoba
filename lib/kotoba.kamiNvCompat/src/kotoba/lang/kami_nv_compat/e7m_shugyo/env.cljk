(ns kotoba.lang.kami-nv-compat.e7m-shugyo.env
  "e7m-shugyo — ManagerBasedRLEnv (Isaac Lab classic Cartpole). Portable
  .cljc port of src/e7m-shugyo/env.ts. Wave 34 (closes e7m-shugyo).

  Mirrors isaaclab.envs.ManagerBasedRLEnv: a Gym-style RL environment
  driven by declarative managers. make-env takes cfg overrides plus an
  optional bundle of Observation / Reward / Termination / Event managers
  (already-constructed via managers.cljc — a simplification vs the TS
  source, which also accepts raw term-group maps and auto-wraps them by
  instanceof-checking; construct via managers.cljc directly if a raw
  group needs wrapping). reset-all!/step-all! run the standard Isaac Lab
  loop — apply action -> decimated physics -> observations / rewards /
  terminations.

  Vectorized over cfg's :num-envs: per-env states (atoms, one per slot)
  are stepped in lockstep, with per-env auto-reset of done envs (the
  Isaac Lab vectorized convention).

  ADR-2605261800 SD6 / D10.4 e7m-shugyo."
  (:require [kotoba.lang.kami-nv-compat.utsushimi.sampler :as sampler]
            [kotoba.lang.kami-nv-compat.e7m-shugyo.managers :as mgr]
            [kotoba.lang.kami-nv-compat.e7m-shugyo.cartpole :as cp]))

;; StepResult {:observations :reward :terminated :truncated :info}
;; ManagerBundle {:observations? :rewards? :terminations? :events?}
;; Env {:cfg :max-steps :obs-mgr :rew-mgr :term-mgr :event-mgr :slots}

(defn make-env
  "A ManagerBasedRLEnv. `cfg-overrides` merges into default-cartpole-cfg."
  ([] (make-env {} {}))
  ([cfg-overrides] (make-env cfg-overrides {}))
  ([cfg-overrides bundle]
   (let [cfg (cp/default-cartpole-cfg cfg-overrides)
         max-steps (long (Math/round (double (/ (:max-episode-length-s cfg) (:physics-dt cfg)))))
         obs-mgr (or (:observations bundle)
                     (mgr/make-observation-manager {:policy (mgr/make-obs-group (cp/cartpole-obs-terms))}))
         rew-mgr (or (:rewards bundle)
                     (mgr/make-reward-manager (mgr/make-rew-group (cp/cartpole-rew-terms cfg))))
         term-mgr (or (:terminations bundle) (mgr/make-termination-manager (cp/cartpole-termination-terms)))
         event-mgr (or (:events bundle) (mgr/make-event-manager (cp/cartpole-event-terms)))
         num-envs (max 1 (:num-envs cfg))
         slots (mapv (fn [i]
                       (atom {:state (cp/zero-state) :last-action [0.0] :terminated false
                              :truncated false :step-count 0 :max-steps max-steps :cfg cfg
                              :rng (sampler/make-sampler i)}))
                     (range num-envs))
         env {:cfg cfg :max-steps max-steps :obs-mgr obs-mgr :rew-mgr rew-mgr
              :term-mgr term-mgr :event-mgr event-mgr :slots slots}]
     (mgr/event-manager-apply! event-mgr (slots 0) :startup)
     env)))

(defn num-envs [env] (max 1 (:num-envs (:cfg env))))
(defn observation-manager [env] (:obs-mgr env))
(defn reward-manager [env] (:rew-mgr env))

(defn env-state
  "Single-env state view (slot 0)."
  [env]
  (:state @((:slots env) 0)))

;; ── vectorized API ─────────────────────────────────────────────────────

(defn reset-all!
  "Reset all envs (optionally re-seeding env i with seed+i). Returns the
  per-env observation maps."
  ([env] (reset-all! env nil))
  ([env seed]
   (mapv (fn [i slot]
           (swap! slot (fn [s]
                         (let [s2 (if seed (assoc s :rng (sampler/make-sampler (+ seed i))) s)]
                           (assoc s2 :state (cp/reset-state (:rng s2) (:cfg s2))
                                  :last-action [0.0] :terminated false :truncated false :step-count 0))))
           (mgr/event-manager-apply! (:event-mgr env) slot :reset)
           (mgr/obs-manager-compute (:obs-mgr env) slot))
         (range) (:slots env))))

(defn- step-slot!
  [env slot action]
  (let [cfg (:cfg @slot)
        raw (or (first action) 0.0)
        force (max (- (:force-mag cfg)) (min (:force-mag cfg) (* raw (:force-mag cfg))))]
    (swap! slot assoc :last-action (vec action))
    (dotimes [_ (:decimation cfg)]
      (swap! slot update :state #(cp/cartpole-step % force cfg)))
    (swap! slot update :step-count inc)
    (let [term (mgr/termination-manager-compute (:term-mgr env) slot)]
      (swap! slot assoc :terminated (:terminated term) :truncated (:truncated term))
      (let [reward (mgr/reward-manager-compute! (:rew-mgr env) slot)
            observations0 (mgr/obs-manager-compute (:obs-mgr env) slot)]
        (if (or (:terminated term) (:truncated term))
          (do
            (swap! slot (fn [s] (assoc s :state (cp/reset-state (:rng s) (:cfg s))
                                       :last-action [0.0] :step-count 0 :terminated false :truncated false)))
            (mgr/event-manager-apply! (:event-mgr env) slot :reset)
            {:observations (mgr/obs-manager-compute (:obs-mgr env) slot)
             :reward reward :terminated (:terminated term) :truncated (:truncated term) :info (:info term)})
          {:observations observations0
           :reward reward :terminated (:terminated term) :truncated (:truncated term) :info (:info term)})))))

(defn step-all!
  "Step all envs with per-env action vectors. Done envs auto-reset and the
  returned observation is the post-reset observation (Isaac Lab
  convention), while :terminated/:truncated flag the transition that
  just ended."
  [env actions]
  (mapv (fn [i slot] (step-slot! env slot (or (nth actions i nil) [0.0])))
        (range) (:slots env)))

;; ── single-env convenience ───────────────────────────────────────────────

(defn reset-env!
  ([env] (reset-env! env nil))
  ([env seed] (first (reset-all! env seed))))

(defn step-env!
  [env action]
  (step-slot! env ((:slots env) 0) action))
