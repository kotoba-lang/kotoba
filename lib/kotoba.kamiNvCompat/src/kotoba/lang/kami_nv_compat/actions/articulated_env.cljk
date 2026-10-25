(ns kotoba.lang.kami-nv-compat.actions.articulated-env
  "The ArticulatedEnv contract that action wrappers consume — JVM port of
  src/actions/articulated-env.ts. Both joint-space (effort/position/velocity)
  and task-space (DiffIK / OSC) wrappers consume an env that conforms to this
  protocol. Real Isaac Lab envs implement it via their sim substrate; for
  browser/JVM use, callers wire dynamics + forward-kinematics into an adapter.
  Wave 16b of ADR-2607020130.

  Effort buffers: the env exposes optional atoms — :applied-torques (atom of
  vector), :applied-force (atom of number), :actions (atom of vector-of-vectors).
  write-effort! dispatches onto whichever exists.")

(defprotocol IArticulatedEnv
  (joint-positions  [this])
  (joint-velocities [this])
  (get-jacobian     [this body-name])
  (get-ee-pose      [this body-name])
  (get-ee-velocity  [this body-name])
  (get-gravity-torque [this body-name]))

(defn- extend-with-zeros
  "Extend v to length (inc max-idx), padding with 0."
  [v max-idx]
  (if (< (count v) (inc max-idx))
    (into v (repeat (- (inc max-idx) (count v)) 0))
    v))

(defn write-effort!
  "Dispatch per-joint torques onto whichever effort buffer the env exposes.
  `torques` is a vector of [joint-idx torque] pairs."
  ([env torques]
   (write-effort! env torques true))
  ([env torques single-dof-force-ok?]
   (cond
     (:applied-torques env)
     (let [max-idx (reduce max 0 (map first torques))]
       (swap! (:applied-torques env)
              (fn [v]
                (reduce (fn [acc [j t]] (assoc acc j t))
                        (extend-with-zeros v max-idx)
                        torques))))

     (and single-dof-force-ok?
          (:applied-force env)
          (= 1 (count torques))
          (zero? (ffirst torques)))
     (reset! (:applied-force env) (second (first torques)))

     (and (:actions env) (pos? (count @(:actions env))))
     (let [max-idx (reduce max 0 (map first torques))]
       (swap! (:actions env)
              (fn [actions]
                (update actions 0 #(reduce (fn [acc [j t]] (assoc acc j t))
                                           (extend-with-zeros % max-idx)
                                           torques)))))

     :else
     (throw (ex-info "write-effort!: env has no effort buffer" {})))))
