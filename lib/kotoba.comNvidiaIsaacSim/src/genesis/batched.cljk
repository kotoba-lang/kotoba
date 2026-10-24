(ns genesis.batched
  "Multi-environment articulation view (Isaac Sim tensor semantics):
  `ArticulationBatch` provides the `[num_envs, n_dof]` env-major flat
  tensor shape Isaac Lab expects, over `genesis.articulation3d`'s
  Spatial3d (Featherstone) solver.

  `genesis.articulation3d` now supplies the underlying general dynamics, so
  this namespace implements env-major flat effort handling, deterministic
  multi-env stepping, and reset. Tensor-native GPU execution, PD-drive
  expansion, IK batches, and domain randomization remain follow-up work.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/batched.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930."
  (:require [genesis.articulation3d :as a3d]))

(defn ->pd-drive
  [{:keys [targets vel-targets kps kds gravity-comp? computed-torque? accel-ff]}]
  {:targets targets :vel-targets vel-targets :kps kps :kds kds
   :gravity-comp? gravity-comp? :computed-torque? computed-torque? :accel-ff accel-ff})

(defn new-batch
  "`Articulation3dConfig` cloned across `num-envs` environments (all
  zeroed). Efforts are stored flat in env-major `[num-envs, ndof]` order."
  [cfg num-envs]
  (let [num-envs (max num-envs 1)
        ndof (:ndof cfg)
        movable-bodies (->> (:bodies cfg) (filter a3d/movable?) (sort-by :dof) vec)
        limits (mapv (fn [{:keys [lower upper has-limit?]}]
                       (if has-limit? [lower upper] [##-Inf ##Inf])) movable-bodies)]
    {:cfg cfg
     :states (vec (repeat num-envs {:q (vec (repeat ndof 0.0)) :qdot (vec (repeat ndof 0.0))}))
     :efforts (vec (repeat (* num-envs ndof) 0.0))
     :pos-drive nil
     :dof-names (mapv :name movable-bodies)
     :dof-limits (if (= ndof (count limits)) limits (vec (repeat ndof [##-Inf ##Inf])))
     :last-efforts (vec (repeat (* num-envs ndof) 0.0))
     :per-env-cfg nil}))

(defn num-envs [{:keys [states]}] (count states))
(defn num-dof [{:keys [cfg]}] (:ndof cfg))
(defn dof-names [{:keys [dof-names]}] dof-names)
(defn get-dof-index [batch name]
  (first (keep-indexed (fn [i n] (when (= n name) i)) (dof-names batch))))
(defn get-dof-limits [{:keys [dof-limits]}] dof-limits)

(defn- expected-effort-count [batch]
  (* (num-envs batch) (num-dof batch)))

(defn set-efforts
  "Set an env-major flat `[num-envs, ndof]` effort tensor for the next step."
  [batch efforts]
  (let [efforts (vec efforts) expected (expected-effort-count batch)]
    (when-not (= expected (count efforts))
      (throw (ex-info "effort tensor shape does not match batch"
                      {:expected expected :actual (count efforts)})))
    (assoc batch :efforts efforts)))

(defn efforts-for-env
  "Return the torque vector for `env-index`."
  [batch env-index]
  (let [n (num-dof batch)]
    (when-not (<= 0 env-index (dec (num-envs batch)))
      (throw (ex-info "environment index out of range" {:env-index env-index})))
    (subvec (vec (:efforts batch)) (* env-index n) (* (inc env-index) n))))

(defn set-pd-drive
  "Install a `PdDrive` map. Per-DOF fields accept either `ndof` values
  (broadcast to every environment) or a flat env-major tensor."
  [batch drive]
  (assoc batch :pos-drive drive))

(defn- expand-env-major [batch values default]
  (let [n (num-dof batch) total (expected-effort-count batch)]
    (cond
      (nil? values) (vec (repeat total default))
      (= total (count values)) (vec values)
      (= n (count values)) (vec (mapcat identity (repeat (num-envs batch) values)))
      :else (throw (ex-info "drive tensor shape does not match batch"
                            {:ndof n :num-envs (num-envs batch) :actual (count values)})))))

(defn pd-efforts
  "Compute the env-major torque tensor for the installed `PdDrive`.

  `:targets`, `:vel-targets`, `:kps`, and `:kds` may be per-DOF or per-env.
  When `:gravity-comp?` is true, each environment gets the RNEA static gravity
  torque in addition to the PD command."
  [batch]
  (let [{:keys [targets vel-targets kps kds gravity-comp?]} (:pos-drive batch)
        n (num-dof batch)
        states (:states batch)
        qs (vec (mapcat :q states))
        qdots (vec (mapcat :qdot states))
        targets (if targets (expand-env-major batch targets 0.0) qs)
        vel-targets (expand-env-major batch vel-targets 0.0)
        kps (expand-env-major batch kps 0.0)
        kds (expand-env-major batch kds 0.0)
        gravity (if gravity-comp?
                  (vec (mapcat #(a3d/gravity-torque (:cfg batch) (:q %)) states))
                  (vec (repeat (* (num-envs batch) n) 0.0)))]
    (mapv (fn [target velocity-target kp kd q qdot gravity-torque]
            (+ (* kp (- target q)) (* kd (- velocity-target qdot)) gravity-torque))
          targets vel-targets kps kds qs qdots gravity)))

(defn step
  "Advance every environment once using its env-major effort vector.

  The returned batch preserves the command tensor in `:last-efforts` and
  clears `:efforts` so a stale action cannot silently be applied twice."
  [batch]
  (let [cfg (:cfg batch)
        efforts (:efforts batch)
        states (mapv (fn [env-index state]
                       (a3d/step cfg state (efforts-for-env batch env-index)))
                     (range (num-envs batch)) (:states batch))]
    (assoc batch :states states :last-efforts efforts
                 :efforts (vec (repeat (expected-effort-count batch) 0.0)))))

(defn step-pd-drive
  "Compute the installed PD drive then advance all environments once."
  [batch]
  (step (set-efforts batch (pd-efforts batch))))

(defn reset
  "Reset all environments, or one environment when `env-index` is supplied."
  ([batch]
   (assoc batch :states (vec (repeat (num-envs batch) (a3d/zeros-state (num-dof batch))))
                :efforts (vec (repeat (expected-effort-count batch) 0.0))
                :last-efforts (vec (repeat (expected-effort-count batch) 0.0))))
  ([batch env-index]
   (when-not (<= 0 env-index (dec (num-envs batch)))
     (throw (ex-info "environment index out of range" {:env-index env-index})))
   (assoc-in batch [:states env-index] (a3d/zeros-state (num-dof batch)))))
