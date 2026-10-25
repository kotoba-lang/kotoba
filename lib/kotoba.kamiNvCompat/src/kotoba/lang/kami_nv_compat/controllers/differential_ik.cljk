(ns kotoba.lang.kami-nv-compat.controllers.differential-ik
  "DifferentialIKController — JVM port of src/controllers/differential-ik.ts.
  Jacobian-based inverse kinematics for arm reaching: maps a 6-DOF task-space
  command (pose or position) onto a joint-space delta via damped least squares
  (DLS) or Moore-Penrose pseudoinverse over the articulation Jacobian. Mirrors
  isaaclab.controllers.DifferentialIKController (Isaac Lab 1.x). Algorithm-for-
  algorithm port. Trademark: 'Isaac®' is a trademark of NVIDIA Corp; API-
  namespace localization for forward-dynamics interop. Wave 10 of ADR-2607020130.")

;; ── Config ────────────────────────────────────────────────────────────────

(defn make-default-differential-ik-cfg
  "Default DifferentialIKController config (with optional overrides)."
  ([] (make-default-differential-ik-cfg nil))
  ([overrides]
   (merge {:command-type     "pose"
           :use-relative-mode false
           :ik-method        "dls"
           :ik-params        {:lambda-val 0.05}}
          overrides)))

;; ── Quaternion math (Hamilton convention, [x y z w]) ──────────────────────

(defn quat-inverse [q]
  (let [[qx qy qz qw] q
        n2 (+ (* qx qx) (* qy qy) (* qz qz) (* qw qw))]
    (if (< n2 1e-24)
      [0 0 0 1]
      (let [inv (/ 1.0 n2)]
        [(* (- qx) inv) (* (- qy) inv) (* (- qz) inv) (* qw inv)]))))

(defn quat-mul [q1 q2]
  (let [[x1 y1 z1 w1] q1
        [x2 y2 z2 w2] q2]
    [(+ (* w1 x2) (* x1 w2) (* y1 z2) (- (* z1 y2)))
     (- (* w1 y2) (* x1 z2) (* y1 w2) (* z1 x2))
     (+ (* w1 z2) (* x1 y2) (- (* y1 x2)) (* z1 w2))
     (- (* w1 w2) (* x1 x2) (* y1 y2) (* z1 z2))]))

(defn spatial->isaaclab-jacobian
  "Swap a 6×n Jacobian from Featherstone spatial [ω; v] (angular rows first)
  into Isaac Lab's IK convention [v; ω] (linear rows first)."
  [J]
  (when (not= 6 (count J))
    (throw (ex-info "spatial->isaaclab-jacobian: expected 6 rows" {:rows (count J)})))
  [(nth J 3) (nth J 4) (nth J 5) (nth J 0) (nth J 1) (nth J 2)])

(defn axis-angle-vec
  "Quaternion -> axis-angle rotation vector (3)."
  [q]
  (let [[qx qy qz qw] (if (neg? (nth q 3)) (mapv - q) q)
        qw (max -1.0 (min 1.0 qw))
        angle (* 2.0 (Math/acos qw))
        s (Math/sqrt (max 0.0 (- 1.0 (* qw qw))))]
    (if (< s 1e-8)
      [0 0 0]
      (let [inv-s (/ 1.0 s)]
        [(* qx inv-s angle) (* qy inv-s angle) (* qz inv-s angle)]))))

;; ── DLS solver (damped least squares via Gauss-Jordan on a 6×6) ───────────

(defn- solve-dls
  "Δq = J^T (J J^T + λ²I)^-1 error. J is a 6×n vector-of-vectors; returns a
  length-n delta. Gauss-Jordan elimination with partial pivoting on a plain
  6×7 vector-of-vectors augmented matrix (no primitive arrays — portable to
  cljs; a 6×7 solve is far too small to need mutable-array performance)."
  [J error lam n]
  (let [lam2 (* lam lam)
        row  (fn [i]
               (conj (vec (for [j (range 6)]
                            (let [s (loop [k 0 acc 0.0]
                                      (if (>= k n) acc
                                        (recur (inc k) (+ acc (* (double (get-in J [i k]))
                                                                 (double (get-in J [j k])))))))]
                              (double (+ s (if (= i j) lam2 0))))))
                     (double (nth error i))))
        ;; 1. A = J J^T + λ²I, augmented with error.
        aug0 (vec (for [i (range 6)] (row i)))
        ;; 2. Gauss-Jordan elimination on the 6×7 augmented matrix.
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
        ;; 3. y = column 6; Δq = J^T y.
        y (mapv #(get-in aug [% 6]) (range 6))]
    (vec (for [k (range n)]
           (loop [i 0 acc 0.0]
             (if (>= i 6) acc
               (recur (inc i) (+ acc (* (double (get-in J [i k])) (nth y i))))))))))

;; ── Controller ────────────────────────────────────────────────────────────

(defprotocol IDifferentialIKController
  (cfg         [this])
  (num-envs    [this])
  (action-dim  [this])
  (reset-controller! [this env-ids])
  (set-command! [this command opts])
  (get-target  [this env-idx])
  (compute     [this args]))

(defn differential-ik-controller
  "Build a DifferentialIKController. `cfg` = (make-default-differential-ik-cfg
  overrides); `num-envs` defaults to 1."
  ([cfg]
   (differential-ik-controller cfg 1))
  ([cfg num-envs]
   (when (<= num-envs 0)
     (throw (ex-info "num-envs must be > 0" {:num-envs num-envs})))
   (when (not (#{:pose "pose" :position "position"} (:command-type cfg)))
     (throw (ex-info "command-type must be 'pose' or 'position'"
                     {:command-type (:command-type cfg)})))
   (when (not (#{:dls "dls" :pinv "pinv"} (:ik-method cfg)))
     (throw (ex-info "ik-method must be 'dls' or 'pinv'" {:ik-method (:ik-method cfg)})))
   (let [target (atom (vec (repeat num-envs [0 0 0 0 0 0 1])))]
     (reify IDifferentialIKController
       (cfg      [_] cfg)
       (num-envs [_] num-envs)
       (action-dim [_]
         (if (= (:command-type cfg) "pose")
           (if (:use-relative-mode cfg) 6 7)
           3))
       (reset-controller! [_ env-ids]
         (let [ids (or env-ids (range num-envs))]
           (swap! target (fn [t] (reduce #(assoc % %2 [0 0 0 0 0 0 1]) t ids)))))
       (set-command! [_ command {:keys [ee-pos ee-quat env-idx] :or {env-idx 0}}]
         (let [dim (if (= (:command-type cfg) "pose")
                     (if (:use-relative-mode cfg) 6 7) 3)]
           (when (not= (count command) dim)
             (throw (ex-info (str "command must be length " dim " for command-type='"
                                  (:command-type cfg) "'") {:got (count command) :expected dim})))
           (when (or (neg? env-idx) (>= env-idx num-envs))
             (throw (ex-info (str "env-idx=" env-idx " out of range [0, " num-envs ")")
                             {:env-idx env-idx :num-envs num-envs})))
           (let [[target-pos target-quat]
                 (if (:use-relative-mode cfg)
                   (do (when (or (nil? ee-pos) (nil? ee-quat))
                         (throw (ex-info "use-relative-mode=true requires ee-pos + ee-quat" {})))
                       [(vec (map + ee-pos (take 3 command)))
                        (if (= (:command-type cfg) "pose")
                          (let [axang (subvec command 3 6)
                                angle (Math/sqrt (reduce + (map #(* % %) axang)))]
                            (if (< angle 1e-9)
                              (quat-mul [0 0 0 1] ee-quat)
                              (let [ax (mapv #(/ % angle) axang)
                                    h (* angle 0.5)
                                    s (Math/sin h)]
                                (quat-mul [(* (ax 0) s) (* (ax 1) s) (* (ax 2) s) (Math/cos h)]
                                          ee-quat))))
                          ee-quat)])
                   [[(nth command 0) (nth command 1) (nth command 2)]
                    (if (= (:command-type cfg) "pose")
                      (subvec command 3 7)
                      (subvec (@target env-idx) 3 7))])]
             (swap! target assoc env-idx
                    (into target-pos target-quat)))))
       (get-target [_ env-idx]
         (vec (@target (or env-idx 0))))
       (compute [_ {:keys [ee-pos ee-quat jacobian env-idx] :or {env-idx 0}}]
         (when (not= 6 (count jacobian))
           (throw (ex-info "jacobian must be 6 rows (linear x/y/z + angular x/y/z)"
                           {:rows (count jacobian)})))
         (let [n (count (nth jacobian 0))]
           (doseq [row jacobian]
             (when (not= (count row) n)
               (throw (ex-info "jacobian rows must all have the same width" {}))))
           (let [t (@target env-idx)
                 t-pos (subvec t 0 3)
                 t-quat (subvec t 3 7)
                 pos-err (vec (map - t-pos ee-pos))
                 ori-err (if (= (:command-type cfg) "pose")
                           (axis-angle-vec (quat-mul t-quat (quat-inverse ee-quat)))
                           [0 0 0])
                 error (vec (concat pos-err ori-err))
                 lam (if (= (:ik-method cfg) "dls")
                       (get-in cfg [:ik-params :lambda-val])
                       1e-6)]
             (solve-dls jacobian error lam n))))))))
