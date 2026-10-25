(ns shugyo.policy
  "Minimal gradient-free policy + trainer over any `VecRLEnv` — 1:1 port of
  the original crate's `policy.rs`.

  The point: kami-shugyo is an RL *training* framework, so it must be able to
  learn a policy, not just simulate. This provides a goal-conditioned
  `LinearPolicy` (`a = W·obs + b`) and `random-search` — a hill-climbing /
  Augmented-Random-Search-lite optimizer that perturbs the policy,
  re-evaluates the vectorized return under a *fixed* goal distribution (same
  eval seed), and keeps improvements. No autodiff, no external deps;
  deterministic given a seed.

  Dependency-direction note: the original `policy.rs` imported `Lcg` from
  `reach_env` (a slightly awkward cross-module dependency for a shared RNG).
  This port puts the shared LCG in `shugyo.lcg` (module 1) instead, so
  `shugyo.policy` has *zero* dependency on `shugyo.reach` — cleaner than the
  original. `shugyo.reach` is only required by this namespace's *tests*
  (`policy_test.cljc`), matching the original's actual usage: the policy
  tests build a `VectorizedReachEnv` to exercise `evaluate`/`random-search`
  against a concrete env."
  (:require [shugyo.lcg :as lcg]
            [shugyo.traits :as t]))

;; ---------------------------------------------------------------------------
;; LinearPolicy
;; ---------------------------------------------------------------------------

(defn zeros
  "All-zero affine policy `action = W·obs + b`, row-major `w[a*obs-dim + o]`."
  [obs-dim act-dim]
  {:obs-dim obs-dim
   :act-dim act-dim
   :w (vec (repeat (* obs-dim act-dim) 0.0))
   :b (vec (repeat act-dim 0.0))})

(defn act-batch
  "Map a `[num-envs, obs-dim]` observation tensor to a `[num-envs, act-dim]`
  action tensor (env-major flat)."
  [{:keys [obs-dim act-dim w b]} obs num-envs]
  (vec
   (for [e (range num-envs)
         a (range act-dim)]
     (let [o-base (* e obs-dim)
           w-base (* a obs-dim)]
       (loop [i 0 acc (nth b a)]
         (if (= i obs-dim)
           acc
           (recur (inc i) (+ acc (* (nth w (+ w-base i)) (nth obs (+ o-base i)))))))))))

(defn- gaussian
  "Standard-normal sample from the uniform LCG via Box-Muller. Returns
  `[value state']`."
  [state]
  (let [[s1 state1] (lcg/next-signed state)
        [s2 state2] (lcg/next-signed state1)
        u1 (max (+ (* s1 0.5) 0.5) 1e-6)
        u2 (+ (* s2 0.5) 0.5)
        pi #?(:clj Math/PI :cljs js/Math.PI)
        v (* #?(:clj (Math/sqrt (* -2.0 (Math/log u1))) :cljs (js/Math.sqrt (* -2.0 (js/Math.log u1))))
             #?(:clj (Math/cos (* 2.0 pi u2)) :cljs (js/Math.cos (* 2.0 pi u2))))]
    [v state2]))

(defn- perturbed
  "A gaussian-perturbed copy of `policy` (Box-Muller noise scaled by
  `sigma`). Returns `[policy' state']`."
  [{:keys [w b] :as policy} state sigma]
  (let [[w' state1] (reduce (fn [[acc st] x]
                               (let [[g st'] (gaussian st)]
                                 [(conj acc (+ x (* sigma g))) st']))
                             [[] state] w)
        [b' state2] (reduce (fn [[acc st] x]
                               (let [[g st'] (gaussian st)]
                                 [(conj acc (+ x (* sigma g))) st']))
                             [[] state1] b)]
    [(assoc policy :w w' :b b') state2]))

;; ---------------------------------------------------------------------------
;; rescale-to-limits
;; ---------------------------------------------------------------------------

(defn rescale-to-limits
  "Map a `[num-envs, n-dof]` normalized action tensor in `[-1, 1]` to joint
  targets in `[lower, upper]` per DOF (the standard Isaac Lab action
  pipeline). `limits` is `[n-dof]` of `[lower upper]`. A DOF with a
  non-finite limit (unbounded joint) passes its action through unchanged."
  [normalized limits num-envs]
  (let [ndof (count limits)]
    (vec
     (for [e (range num-envs)
           d (range ndof)]
       (let [a (max -1.0 (min 1.0 (nth normalized (+ (* e ndof) d))))
             [lo hi] (nth limits d)]
         (if (and #?(:clj (Double/isFinite lo) :cljs (js/isFinite lo))
                  #?(:clj (Double/isFinite hi) :cljs (js/isFinite hi)))
           (+ lo (* (+ (* a 0.5) 0.5) (- hi lo)))
           (nth normalized (+ (* e ndof) d))))))))

;; ---------------------------------------------------------------------------
;; evaluate / random-search
;; ---------------------------------------------------------------------------

(defn evaluate
  "Roll out `policy` on `env` for `episode-len` control ticks and return the
  total reward summed over envs and ticks (higher = better). `seed` fixes the
  per-env goal distribution so two policies are compared on the same task."
  [env policy episode-len seed]
  (let [obs0 (t/reset-all! env seed)
        n (t/num-envs env)]
    (loop [i 0 obs obs0 total 0.0]
      (if (= i episode-len)
        total
        (let [action (act-batch policy obs n)
              results (t/step-all! env action)
              total' (+ total (reduce + 0.0 (map :reward results)))
              obs' (vec (mapcat :observation results))]
          (recur (inc i) obs' total'))))))

(defn random-search
  "Hill-climbing random search (ARS-lite): start from `init`, perturb, keep
  the candidate if it scores higher on the fixed-seed task, repeat for
  `iters`. Returns `[best-policy history]` where `history` has `iters + 1`
  entries, monotone non-decreasing."
  [env init iters sigma episode-len seed]
  (let [eval-seed (bit-xor seed 0x51515151)
        best0 init
        best-score0 (evaluate env best0 episode-len eval-seed)]
    (loop [i 0 best best0 best-score best-score0 rng-state (lcg/lcg-new seed) history [best-score0]]
      (if (= i iters)
        [best history]
        (let [[cand rng-state'] (perturbed best rng-state sigma)
              score (evaluate env cand episode-len eval-seed)]
          (if (> score best-score)
            (recur (inc i) cand score rng-state' (conj history score))
            (recur (inc i) best best-score rng-state' (conj history best-score))))))))
