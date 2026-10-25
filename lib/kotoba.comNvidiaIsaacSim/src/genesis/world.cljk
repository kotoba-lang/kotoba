(ns genesis.world
  "`World` + `Articulation` — Isaac Sim/PhysX-style API surface.

  Scoping decision (native-facade-dependent file, ADR-2607010930
  scoped-restoration pattern): the original `World`/`Articulation` are
  built via `Articulation::from_urdf`, which requires
  `kami_articulated::{ArticulatedSystem, JointKind}` (a separate,
  not-restored URDF-parsing crate) to turn a URDF file into a rigid-body
  topology. Every other module in this restoration that needs a `World`
  (`genesis.controllers`, `genesis.trajectory`'s integration test) is
  adapted instead to operate on the closed-form topology states directly
  (`genesis.cartpole`/`genesis.double-pendulum`/`genesis.planar-chain`),
  which is a faithful port of the *dynamics*, just not of this
  URDF-driven container.

  What IS ported here (pure data, no `kami_articulated` dependency): the
  `LinkState` per-link kinematic pose/twist record, the default `World`
  scene parameters (gravity, dt), and the `WorldError` variants — plus a
  small multi-topology dispatcher `step-topology`/`jacobian-for-link` that
  mirrors `Articulation::step`/`Articulation::jacobian` for the three
  closed-form topologies this crate implements natively (Cartpole,
  DoublePendulum, PlanarChain), operating on a `{:topology :cfg :state}`
  map instead of a `kami_articulated`-parsed generic articulation.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/world.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930."
  (:require [genesis.cartpole :as cartpole]
            [genesis.double-pendulum :as dp]
            [genesis.planar-chain :as pc]
            [genesis.articulation3d :as a3d]
            [genesis.jacobian :as jac]))

(defn link-state-at-origin []
  {:position [0.0 0.0 0.0] :orientation [0.0 0.0 0.0 1.0] ;; quat wxyz->xyzw irrelevant at identity
   :linear-velocity [0.0 0.0 0.0] :angular-velocity [0.0 0.0 0.0]})

(defn default-world []
  {:gravity 9.81 :dt (/ 1.0 60.0) :articulations []})

;; WorldError variants (as keyword + message, mirroring the Rust `thiserror`
;; messages 1:1):
(defn unsupported-topology-error [name]
  {:kind :unsupported-topology
   :message (str "articulation topology not supported at R1.1: " name
                 ". Cartpole (1 prismatic + 1 revolute) is the only supported topology.")})
(defn invalid-handle-error [h] {:kind :invalid-handle :message (str "articulation handle " h " is invalid")})
(defn duplicate-name-error [name] {:kind :duplicate-name :message (str "articulation `" name "` already registered")})

(defn add-articulation
  "Add a named general 3-D articulation config to `world`.

  `cfg` is normally built by `genesis.articulation3d/from-articulated-system`.
  The world stores state and the pending effort command separately so callers
  can set actions for several robots before a single deterministic step."
  ([world name cfg] (add-articulation world name cfg (a3d/zeros-state (:ndof cfg))))
  ([world name cfg state]
   (when (some #(= name (:name %)) (:articulations world))
     (throw (ex-info (:message (duplicate-name-error name)) (duplicate-name-error name))))
   (when-not (= (:ndof cfg) (count (:q state)))
     (throw (ex-info "articulation state does not match configuration" {:name name})))
   (update world :articulations conj {:name name :cfg cfg :state state
                                      :efforts (vec (repeat (:ndof cfg) 0.0))})))

(defn articulation
  "Lookup a named articulation entry, or nil."
  [world name]
  (first (filter #(= name (:name %)) (:articulations world))))

(defn set-articulation-efforts
  "Set the pending torque vector for a named articulation."
  [world name efforts]
  (let [entry (articulation world name)]
    (when-not entry
      (throw (ex-info (:message (invalid-handle-error name)) (invalid-handle-error name))))
    (let [efforts (vec efforts)]
      (when-not (= (:ndof (:cfg entry)) (count efforts))
        (throw (ex-info "effort vector does not match articulation DOFs"
                        {:name name :expected (:ndof (:cfg entry)) :actual (count efforts)})))
      (update world :articulations
              (fn [entries] (mapv #(if (= name (:name %)) (assoc % :efforts efforts) %) entries))))))

(defn step-articulations
  "Advance every registered general 3-D articulation once and clear commands."
  [world]
  (update world :articulations
          (fn [entries]
            (mapv (fn [{:keys [cfg state efforts] :as entry}]
                    (assoc entry :state (a3d/step cfg state efforts)
                                 :efforts (vec (repeat (:ndof cfg) 0.0))))
                  entries))))

(defn reset
  "Reset every registered articulation to zero position and velocity."
  [world]
  (update world :articulations
          (fn [entries]
            (mapv (fn [{:keys [cfg] :as entry}]
                    (assoc entry :state (a3d/zeros-state (:ndof cfg))
                                 :efforts (vec (repeat (:ndof cfg) 0.0))))
                  entries))))

(defn articulation-link-state
  "World-frame pose and twist of a named articulated link.

  Orientation is a 3x3 world rotation matrix; `:position`, linear velocity
  and angular velocity use the same world coordinates as Isaac's link state."
  [world articulation-name link-name]
  (let [{:keys [cfg state] :as entry} (articulation world articulation-name)]
    (when-not entry
      (throw (ex-info (:message (invalid-handle-error articulation-name))
                      (invalid-handle-error articulation-name))))
    (let [pose (a3d/link-pose cfg state link-name)]
      (when-not pose
        (throw (ex-info "link not found in articulation" {:articulation articulation-name :link link-name})))
      (let [jacobian (a3d/geometric-jacobian cfg state link-name)
            velocity (fn [row] (reduce + (map * row (:qdot state))))]
        {:position (:position pose) :rotation (:rotation pose)
         :linear-velocity (mapv velocity (subvec (vec jacobian) 3 6))
         :angular-velocity (mapv velocity (subvec (vec jacobian) 0 3))}))))

;; ── Small multi-topology dispatcher over the closed-form solvers ────────

(defn step-topology
  "Steps a `{:topology (:cartpole|:double-pendulum|:planar-chain) :cfg
  :state}` map by one physics step under `action` (a scalar force for
  :cartpole, or a per-joint torque vector for the other two)."
  [{:keys [topology cfg state] :as art} action]
  (assoc art :state
    (case topology
      :cartpole (cartpole/step state action cfg)
      :double-pendulum (dp/step state action cfg)
      :planar-chain (pc/step state action cfg))))

(defn jacobian-for-link
  "Analytical Jacobian for `link` on a `{:topology :cfg :state}` map."
  [{:keys [topology cfg state]} link]
  (case topology
    :cartpole (jac/cartpole-link-jacobian (:theta state) link cfg)
    :double-pendulum (jac/dp-link-jacobian (:q1 state) (:q2 state) link cfg)
    :planar-chain (jac/planar-chain-link-jacobian (:q state) link cfg)))
