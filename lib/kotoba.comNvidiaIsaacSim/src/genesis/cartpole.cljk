(ns genesis.cartpole
  "Closed-form Cartpole dynamics (Sutton & Barto 1983, §10.2).

  State: (x, x-dot, theta, theta-dot)
    x         — cart position [m]
    x-dot     — cart velocity [m/s]
    theta     — pole angle from vertical (positive = pole tilts +x) [rad]
    theta-dot — pole angular velocity [rad/s]

  Action: force on cart [N] (continuous, clamped to ±force-mag).

  Convention matches OpenAI Gym CartPole-v1 / Isaac Lab Cartpole-Direct-v0:
  gravity points -z; pole is balanced upright at theta = 0.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/cartpole.rs`
  (deleted PR #82, \"Remove Rust workspace\") as zero-dependency portable
  CLJC. Per ADR-2607010930. Ported 1:1 (fully portable pure math/data —
  no PhysX / OmniKit / wgpu dependency)."
  )

(defn default-config
  "Matches kami-engine fixtures/cartpole/cartpole.urdf and the OpenAI Gym
  CartPole-v1 reference."
  []
  {:cart-mass 1.0
   :pole-mass 0.1
   :pole-half-length 0.25 ;; = pole_length / 2 (0.5 m total)
   :gravity 9.81
   :force-mag 100.0 ;; |action| <= force-mag, matches urdf effort limit
   :dt (/ 1.0 60.0)}) ;; 60 Hz physics step

(defn default-state []
  {:x 0.0 :x-dot 0.0 :theta 0.0 :theta-dot 0.0})

(defn clamp [v lo hi] (max lo (min hi v)))

(defn step
  "Apply one semi-implicit Euler integration step under `action` (force on
  cart). Returns the next state."
  [{:keys [x x-dot theta theta-dot] :as _state} action
   {:keys [cart-mass pole-mass pole-half-length gravity force-mag dt]}]
  (let [force (clamp action (- force-mag) force-mag)
        sin-t (Math/sin theta)
        cos-t (Math/cos theta)
        total-mass (+ cart-mass pole-mass)
        pole-mass-length (* pole-mass pole-half-length)
        temp (/ (+ force (* pole-mass-length theta-dot theta-dot sin-t))
                total-mass)
        theta-acc (/ (- (* gravity sin-t) (* cos-t temp))
                      (* pole-half-length
                         (- (/ 4.0 3.0)
                            (/ (* pole-mass cos-t cos-t) total-mass))))
        x-acc (- temp (/ (* pole-mass-length theta-acc cos-t) total-mass))
        x-dot' (+ x-dot (* dt x-acc))
        x' (+ x (* dt x-dot'))
        theta-dot' (+ theta-dot (* dt theta-acc))
        theta' (+ theta (* dt theta-dot'))]
    {:x x' :x-dot x-dot' :theta theta' :theta-dot theta-dot'}))
