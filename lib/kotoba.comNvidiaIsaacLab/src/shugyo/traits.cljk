(ns shugyo.traits
  "Gym-style RL environment trait — 1:1 port of the original crate's
  `traits.rs`.

  Designed to mirror the `isaaclab.envs.ManagerBasedRLEnv` contract:
    - `reset!` returns the initial observation
    - `step!` returns `{:observation ... :reward ... :terminated? ... :truncated? ...}`

  Observation + action are flat numeric vectors. Vectorized envs implement
  `VecRLEnv` with `[num_envs, dim]` tensor I/O (env-major flat vectors, same
  layout as the original Rust `Vec<f32>` tensors).")

;; ---------------------------------------------------------------------------
;; StepResult
;; ---------------------------------------------------------------------------

(defn step-result
  "Construct a `StepResult` map — the CLJC analogue of the Rust
  `#[derive(Debug, Clone, PartialEq)] struct StepResult`."
  [observation reward terminated? truncated?]
  {:observation observation
   :reward reward
   :terminated? terminated?
   :truncated? truncated?})

;; ---------------------------------------------------------------------------
;; RLEnv — single-environment contract
;; ---------------------------------------------------------------------------

(defprotocol RLEnv
  "Single-environment gym contract."
  (reset! [this seed]
    "Reset to initial state with an optional random `seed` (or `nil`). Returns
    the initial observation vector.")
  (step! [this action]
    "Apply `action`, advance one decimation × dt of simulation, return a
    `StepResult` map.")
  (observation-dim [this]
    "Dimensionality of the flat observation vector.")
  (action-dim [this]
    "Dimensionality of the flat action vector."))

;; ---------------------------------------------------------------------------
;; VecRLEnv — vectorized (`[num_envs, dim]`) contract
;; ---------------------------------------------------------------------------

(defprotocol VecRLEnv
  "Vectorized RL environment contract — `num_envs` independent copies stepped
  in lockstep with `[num_envs, dim]` env-major flat tensors, mirroring Isaac
  Lab's `ManagerBasedRLEnv` batched API. A trainer written against this
  protocol runs over any env (Cartpole, joint-space reach, EE Cartesian
  reach, …)."
  (num-envs [this]
    "Number of parallel environments.")
  (observation-dim-per-env [this]
    "Per-env observation width (flat tensor is `num_envs * this`).")
  (action-dim-per-env [this]
    "Per-env action width (flat action tensor is `num_envs * this`).")
  (reset-all! [this base-seed]
    "Reset all envs (seeded, or `nil`). Returns the `[num_envs, obs_dim]`
    observation.")
  (step-all! [this actions]
    "Step all envs with a `[num_envs, action_dim]` flat action tensor. Returns
    a vector of `StepResult` maps, one per env.")
  (observations-flat [this]
    "Current `[num_envs, obs_dim]` observation without advancing."))

;; ---------------------------------------------------------------------------
;; Trainer-agnostic harness
;; ---------------------------------------------------------------------------

(defn run-zero-action-rollout
  "Reset, then step a zero-action policy for `steps` control ticks, returning
  the total reward summed over envs and ticks. A minimal harness proving any
  `VecRLEnv` composes with a generic training loop (real policies replace the
  zero action with their own)."
  [env steps seed]
  (reset-all! env seed)
  (let [action (vec (repeat (* (num-envs env) (action-dim-per-env env)) 0.0))]
    (loop [i 0 total 0.0]
      (if (= i steps)
        total
        (let [results (step-all! env action)]
          (recur (inc i) (+ total (reduce + 0.0 (map :reward results)))))))))
