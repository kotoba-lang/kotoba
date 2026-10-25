(ns kotoba.lang.kami-nv-compat.controllers.operational-space
  "OperationalSpaceController — JVM port of src/controllers/operational-space.ts.
  Task-space torque control (sibling of DifferentialIKController): target
  pose/wrench → joint TORQUE via Jacobian transpose. Cartesian impedance
  (K_p·pos_err + K_d·vel_err) → 6-DOF task wrench → τ = Jᵀ F_task, with
  optional null-space joint regularization (n>6) + gravity compensation.
  Algorithm-for-algorithm port. Pure, zero runtime deps (reuses the
  differential-ik quaternion math). Wave 11 of ADR-2607020130."
  (:require [kotoba.lang.kami-nv-compat.controllers.differential-ik :as dik]))

;; ── Config ────────────────────────────────────────────────────────────────

(defn make-default-osc-cfg
  ([] (make-default-osc-cfg nil))
  ([overrides]
   (merge {:target-types              ["pose_abs"]
           :impedance-mode            "fixed"
           :motion-stiffness-task     [100 100 100 100 100 100]
           :motion-damping-ratio-task [1 1 1 1 1 1]
           :motion-stiffness-limits   [0 1000]
           :motion-damping-limits     [0 100]
           :nullspace-control         "none"
           :nullspace-stiffness       10
           :nullspace-damping-ratio   1
           :gravity-compensation      false}
          overrides)))

;; ── Null-space projection (damped pseudoinverse, Gauss-Jordan 6×6) ────────

(defn- project-to-nullspace
  "Project tauNs into the null-space of J: P_null = I - Jᵀ(JJᵀ+λ²I)⁻¹ J. Gauss-
  Jordan elimination with partial pivoting on a plain 6×7 vector-of-vectors
  augmented matrix (no primitive arrays — portable to cljs; a 6×7 solve is far
  too small to need mutable-array performance)."
  [J tauNs n lam]
  (let [lam2 (* lam lam)
        ;; Jtau = J · tauNs (6-vec)
        Jtau (vec (for [k (range 6)]
                    (loop [i 0 acc 0.0]
                      (if (>= i n) acc
                        (recur (inc i) (+ acc (* (double (get-in J [k i])) (double (nth tauNs i)))))))))
        row  (fn [i]
               (conj (vec (for [j (range 6)]
                            (let [s (loop [k 0 acc 0.0]
                                      (if (>= k n) acc
                                        (recur (inc k) (+ acc (* (double (get-in J [i k])) (double (get-in J [j k])))))))]
                              (double (+ s (if (= i j) lam2 0))))))
                     (nth Jtau i)))
        ;; A = J Jᵀ + λ²I, augmented with Jtau.
        aug0 (vec (for [i (range 6)] (row i)))
        ;; Gauss-Jordan.
        aug  (reduce
               (fn [aug col]
                 (let [piv (reduce (fn [p r]
                                      (if (> (Math/abs (double (get-in aug [r col])))
                                             (Math/abs (double (get-in aug [p col]))))
                                        r p))
                                    col (range (inc col) 6))
                       mx  (Math/abs (double (get-in aug [piv col])))]
                   (if (< mx 1e-18)
                     aug
                     (let [aug (if (not= piv col)
                                 (let [rc (nth aug col) rp (nth aug piv)]
                                   (-> aug (assoc col rp) (assoc piv rc)))
                                 aug)
                           pv  (get-in aug [col col])
                           aug (assoc aug col (mapv #(/ % pv) (nth aug col)))]
                       (reduce
                         (fn [aug r]
                           (if (= r col)
                             aug
                             (let [f (double (get-in aug [r col]))]
                               (if (< (Math/abs f) 1e-18)
                                 aug
                                 (assoc aug r (mapv #(- %1 (* f %2)) (nth aug r) (nth aug col)))))))
                         aug (range 6))))))
               aug0 (range 6))
        ;; Jty = Jᵀ y ; out = tauNs - Jty.
        y (mapv #(get-in aug [% 6]) (range 6))]
    (vec (for [i (range n)]
           (- (double (nth tauNs i))
              (loop [k 0 acc 0.0]
                (if (>= k 6) acc
                  (recur (inc k) (+ acc (* (double (get-in J [k i])) (nth y k)))))))))))

;; ── Controller ────────────────────────────────────────────────────────────

(defprotocol IOperationalSpaceController
  (cfg        [this])
  (num-envs   [this])
  (num-dof    [this])
  (action-dim [this])
  (reset-controller! [this env-ids])
  (set-command! [this command opts])
  (get-target  [this env-idx])
  (compute     [this args]))

(defn- target-type-dim [tt]
  (condp = tt "pose_abs" 7 "pose_rel" 6 "wrench_abs" 6 3))   ; force_abs / torque_abs

(defn operational-space-controller
  "Build an OperationalSpaceController. `num-envs` default 1, `num-dof` 7."
  ([cfg] (operational-space-controller cfg 1 7))
  ([cfg num-envs] (operational-space-controller cfg num-envs 7))
  ([cfg num-envs num-dof]
   (when (<= num-envs 0) (throw (ex-info "num-envs must be > 0" {:num-envs num-envs})))
   (when (<= num-dof 0) (throw (ex-info "num-dof must be > 0" {:num-dof num-dof})))
   (when (not (#{"fixed" "variable"} (:impedance-mode cfg)))
     (throw (ex-info "impedance-mode must be 'fixed' or 'variable'" {:impedance-mode (:impedance-mode cfg)})))
   (when (not (#{"none" "position"} (:nullspace-control cfg)))
     (throw (ex-info "nullspace-control must be 'none' or 'position'" {:nullspace-control (:nullspace-control cfg)})))
   (when (not= 6 (count (:motion-stiffness-task cfg)))
     (throw (ex-info "motion-stiffness-task must be 6-vec" {:got (count (:motion-stiffness-task cfg))})))
   (when (not= 6 (count (:motion-damping-ratio-task cfg)))
     (throw (ex-info "motion-damping-ratio-task must be 6-vec" {:got (count (:motion-damping-ratio-task cfg))})))
   (let [target  (atom (vec (repeat num-envs [0 0 0 0 0 0 1])))
         var-stf (atom (vec (repeat num-envs nil)))]
     (reify IOperationalSpaceController
       (cfg      [_] cfg)
       (num-envs [_] num-envs)
       (num-dof  [_] num-dof)
       (action-dim [_]
         (let [base (reduce + (map target-type-dim (:target-types cfg)))]
           (if (= (:impedance-mode cfg) "variable") (+ base 12) base)))
       (reset-controller! [_ env-ids]
         (let [ids (or env-ids (range num-envs))]
           (swap! target (fn [t] (reduce #(assoc % %2 [0 0 0 0 0 0 1]) t ids)))
           (swap! var-stf (fn [v] (reduce #(assoc % %2 nil) v ids)))))
       (set-command! [_ command {:keys [ee-pos ee-quat env-idx] :or {env-idx 0}}]
         (when (or (neg? env-idx) (>= env-idx num-envs))
           (throw (ex-info (str "env-idx=" env-idx " out of range [0, " num-envs ")")
                           {:env-idx env-idx :num-envs num-envs})))
         (let [expected (if (= (:impedance-mode cfg) "variable")
                          (+ (reduce + (map target-type-dim (:target-types cfg))) 12)
                          (reduce + (map target-type-dim (:target-types cfg))))]
           (when (not= (count command) expected)
             (throw (ex-info (str "command must be length " expected) {:got (count command) :expected expected})))
           (let [[cmd _] (if (= (:impedance-mode cfg) "variable")
                           (let [gains-start (- expected 12)]
                             (swap! var-stf assoc env-idx (subvec command gains-start))
                             [(subvec command 0 gains-start)])
                           [command])]
             (loop [tts (:target-types cfg) idx 0]
               (when (seq tts)
                 (let [tt (first tts)]
                   (condp = tt
                     "pose_abs"
                     (do (swap! target assoc env-idx (subvec cmd idx (+ idx 7)))
                         (recur (rest tts) (+ idx 7)))
                     "pose_rel"
                     (do (when (or (nil? ee-pos) (nil? ee-quat))
                           (throw (ex-info "pose_rel requires ee-pos + ee-quat" {})))
                         (let [delta (subvec cmd idx (+ idx 6))
                               pos'  (vec (map + ee-pos (subvec delta 0 3)))
                               angle (Math/sqrt (reduce + (map #(* % %) (subvec delta 3 6))))
                               q'    (if (< angle 1e-9)
                                       ee-quat
                                       (let [ax (mapv #(/ % angle) (subvec delta 3 6))
                                             h  (* angle 0.5)
                                             s  (Math/sin h)]
                                         (dik/quat-mul [(* (ax 0) s) (* (ax 1) s) (* (ax 2) s) (Math/cos h)]
                                                       ee-quat)))]
                           (swap! target assoc env-idx (into pos' q'))
                           (recur (rest tts) (+ idx 6))))
                     "wrench_abs" (recur (rest tts) (+ idx 6))
                     (recur (rest tts) (+ idx 3)))))))))   ; force_abs / torque_abs
       (get-target [_ env-idx] (vec (@target (or env-idx 0))))
       (compute [_ {:keys [ee-pos ee-quat ee-lin-vel ee-ang-vel jacobian joint-pos joint-vel
                           gravity-torque nullspace-target-pos env-idx] :or {env-idx 0}}]
         (when (not= 6 (count jacobian))
           (throw (ex-info "jacobian must have 6 rows" {:rows (count jacobian)})))
         (let [n (count (nth jacobian 0))]
           (when (not= n num-dof)
             (throw (ex-info (str "jacobian width " n " != num-dof " num-dof) {:n n :num-dof num-dof})))
           (let [t (@target env-idx)
                 t-pos (subvec t 0 3) t-quat (subvec t 3 7)
                 pos-err (vec (map - t-pos ee-pos))
                 ori-err (dik/axis-angle-vec (dik/quat-mul t-quat (dik/quat-inverse ee-quat)))
                 error (vec (concat pos-err ori-err))
                 d-error (vec (concat (map - ee-lin-vel) (map - ee-ang-vel)))
                 vs (@var-stf env-idx)
                 [kp-task kd-ratio] (if (and (= (:impedance-mode cfg) "variable") vs)
                                      [(subvec vs 0 6) (subvec vs 6 12)]
                                      [(:motion-stiffness-task cfg) (:motion-damping-ratio-task cfg)])
                 kd-task (vec (for [i (range 6)] (* 2.0 (nth kd-ratio i) (Math/sqrt (max 0.0 (nth kp-task i))))))
                 f-task (vec (for [i (range 6)] (+ (* (nth kp-task i) (nth error i))
                                                   (* (nth kd-task i) (nth d-error i)))))
                 ;; τ = Jᵀ F_task
                 tau (vec (for [i (range n)]
                            (loop [k 0 acc 0.0]
                              (if (>= k 6) acc
                                (recur (inc k) (+ acc (* (double (get-in jacobian [k i])) (nth f-task k))))))))
                 ;; null-space regularization (n > 6)
                 tau (if (and (= (:nullspace-control cfg) "position")
                              nullspace-target-pos joint-pos joint-vel (> n 6))
                       (let [kp-ns (:nullspace-stiffness cfg)
                             kd-ns (* 2.0 (:nullspace-damping-ratio cfg) (Math/sqrt (max 0.0 kp-ns)))
                             tau-ns (vec (for [i (range n)]
                                           (- (* kp-ns (- (nth nullspace-target-pos i) (nth joint-pos i)))
                                              (* kd-ns (nth joint-vel i)))))
                             tau-ns-proj (project-to-nullspace jacobian tau-ns n 0.05)]
                         (vec (map + tau tau-ns-proj)))
                       tau)
                 ;; gravity compensation
                 tau (if (and (:gravity-compensation cfg) gravity-torque)
                       (let [m (min n (count gravity-torque))]
                         (vec (for [i (range n)] (+ (nth tau i) (if (< i m) (nth gravity-torque i) 0)))))
                       tau)]
             tau)))))))
