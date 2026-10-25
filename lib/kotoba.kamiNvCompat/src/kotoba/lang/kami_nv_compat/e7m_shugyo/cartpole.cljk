(ns kotoba.lang.kami-nv-compat.e7m-shugyo.cartpole
  "e7m-shugyo — clean-room cart-pole dynamics + MDP terms (Isaac Lab
  classic). Portable .cljc port of src/e7m-shugyo/cartpole.ts. Wave 34.

  Reproduces the Isaac Lab classic Cartpole task: cart-pole ODE
  integration, CartpoleEnvCfg, LCG-seeded reset (the same 64-bit LCG as
  utsushimi, so seeds are reproducible across the SDK), and the MDP term
  functions the managers consume (observations / rewards / terminations /
  events).

  State: x (cart position), x-dot, theta (pole angle from upright, 0 =
  up), theta-dot. Dynamics are the textbook Barto-Sutton cart-pole; no
  Isaac Lab source/weights are used.

  MDP term functions take [env params] where `env` is an atom holding a
  CartpoleEnvView map (see env.cljc) — reading terms deref it,
  reset-joints-by-offset! (an event term) swap!s it.

  ADR-2605261800 SD6 / D10.4 e7m-shugyo."
  (:require [kotoba.lang.kami-nv-compat.utsushimi.sampler :as sampler]))

;; CartpoleState {:x :x-dot :theta :theta-dot}

(defn zero-state [] {:x 0.0 :x-dot 0.0 :theta 0.0 :theta-dot 0.0})

;; CartpoleEnvCfg {:num-envs :physics-dt :decimation :gravity :cart-mass
;;                 :pole-mass :pole-length :force-mag :alive :terminating
;;                 :pole-pos-penalty :cart-vel-penalty :pole-vel-penalty
;;                 :max-episode-length-s :pole-bound :cart-bound :reset-noise}

(defn default-cartpole-cfg
  ([] (default-cartpole-cfg {}))
  ([over]
   (merge
    {:num-envs 1 :physics-dt (/ 1.0 60.0) :decimation 2 :gravity 9.81
     :cart-mass 1.0 :pole-mass 0.1 :pole-length 0.5 :force-mag 10.0
     :alive 1.0 :terminating -2.0 :pole-pos-penalty -1.0 :cart-vel-penalty -0.01
     :pole-vel-penalty -0.005 :max-episode-length-s 5.0 :pole-bound 0.6
     :cart-bound 2.4 :reset-noise 0.05}
    over)))

(defn cartpole-step
  "One physics step of the cart-pole (Barto-Sutton, theta from upright)."
  [s force cfg]
  (let [g (:gravity cfg) mc (:cart-mass cfg) mp (:pole-mass cfg)
        l (:pole-length cfg) dt (:physics-dt cfg)
        total (+ mc mp)
        ct (Math/cos (:theta s))
        st (Math/sin (:theta s))
        temp (/ (+ force (* mp l (:theta-dot s) (:theta-dot s) st)) total)
        theta-acc (/ (- (* g st) (* ct temp)) (* l (- (/ 4.0 3.0) (/ (* mp ct ct) total))))
        x-acc (- temp (/ (* mp l theta-acc ct) total))]
    {:x (+ (:x s) (* dt (:x-dot s)))
     :x-dot (+ (:x-dot s) (* dt x-acc))
     :theta (+ (:theta s) (* dt (:theta-dot s)))
     :theta-dot (+ (:theta-dot s) (* dt theta-acc))}))

(defn next-centered
  "Centered uniform draw in [-half, half] from a sampler (matches the
  Python `_Lcg.next_f32_centered`)."
  [rng half]
  (* (- (* (sampler/next-u01! rng) 2.0) 1.0) half))

(defn reset-state
  "Seed a fresh randomized cart-pole state."
  [rng cfg]
  {:x (next-centered rng (:reset-noise cfg))
   :x-dot (next-centered rng (:reset-noise cfg))
   :theta (next-centered rng (:reset-noise cfg))
   :theta-dot (next-centered rng (:reset-noise cfg))})

;; ── env surface the MDP terms read ───────────────────────────────────────
;;
;; CartpoleEnvView (held in an atom) {:state :last-action :terminated
;;   :step-count :max-steps :cfg :rng}

;; ── MDP term functions ────────────────────────────────────────────────────

(defn joint-pos-rel [env _] (let [s (:state @env)] [(:x s) (:theta s)]))
(defn joint-vel-rel [env _] (let [s (:state @env)] [(:x-dot s) (:theta-dot s)]))
(defn last-action-term [env _] (vec (:last-action @env)))

(defn is-alive [env _] (if (:terminated @env) 0.0 1.0))
(defn is-terminated [env _] (if (:terminated @env) 1.0 0.0))
(defn pole-pos-l2 [env _] (let [th (:theta (:state @env))] (* th th)))
(defn cart-vel-l2 [env _] (let [v (:x-dot (:state @env))] (* v v)))
(defn pole-vel-l2 [env _] (let [v (:theta-dot (:state @env))] (* v v)))

(defn pole-out-of-bounds? [env _] (> (Math/abs (:theta (:state @env))) (:pole-bound (:cfg @env))))
(defn cart-out-of-bounds? [env _] (> (Math/abs (:x (:state @env))) (:cart-bound (:cfg @env))))
(defn time-out? [env _] (>= (:step-count @env) (:max-steps @env)))

(defn reset-joints-by-offset!
  [env _]
  (swap! env (fn [e] (assoc e :state (reset-state (:rng e) (:cfg e))))))

;; ── default Isaac Lab Cartpole term groups ────────────────────────────────

(defn cartpole-obs-terms
  []
  {:joint-pos {:func joint-pos-rel}
   :joint-vel {:func joint-vel-rel}
   :last-action {:func last-action-term :scale 0.1}})

(defn cartpole-rew-terms
  [cfg]
  {:alive {:func is-alive :weight (:alive cfg)}
   :terminating {:func is-terminated :weight (:terminating cfg)}
   :pole-pos {:func pole-pos-l2 :weight (:pole-pos-penalty cfg)}
   :cart-vel {:func cart-vel-l2 :weight (:cart-vel-penalty cfg)}
   :pole-vel {:func pole-vel-l2 :weight (:pole-vel-penalty cfg)}})

(defn cartpole-termination-terms
  []
  {:pole-oob {:func pole-out-of-bounds?}
   :cart-oob {:func cart-out-of-bounds?}
   :time-out {:func time-out? :time-out true}})

(defn cartpole-event-terms
  []
  {:reset-pose {:func reset-joints-by-offset! :mode :reset}})
