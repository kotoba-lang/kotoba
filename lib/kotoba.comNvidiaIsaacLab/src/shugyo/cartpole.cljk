(ns shugyo.cartpole
  "CartpoleEnv + VectorizedCartpoleEnv — merged port of the original crate's
  `cartpole_env.rs` (single-env `RLEnv`) and `vectorized_env.rs`
  (`VectorizedCartpoleEnv`, `VecRLEnv`).

  Duck-typing note: the original constructors took Isaac Lab-style
  `scene.yaml` text + URDF text, parsed the URDF via `kami_articulated::
  parse_urdf`, and ran the dynamics through `kami_genesis::World` /
  `step_vectorized` / `step_vectorized_per_env`. `kami-articulated` is a real
  dependency of the original crate but its restoration (`kotoba-lang/
  kami-articulated`) is currently empty (mid-restoration, parallel work), and
  `kami-genesis` (the physics engine) was never restored as a kotoba-lang
  repo at all. Both are therefore duck-typed:

    1. Instead of URDF text + deriving `CartpoleConfig` from `<link>`/`<joint>`
       elements, this port accepts a `CartpoleConfig` map directly at
       construction (`shugyo.dr/cartpole-config`) — the numeric content the
       original derived from the URDF's `cart`/`pole_link` masses and
       `slider_to_cart` joint effort, just supplied explicitly rather than
       parsed. `shugyo.scene-cfg` documents the parallel scene.yaml -> EDN
       substitution.
    2. The classic cart-pole equations of motion (the actual physics
       `kami_genesis::step_vectorized`/`step_vectorized_per_env` would have
       run) are reimplemented here as pure math over a state map, generalized
       to take an arbitrary `CartpoleConfig` (mass/length/gravity/dt) rather
       than fixed constants — this generalizes the fixed-constant ODE that
       `kotoba-lang/cartpole-wasm` already ported from the same original
       dynamics, for consistency across the two sibling restorations.

  Layout matches the original: observation = `[x, x_dot, theta, theta_dot]`;
  action = `[force_on_cart]` (Newtons, applied directly — not rescaled by
  `force-mag`, matching `cartpole_env.rs::step`)."
  (:require [shugyo.lcg :as lcg]
            [shugyo.traits :as t]))

;; ---------------------------------------------------------------------------
;; Pure cart-pole ODE (classic Barto/Sutton/Anderson equations, parameterized
;; by a CartpoleConfig instead of fixed constants — see docstring above).
;; ---------------------------------------------------------------------------

(defn cartpole-init-state
  "Zero state map, the shape `CartpoleState::default()` produces."
  []
  {:x 0.0 :x-dot 0.0 :theta 0.0 :theta-dot 0.0})

(defn cartpole-physics-step
  "Advance `state` by one `dt` substep under `force` (Newtons), per
  `cartpole-cfg` (`:cart-mass :pole-mass :pole-half-length :gravity
  :force-mag :dt`). Pure function; semi-implicit-Euler-free (matches the
  original's explicit Euler integration exactly)."
  [{:keys [x x-dot theta theta-dot]} cartpole-cfg force]
  (let [{:keys [cart-mass pole-mass pole-half-length gravity dt]} cartpole-cfg
        total-mass (+ cart-mass pole-mass)
        polemass-length (* pole-mass pole-half-length)
        costheta #?(:clj (Math/cos theta) :cljs (js/Math.cos theta))
        sintheta #?(:clj (Math/sin theta) :cljs (js/Math.sin theta))
        temp (/ (+ force (* polemass-length theta-dot theta-dot sintheta)) total-mass)
        thetaacc (/ (- (* gravity sintheta) (* costheta temp))
                     (* pole-half-length
                        (- (/ 4.0 3.0) (/ (* pole-mass costheta costheta) total-mass))))
        xacc (- temp (/ (* polemass-length thetaacc costheta) total-mass))]
    {:x (+ x (* dt x-dot))
     :x-dot (+ x-dot (* dt xacc))
     :theta (+ theta (* dt theta-dot))
     :theta-dot (+ theta-dot (* dt thetaacc))}))

(defn- reset-state
  "Small random init within ±0.05 (Isaac Lab baseline). Returns [state rng']."
  [rng]
  (let [[x rng1] (lcg/next-f32-centered rng 0.05)
        [x-dot rng2] (lcg/next-f32-centered rng1 0.05)
        [theta rng3] (lcg/next-f32-centered rng2 0.05)
        [theta-dot rng4] (lcg/next-f32-centered rng3 0.05)]
    [{:x x :x-dot x-dot :theta theta :theta-dot theta-dot} rng4]))

(defn- observation-of [{:keys [x x-dot theta theta-dot]}]
  [x x-dot theta theta-dot])

(defn- pole-out-of-bounds? [scene theta]
  (let [[lo hi] (:bounds (:pole-out-of-bounds (:termination scene)))]
    (or (< theta lo) (> theta hi))))

(defn- cart-out-of-bounds? [scene x]
  (let [[lo hi] (:bounds (:cart-out-of-bounds (:termination scene)))]
    (or (< x lo) (> x hi))))

(defn- reward-of [scene {:keys [theta x-dot theta-dot]} terminated?]
  (let [r (:reward scene)]
    (+ (:alive r)
       (if terminated? (:terminating r) 0.0)
       (* (:pole-pos-penalty r) theta theta)
       (* (:cart-vel-penalty r) x-dot x-dot)
       (* (:pole-vel-penalty r) theta-dot theta-dot))))

(defn- max-episode-steps* [scene dt]
  #?(:clj (Math/round (/ (:max-episode-length-s (:time-out (:termination scene))) dt))
     :cljs (js/Math.round (/ (:max-episode-length-s (:time-out (:termination scene))) dt))))

;; ---------------------------------------------------------------------------
;; CartpoleEnv — single env, `RLEnv`
;; ---------------------------------------------------------------------------

(deftype CartpoleEnvT [scene cartpole-cfg state-atom steps-atom rng-atom max-episode-steps]
  t/RLEnv
  (reset! [_ seed]
    (when (some? seed)
      (clojure.core/reset! rng-atom (lcg/lcg-new seed)))
    (let [[state rng'] (reset-state @rng-atom)]
      (clojure.core/reset! state-atom state)
      (clojure.core/reset! rng-atom rng')
      (clojure.core/reset! steps-atom 0)
      (observation-of state)))
  (step! [_ action]
    (assert (= (count action) 1) "Cartpole action is 1-dim (force on cart)")
    (let [force (first action)
          decimation (max (long (:decimation (:scene scene))) 1)]
      (dotimes [_ decimation]
        (clojure.core/swap! state-atom cartpole-physics-step cartpole-cfg force))
      (clojure.core/swap! steps-atom + decimation))
    (let [state @state-atom
          obs (observation-of state)
          terminated? (or (pole-out-of-bounds? scene (:theta state))
                           (cart-out-of-bounds? scene (:x state)))
          truncated? (>= @steps-atom max-episode-steps)
          reward (reward-of scene state terminated?)]
      (t/step-result obs reward terminated? truncated?)))
  (observation-dim [_] 4)
  (action-dim [_] 1))

(defn env-state
  "Current state map of a single-env `CartpoleEnvT` (test/diagnostic
  accessor, mirrors direct field access used by the original Rust tests via
  `observation_inner`)."
  [^CartpoleEnvT env]
  @(.-state-atom env))

(defn cartpole-env-new
  "Build a single-env CartpoleEnv from a scene EDN map (`shugyo.scene-cfg`)
  and a `CartpoleConfig` map (`shugyo.dr/cartpole-config`) — see the namespace
  docstring for why this takes a config directly instead of URDF text."
  [scene cartpole-cfg]
  (->CartpoleEnvT scene cartpole-cfg
                   (atom (cartpole-init-state))
                   (atom 0)
                   (atom (lcg/lcg-new 0))
                   (max-episode-steps* scene (:dt cartpole-cfg))))

;; ---------------------------------------------------------------------------
;; VectorizedCartpoleEnv — N parallel envs, `VecRLEnv`
;; ---------------------------------------------------------------------------

(deftype VectorizedCartpoleEnvT
    [scene num-envs-n
     states-atom rngs-atom steps-atom
     cartpole-cfg per-env-cfgs-atom
     decimation max-episode-control-steps]
  t/VecRLEnv
  (num-envs [_] num-envs-n)
  (observation-dim-per-env [_] 4)
  (action-dim-per-env [_] 1)
  (reset-all! [this base-seed]
    (when (some? base-seed)
      (clojure.core/reset! rngs-atom (mapv #(lcg/lcg-new (+ base-seed %)) (range num-envs-n))))
    (let [pairs (mapv reset-state @rngs-atom)]
      (clojure.core/reset! states-atom (mapv first pairs))
      (clojure.core/reset! rngs-atom (mapv second pairs))
      (clojure.core/reset! steps-atom (vec (repeat num-envs-n 0))))
    (t/observations-flat this))
  (step-all! [_ actions]
    (assert (= (count actions) num-envs-n))
    (let [per-env-cfgs @per-env-cfgs-atom]
      (dotimes [_ decimation]
        (clojure.core/swap!
         states-atom
         (fn [states]
           (mapv (fn [i state]
                   (let [cfg (if per-env-cfgs (nth per-env-cfgs i) cartpole-cfg)]
                     (cartpole-physics-step state cfg (nth actions i))))
                 (range num-envs-n) states)))))
    (clojure.core/swap! steps-atom #(mapv (fn [s] (+ s decimation)) %))
    (let [states @states-atom
          steps @steps-atom
          max-total (* max-episode-control-steps decimation)]
      (mapv (fn [i state]
              (let [terminated? (or (pole-out-of-bounds? scene (:theta state))
                                     (cart-out-of-bounds? scene (:x state)))
                    truncated? (>= (nth steps i) max-total)
                    reward (reward-of scene state terminated?)]
                (t/step-result (observation-of state) reward terminated? truncated?)))
            (range num-envs-n) states)))
  (observations-flat [_]
    (vec (mapcat observation-of @states-atom))))

(defn vectorized-cartpole-env-new
  "Build a `num-envs`-way VectorizedCartpoleEnv from a scene EDN map and a
  shared `CartpoleConfig` (see `cartpole-env-new` for the URDF-duck-typing
  rationale)."
  [num-envs scene cartpole-cfg]
  (when (zero? num-envs) (throw (ex-info "num-envs must be > 0" {})))
  (let [dt (:dt cartpole-cfg)
        total-physics-steps (max-episode-steps* scene dt)
        decimation (max (long (:decimation (:scene scene))) 1)
        max-episode-control-steps (quot total-physics-steps decimation)]
    (->VectorizedCartpoleEnvT
     scene num-envs
     (atom (vec (repeat num-envs (cartpole-init-state))))
     (atom (mapv #(lcg/lcg-new %) (range num-envs)))
     (atom (vec (repeat num-envs 0)))
     cartpole-cfg
     (atom nil)
     decimation
     max-episode-control-steps)))

;; Extra (non-protocol) operations mirroring the Rust inherent-impl surface.

(defn set-per-env-configs!
  "Install per-env physics configs (domain randomisation). `cfgs` must have
  length `num-envs`."
  [^VectorizedCartpoleEnvT env cfgs]
  (assert (= (count cfgs) (.-num-envs-n env)))
  (clojure.core/reset! (.-per-env-cfgs-atom env) (vec cfgs)))

(defn clear-per-env-configs!
  "Drop per-env DR and revert to the shared cartpole-cfg."
  [^VectorizedCartpoleEnvT env]
  (clojure.core/reset! (.-per-env-cfgs-atom env) nil))

(defn per-env-configs
  "Access the per-env cfg slice (for diagnostic/sampling), or nil."
  [^VectorizedCartpoleEnvT env]
  @(.-per-env-cfgs-atom env))

(defn base-cfg
  "Shared base cfg accessor (used by DR builders)."
  [^VectorizedCartpoleEnvT env]
  (.-cartpole-cfg env))

(defn reset-envs!
  "Reset specific envs by index. Useful for auto-reset after termination."
  [^VectorizedCartpoleEnvT env env-indices]
  (let [rngs-atom (.-rngs-atom env)
        states-atom (.-states-atom env)
        steps-atom (.-steps-atom env)
        n (.-num-envs-n env)]
    (doseq [i env-indices]
      (when (< i n)
        (let [[state rng'] (reset-state (nth @rngs-atom i))]
          (clojure.core/swap! states-atom assoc i state)
          (clojure.core/swap! rngs-atom assoc i rng')
          (clojure.core/swap! steps-atom assoc i 0))))))

(defn env-states
  "Raw per-env state maps (test/diagnostic accessor, mirrors direct field
  access used by the original Rust tests, e.g. `env.states[0].theta = 1.0`)."
  [^VectorizedCartpoleEnvT env]
  @(.-states-atom env))

(defn set-env-state!
  "Overwrite env `i`'s state map directly (test/diagnostic accessor)."
  [^VectorizedCartpoleEnvT env i state]
  (clojure.core/swap! (.-states-atom env) assoc i state))
