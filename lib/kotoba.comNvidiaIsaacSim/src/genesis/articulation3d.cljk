(ns genesis.articulation3d
  "Clean-room 3-D reduced-coordinate articulated rigid-body dynamics (the
  algorithm class NVIDIA PhysX uses for its `Articulation`): RNEA + CRBA +
  LDL^T over `genesis.spatial`'s 6-D spatial-vector algebra, for
  arbitrary 3-D joint axes (not just the planar single-axis case of
  `genesis.planar-chain`).

  Scoping decision (large file, 1564 lines in the original, ADR-2607010930
  scoped-restoration pattern): the *data model* — `JointType3d`, `Body3d`
  (per-body joint/inertia/limit parameters), `Articulation3dConfig`,
  `Articulation3dState` — is pure data with no `kami_articulated`
  dependency and is ported 1:1 below, along with the small pure helpers
  `movable?`/`zeros-state`/`n-bodies`.

  This namespace now includes a portable URDF-system bridge,
  `from-articulated-system`, tree forward kinematics (`fk-world`), and a
  6xN geometric Jacobian (`geometric-jacobian`). The bridge consumes the
  public plain-map output shape of `kotoba-lang/kami-articulated` without
  depending on that namespace, preserving this library's zero-dependency
  CLJC property. It also implements RNEA bias, CRBA mass matrix, free
  forward dynamics and semi-implicit Euler integration. Inverse dynamics,
  DLS pose IK, and contact coupling remain follow-up work.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/articulation3d.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930."
  (:require [genesis.spatial :as sp]
            [genesis.vec3 :as v3]))

;; JointType3d
(def joint-type-fixed :fixed)
(def joint-type-revolute :revolute)
(def joint-type-prismatic :prismatic)

(defn ->body3d
  "One body + the joint connecting it to its parent. Topologically ordered
  (`parent` index < this body's own index; `parent` = -1 means base)."
  [{:keys [name parent joint-type axis e-tree r-tree inertia mass com
           lower upper has-limit? effort damping dof]}]
  {:name name :parent parent :joint-type joint-type :axis axis
   :e-tree e-tree :r-tree r-tree :inertia inertia :mass mass :com com
   :lower lower :upper upper :has-limit? has-limit? :effort effort
   :damping damping :dof dof})

(defn movable? [{:keys [joint-type]}] (not= joint-type joint-type-fixed))

(defn ->articulation3d-config [bodies gravity dt ndof]
  {:bodies bodies :gravity gravity :dt dt :ndof ndof})

(defn n-bodies [{:keys [bodies]}] (count bodies))

(defn zeros-state [ndof]
  {:q (vec (repeat ndof 0.0)) :qdot (vec (repeat ndof 0.0))})

(defn- rpy->mat3
  "URDF roll-pitch-yaw (fixed-axis XYZ) to a row-major rotation matrix."
  [[roll pitch yaw]]
  (let [cr (Math/cos roll) sr (Math/sin roll)
        cp (Math/cos pitch) sp* (Math/sin pitch)
        cy (Math/cos yaw) sy (Math/sin yaw)]
    [[(* cy cp) (- (* cy sp* sr)) (+ (* cy sp* cr) (* sy sr))]
     [(* sy cp) (+ (* sy sp* sr) (* cy cr)) (- (* sy sp* cr) (* cy sr))]
     [(- sp*) (* cp sr) (* cp cr)]]))

(defn- axis-angle->mat3 [axis angle]
  (let [[x y z] (v3/normalize axis)
        c (Math/cos angle) s (Math/sin angle) d (- 1.0 c)]
    [[(+ c (* x x d)) (- (* x y d) (* z s)) (+ (* x z d) (* y s))]
     [(+ (* y x d) (* z s)) (+ c (* y y d)) (- (* y z d) (* x s))]
     [(- (* z x d) (* y s)) (+ (* z y d) (* x s)) (+ c (* z z d))]]))

(defn- inertia-matrix [{:keys [ixx iyy izz ixy ixz iyz]}]
  [[(double (or ixx 0.0)) (double (or ixy 0.0)) (double (or ixz 0.0))]
   [(double (or ixy 0.0)) (double (or iyy 0.0)) (double (or iyz 0.0))]
   [(double (or ixz 0.0)) (double (or iyz 0.0)) (double (or izz 0.0))]])

(defn- ordered-joints [joints]
  (loop [remaining (vec joints) known #{"world"} out []]
    (if (empty? remaining)
      out
      (let [ready (filterv #(contains? known (:parent %)) remaining)]
        (when (empty? ready)
          (throw (ex-info "articulated system has a cycle or disconnected parent"
                          {:remaining (mapv :name remaining) :known known})))
        (recur (vec (remove #(contains? (set ready) %) remaining))
               (into known (map :child ready))
               (into out ready))))))

(defn from-articulated-system
  "Convert the public `kami-articulated/parse-urdf` result into an
  `Articulation3dConfig`. The input is intentionally duck-typed so callers
  can parse URDF in a separate optional dependency and pass its plain map."
  ([system] (from-articulated-system system [0.0 0.0 -9.81] (/ 1.0 60.0)))
  ([{:keys [links joints] :as system} gravity dt]
   (when-not (and (vector? links) (vector? joints))
     (throw (ex-info "articulated system requires vector :links and :joints" {:system system})))
   (let [links-by-name (into {} (map (juxt :name identity) links))]
     (loop [remaining (ordered-joints joints) bodies [] by-link {} next-dof 0]
       (if-let [joint (first remaining)]
         (let [parent-name (:parent joint)
               parent (if (= parent-name "world") -1 (get by-link parent-name))
               _ (when (nil? parent)
                   (throw (ex-info "joint parent has no preceding body"
                                   {:joint (:name joint) :parent parent-name})))
               link (get links-by-name (:child joint))
               _ (when-not link
                   (throw (ex-info "joint child has no link" {:joint (:name joint) :child (:child joint)})))
               kind (if (= (:kind joint) :continuous) :revolute (:kind joint))
               movable (not= kind :fixed)
               dof (if movable next-dof -1)
               origin (or (:origin joint) {:xyz [0.0 0.0 0.0] :rpy [0.0 0.0 0.0]})
               inertial (or (:inertia link) {})
               com (get-in inertial [:com :xyz] [0.0 0.0 0.0])
               body (->body3d
                     {:name (:child joint) :parent parent :joint-type kind
                      :axis (v3/normalize (or (:axis joint) [1.0 0.0 0.0]))
                      ;; Spatial transforms use child<-parent; URDF RPY maps
                      ;; child-frame coordinates into the parent frame.
                      :e-tree (sp/mat3-transpose (rpy->mat3 (or (:rpy origin) [0.0 0.0 0.0])))
                      :r-tree (or (:xyz origin) [0.0 0.0 0.0])
                      :inertia (sp/spatial-inertia (double (or (:mass inertial) 0.0)) com
                                                   (inertia-matrix inertial))
                      :mass (double (or (:mass inertial) 0.0)) :com com
                      :lower (or (:lower joint) ##-Inf) :upper (or (:upper joint) ##Inf)
                      :has-limit? (and movable (not= (:kind joint) :continuous))
                      :effort (double (or (:effort joint) 0.0))
                      :damping (double (or (:damping joint) 0.0)) :dof dof})]
           (recur (next remaining) (conj bodies body)
                  (assoc by-link (:child joint) (count bodies))
                  (if movable (inc next-dof) next-dof)))
         (->articulation3d-config bodies gravity dt next-dof))))))

(defn- state-q [cfg state]
  (let [q (vec (:q state))]
    (when-not (= (count q) (:ndof cfg))
      (throw (ex-info "state q length does not match articulation DOFs"
                      {:expected (:ndof cfg) :actual (count q)})))
    q))

(defn fk-world
  "Forward kinematics for an arbitrary URDF articulation tree.

  Returns a vector in body order. Each entry has `:position`, `:rotation`,
  `:joint-position`, and `:axis-world`."
  [cfg state]
  (let [q (state-q cfg state)]
    (reduce
     (fn [poses body]
       (let [parent-pose (if (= -1 (:parent body))
                           {:position v3/zero :rotation sp/mat3-identity}
                           (nth poses (:parent body)))
             parent-r (:rotation parent-pose)
             ;; `e-tree` is child<-parent for spatial motion transforms.
             ;; World pose rotation is therefore parent<-world composed with
             ;; its inverse, parent<-child.
             joint-r (sp/mat3-mul parent-r (sp/mat3-transpose (:e-tree body)))
             joint-p (v3/add (:position parent-pose) (sp/mat3-vec parent-r (:r-tree body)))
             axis-world (sp/mat3-vec joint-r (:axis body))
             qi (if (movable? body) (nth q (:dof body)) 0.0)
             rotation (if (= :revolute (:joint-type body))
                        (sp/mat3-mul joint-r (axis-angle->mat3 (:axis body) qi))
                        joint-r)
             position (if (= :prismatic (:joint-type body))
                        (v3/add joint-p (v3/scale axis-world qi))
                        joint-p)]
         (conj poses {:name (:name body) :position position :rotation rotation
                      :joint-position joint-p :axis-world axis-world})))
     []
     (:bodies cfg))))

(defn link-pose [cfg state link-name]
  (first (filter #(= (:name %) link-name) (fk-world cfg state))))

(defn geometric-jacobian
  "Return the 6xN world-frame geometric Jacobian for `link-name`.

  Rows 0-2 are angular velocity and rows 3-5 are linear velocity."
  [cfg state link-name]
  (let [poses (fk-world cfg state)
        target-index (first (keep-indexed (fn [i body]
                                            (when (= (:name body) link-name) i))
                                          (:bodies cfg)))]
    (when (nil? target-index)
      (throw (ex-info "link not found in articulation" {:link link-name})))
    (let [target-p (:position (nth poses target-index))
          ancestor-indexes
          (loop [i target-index out []]
            (if (= i -1) out (recur (:parent (nth (:bodies cfg) i)) (conj out i))))
          rows (vec (repeat 6 (vec (repeat (:ndof cfg) 0.0))))]
      (reduce
       (fn [jac i]
         (let [body (nth (:bodies cfg) i)]
           (if-not (movable? body)
             jac
             (let [dof (:dof body) pose (nth poses i) axis (:axis-world pose)
                   linear (if (= :revolute (:joint-type body))
                            (v3/cross axis (v3/sub target-p (:joint-position pose)))
                            axis)]
               (-> jac
                   (assoc-in [0 dof] (nth axis 0))
                   (assoc-in [1 dof] (nth axis 1))
                   (assoc-in [2 dof] (nth axis 2))
                   (assoc-in [3 dof] (nth linear 0))
                   (assoc-in [4 dof] (nth linear 1))
                   (assoc-in [5 dof] (nth linear 2)))))))
       rows
       ancestor-indexes))))

(defn- motion-subspace [body]
  (case (:joint-type body)
    :revolute (sp/sv (:axis body) v3/zero)
    :prismatic (sp/sv v3/zero (:axis body))
    sp/zero-sv))

(defn- joint-transform [body qi]
  (case (:joint-type body)
    :revolute (sp/plucker (sp/mat3-transpose (axis-angle->mat3 (:axis body) qi)) v3/zero)
    :prismatic (sp/plucker sp/mat3-identity (v3/scale (:axis body) qi))
    (sp/from-blocks sp/mat3-identity sp/mat3-zero sp/mat3-zero sp/mat3-identity)))

(defn- kinematics
  "Spatial kinematics used by RNEA and CRBA. Every vector is body-frame."
  [cfg q qdot]
  (reduce
   (fn [{:keys [x v]} body]
     (let [qi (if (movable? body) (nth q (:dof body)) 0.0)
           qdi (if (movable? body) (nth qdot (:dof body)) 0.0)
           xi (sp/mat-mul (joint-transform body qi) (sp/plucker (:e-tree body) (:r-tree body)))
           parent-v (if (= -1 (:parent body)) sp/zero-sv (nth v (:parent body)))
           vj (sp/axpy qdi (motion-subspace body) sp/zero-sv)]
       {:x (conj x xi) :v (conj v (sp/axpy 1.0 vj (sp/mat-vec xi parent-v)))}))
   {:x [] :v []}
   (:bodies cfg)))

(defn- rnea-bias [cfg qdot {:keys [x v]}]
  (let [nb (count (:bodies cfg))
        base-a (sp/sv v3/zero (v3/neg (:gravity cfg)))]
    (loop [i 0 accelerations [] forces []]
      (if (= i nb)
        (loop [j (dec nb) accumulated forces tau (vec (repeat (:ndof cfg) 0.0))]
          (if (neg? j)
            tau
            (let [body (nth (:bodies cfg) j) force (nth accumulated j)
                  tau' (if (movable? body)
                         (assoc tau (:dof body) (sp/sv-dot (motion-subspace body) force))
                         tau)
                  accumulated' (if (= -1 (:parent body))
                                 accumulated
                                 (update accumulated (:parent body)
                                         #(sp/axpy 1.0 (sp/mat-vec (sp/transpose (nth x j)) force) %)))]
              (recur (dec j) accumulated' tau'))))
        (let [body (nth (:bodies cfg) i)
              qdi (if (movable? body) (nth qdot (:dof body)) 0.0)
              parent-a (if (= -1 (:parent body)) base-a (nth accelerations (:parent body)))
              vj (sp/axpy qdi (motion-subspace body) sp/zero-sv)
              ai (sp/axpy 1.0 (sp/mat-vec (sp/crm (nth v i)) vj)
                          (sp/mat-vec (nth x i) parent-a))
              iv (sp/mat-vec (:inertia body) (nth v i))
              fi (sp/axpy 1.0 (sp/mat-vec (sp/crf (nth v i)) iv)
                          (sp/mat-vec (:inertia body) ai))]
          (recur (inc i) (conj accelerations ai) (conj forces fi)))))))

(defn mass-matrix
  "Joint-space inertia M(q) from the Composite Rigid Body Algorithm."
  [cfg q]
  (let [{:keys [x]} (kinematics cfg q (vec (repeat (:ndof cfg) 0.0)))
        bodies (:bodies cfg)
        composite (loop [i (dec (count bodies)) ic (mapv :inertia bodies)]
                    (if (neg? i)
                      ic
                      (let [body (nth bodies i)]
                        (recur (dec i)
                               (if (= -1 (:parent body))
                                 ic
                                 (update ic (:parent body)
                                         #(sp/m-add % (sp/mat-mul (sp/mat-mul (sp/transpose (nth x i)) (nth ic i))
                                                                     (nth x i)))))))))]
    (loop [i 0 matrix (vec (repeat (:ndof cfg) (vec (repeat (:ndof cfg) 0.0))))]
      (if (= i (count bodies))
        matrix
        (let [body (nth bodies i)]
          (if-not (movable? body)
            (recur (inc i) matrix)
            (let [dof (:dof body) s (motion-subspace body)
                  f0 (sp/mat-vec (nth composite i) s)
                  diagonal (sp/sv-dot s f0)
                  next-matrix
                  (loop [j i f f0 result (assoc-in matrix [dof dof] diagonal)]
                    (let [f' (sp/mat-vec (sp/transpose (nth x j)) f)
                          parent (:parent (nth bodies j))]
                      (if (= -1 parent)
                        result
                        (let [parent-body (nth bodies parent)
                              result' (if (movable? parent-body)
                                        (let [value (sp/sv-dot (motion-subspace parent-body) f')
                                              parent-dof (:dof parent-body)]
                                          (-> result
                                              (assoc-in [dof parent-dof] value)
                                              (assoc-in [parent-dof dof] value)))
                                        result)]
                          (recur parent f' result')))))]
              (recur (inc i) next-matrix))))))))

(defn- solve-ldlt
  "Pure functional LDL^T solve for symmetric positive-definite matrices."
  [matrix rhs]
  (let [n (count rhs)]
    (when (and (= n (count matrix)) (every? #(= n (count %)) matrix))
      (let [factor (loop [j 0 l (vec (repeat n (vec (repeat n 0.0)))) d (vec (repeat n 0.0))]
                     (if (= j n)
                       [l d]
                       (let [dj (- (get-in matrix [j j])
                                   (reduce + (map (fn [k] (* (get-in l [j k]) (get-in l [j k]) (nth d k)))
                                                  (range j))))]
                         (when (< (Math/abs dj) 1e-12)
                           (throw (ex-info "singular mass matrix" {})))
                         (let [d' (assoc d j dj)
                               l' (reduce (fn [acc i]
                                            (let [value (/ (- (get-in matrix [i j])
                                                              (reduce + (map (fn [k] (* (get-in acc [i k])
                                                                                          (get-in acc [j k])
                                                                                          (nth d' k)))
                                                                             (range j))))
                                                           dj)]
                                              (assoc-in acc [i j] value)))
                                          (assoc-in l [j j] 1.0) (range (inc j) n))]
                           (recur (inc j) l' d')))))]
        (try
          (let [[l d] factor
                y (reduce (fn [values i]
                            (conj values (- (nth rhs i)
                                            (reduce + (map (fn [k] (* (get-in l [i k]) (nth values k)))
                                                           (range i)))))) [] (range n))
                z (mapv #(/ (nth y %) (nth d %)) (range n))]
            (reduce (fn [values i]
                      (assoc values i (- (nth z i)
                                         (reduce + (map (fn [k] (* (get-in l [k i]) (nth values k)))
                                                        (range (inc i) n))))))
                    (vec (repeat n 0.0)) (reverse (range n))))
          (catch #?(:clj Exception :cljs :default) _ nil))))))

(declare clamp)

(defn point-jacobian
  "3xN world-frame linear velocity Jacobian at a world point on `link-name`."
  [cfg state link-name point]
  (let [pose (link-pose cfg state link-name)
        geometric (geometric-jacobian cfg state link-name)
        offset (v3/sub point (:position pose))]
    (mapv (fn [component]
            (mapv (fn [wx wy wz vx vy vz]
                    (nth (v3/add (v3/cross [wx wy wz] offset) [vx vy vz]) component))
                  (nth geometric 0) (nth geometric 1) (nth geometric 2)
                  (nth geometric 3) (nth geometric 4) (nth geometric 5)))
          (range 3))))

(defn constraint-effective-mass
  "Return `J M^-1 J^T` for a scalar joint-space constraint row, or nil."
  [cfg state constraint-row]
  (let [m (mass-matrix cfg (:q state))]
    (when-let [response (solve-ldlt m constraint-row)]
      (let [value (reduce + (map * constraint-row response))]
        (when (> value 1e-12) {:effective-mass value :response response})))))

(defn apply-velocity-impulse
  "Apply scalar impulse along a joint-space constraint row to `state`."
  [cfg state constraint-row impulse]
  (if-let [{:keys [response]} (constraint-effective-mass cfg state constraint-row)]
    (update state :qdot #(mapv + % (mapv (fn [value] (* impulse value)) response)))
    state))

(defn forward-dynamics
  "Free articulated acceleration from applied joint torque. Returns qddot and M."
  [cfg {:keys [q qdot]} tau-applied]
  (let [q (state-q cfg {:q q}) qdot (vec qdot)
        _ (when-not (= (:ndof cfg) (count qdot))
            (throw (ex-info "state qdot length does not match articulation DOFs" {})))
        kin (kinematics cfg q qdot)
        bias (rnea-bias cfg qdot kin)
        m (mass-matrix cfg q)
        rhs (mapv (fn [dof]
                    (let [body (first (filter #(= (:dof %) dof) (:bodies cfg)))
                          applied (double (or (nth tau-applied dof nil) 0.0))
                          limited (if (pos? (:effort body))
                                    (clamp applied (- (:effort body)) (:effort body)) applied)]
                      (- limited (nth bias dof) (* (:damping body) (nth qdot dof)))))
                  (range (:ndof cfg)))]
    {:qddot (or (solve-ldlt m rhs) (vec (repeat (:ndof cfg) 0.0))) :mass-matrix m :bias bias}))

(defn inverse-dynamics
  "Joint torques that realize `qddot-des` at `state`.

  This is the exact inverse of `forward-dynamics`: `M*qddot + C + g + d*qdot`.
  It is useful for computed-torque control and gravity compensation."
  [cfg {:keys [q qdot]} qddot-des]
  (let [q (state-q cfg {:q q})
        qdot (vec qdot)
        _ (when-not (= (:ndof cfg) (count qdot))
            (throw (ex-info "state qdot length does not match articulation DOFs" {})))
        _ (when-not (= (:ndof cfg) (count qddot-des))
            (throw (ex-info "desired acceleration length does not match articulation DOFs" {})))
        bias (rnea-bias cfg qdot (kinematics cfg q qdot))
        m (mass-matrix cfg q)
        damping (into {} (keep #(when (movable? %) [(:dof %) (:damping %)])) (:bodies cfg))]
    (mapv (fn [i]
            (+ (nth bias i)
               (* (get damping i 0.0) (nth qdot i))
               (reduce + (map * (nth m i) qddot-des))))
          (range (:ndof cfg)))))

(defn gravity-torque
  "Joint torque that statically balances gravity at configuration `q`."
  [cfg q]
  (:bias (forward-dynamics cfg {:q q :qdot (vec (repeat (:ndof cfg) 0.0))}
                                (vec (repeat (:ndof cfg) 0.0)))))

(defn step
  "One contact-less semi-implicit Euler step under joint torque."
  [cfg state tau-applied]
  (let [{:keys [qddot]} (forward-dynamics cfg state tau-applied)
        qdot (mapv + (:qdot state) (map #(* (:dt cfg) %) qddot))
        by-dof (into {} (keep #(when (movable? %) [(:dof %) %])) (:bodies cfg))
        q (mapv (fn [dof qi qdi]
                  (let [body (get by-dof dof) candidate (+ qi (* (:dt cfg) qdi))]
                    (if (:has-limit? body) (clamp candidate (:lower body) (:upper body)) candidate)))
                (range (:ndof cfg)) (:q state) qdot)]
    {:q q
     :qdot (mapv (fn [dof qdi qi]
                    (let [body (get by-dof dof)]
                      (if (and (:has-limit? body) (or (= qi (:lower body)) (= qi (:upper body)))) 0.0 qdi)))
                  (range (:ndof cfg)) qdot q)}))

(defn- mat3-inverse [m]
  (let [[[a b c] [d e f] [g h i]] m
        a11 (- (* e i) (* f h))
        a12 (- (* c h) (* b i))
        a13 (- (* b f) (* c e))
        det (+ (* a a11) (* b a12) (* c a13))]
    (when (> (Math/abs det) 1e-12)
      (let [a21 (- (* f g) (* d i))
            a22 (- (* a i) (* c g))
            a23 (- (* c d) (* a f))
            a31 (- (* d h) (* e g))
            a32 (- (* b g) (* a h))
            a33 (- (* a e) (* b d))]
        (mapv (fn [row] (mapv #(/ % det) row))
              [[a11 a12 a13] [a21 a22 a23] [a31 a32 a33]])))))

(defn- clamp [value lower upper]
  (max lower (min upper value)))

(defn position-ik
  "Damped least-squares IK for a link's world position.

  Returns `{:state ... :converged? ... :iterations ... :error ...}`. It uses
  the world-frame linear rows of `geometric-jacobian`, honours finite URDF
  joint limits, and is intentionally independent of an Isaac runtime.
  Options are `:max-iterations` (80), `:tolerance` (1e-4), `:damping`
  (1e-3), and `:step-scale` (1.0)."
  ([cfg state link-name target]
   (position-ik cfg state link-name target {}))
  ([cfg state link-name target {:keys [max-iterations tolerance damping step-scale]
                               :or {max-iterations 80 tolerance 1e-4
                                    damping 1e-3 step-scale 1.0}}]
   (let [dof-bodies (into {} (keep (fn [body]
                                     (when (movable? body) [(:dof body) body])))
                           (:bodies cfg))]
     (loop [current state iteration 0]
       (let [pose (link-pose cfg current link-name)
             error (v3/sub target (:position pose))
             error-norm (v3/length error)]
         (cond
           (<= error-norm tolerance)
           {:state current :converged? true :iterations iteration :error error}

           (>= iteration max-iterations)
           {:state current :converged? false :iterations iteration :error error}

           :else
           (let [jac (geometric-jacobian cfg current link-name)
                 linear (subvec (vec jac) 3 6)
                 jjt (mapv (fn [row]
                             (mapv (fn [column]
                                     (reduce + (map * row column)))
                                   linear))
                           linear)
                 regularized (mapv (fn [row i] (update row i + (* damping damping)))
                                   jjt (range 3))
                 inv (mat3-inverse regularized)]
             (if-not inv
               {:state current :converged? false :iterations iteration :error error}
               (let [projected (sp/mat3-vec inv error)
                     dq (mapv (fn [dof]
                                (* step-scale
                                   (reduce + (map * (map #(nth % dof) linear) projected))))
                              (range (:ndof cfg)))
                     q (state-q cfg current)
                     next-q (mapv (fn [dof qi delta]
                                    (let [body (get dof-bodies dof)
                                          candidate (+ qi delta)]
                                      (if (:has-limit? body)
                                        (clamp candidate (:lower body) (:upper body))
                                        candidate)))
                                  (range (:ndof cfg)) q dq)]
                 (recur (assoc current :q next-q) (inc iteration)))))))))))

(defn- clamp-unit [value]
  (max -1.0 (min 1.0 value)))

(defn- so3-error
  "Shortest world-frame rotation vector from `current` to `target`."
  [target current]
  (let [r (sp/mat3-mul target (sp/mat3-transpose current))
        trace (+ (get-in r [0 0]) (get-in r [1 1]) (get-in r [2 2]))
        angle (Math/acos (clamp-unit (/ (- trace 1.0) 2.0)))]
    (if (< angle 1e-8)
      v3/zero
      (let [denominator (* 2.0 (Math/sin angle))]
        ;; Near pi the standard log map is poorly conditioned. The DLS update
        ;; remains well-defined with this finite axis approximation.
        (if (< (Math/abs denominator) 1e-8)
          (v3/scale (v3/normalize [(Math/sqrt (max 0.0 (/ (+ 1.0 (get-in r [0 0])) 2.0)))
                                    (Math/sqrt (max 0.0 (/ (+ 1.0 (get-in r [1 1])) 2.0)))
                                    (Math/sqrt (max 0.0 (/ (+ 1.0 (get-in r [2 2])) 2.0)))]) angle)
          (v3/scale [(/ (- (get-in r [2 1]) (get-in r [1 2])) denominator)
                     (/ (- (get-in r [0 2]) (get-in r [2 0])) denominator)
                     (/ (- (get-in r [1 0]) (get-in r [0 1])) denominator)] angle))))))

(defn pose-ik
  "Damped least-squares 6D world pose IK for `link-name`.

  `target-rotation` is a row-major 3x3 world rotation matrix. The result has
  the same shape as `position-ik`; lower-DOF mechanisms converge to their
  least-squares closest pose."
  ([cfg state link-name target-position target-rotation]
   (pose-ik cfg state link-name target-position target-rotation {}))
  ([cfg state link-name target-position target-rotation
    {:keys [max-iterations tolerance damping step-scale]
     :or {max-iterations 100 tolerance 1e-4 damping 1e-3 step-scale 1.0}}]
   (let [dof-bodies (into {} (keep #(when (movable? %) [(:dof %) %])) (:bodies cfg))]
     (loop [current state iteration 0]
       (let [pose (link-pose cfg current link-name)
             rotational (so3-error target-rotation (:rotation pose))
             positional (v3/sub target-position (:position pose))
             error (vec (concat rotational positional))
             error-norm (Math/sqrt (reduce + (map #(* % %) error)))]
         (cond
           (<= error-norm tolerance) {:state current :converged? true :iterations iteration :error error}
           (>= iteration max-iterations) {:state current :converged? false :iterations iteration :error error}
           :else
           (let [jacobian (geometric-jacobian cfg current link-name)
                 ;; A = J*J^T + lambda^2*I.
                 a (mapv (fn [i row] (update row i + (* damping damping)))
                         (range 6) (mapv (fn [row] (mapv (fn [column]
                                                            (reduce + (map * row column)))
                                                          jacobian)) jacobian))
                 y (solve-ldlt a error)]
             (if-not y
               {:state current :converged? false :iterations iteration :error error}
               (let [dq (mapv (fn [dof]
                                (* step-scale (reduce + (map (fn [row yi] (* (nth row dof) yi)) jacobian y))))
                              (range (:ndof cfg)))
                     q (state-q cfg current)
                     next-q (mapv (fn [dof qi delta]
                                    (let [body (get dof-bodies dof)
                                          candidate (+ qi delta)]
                                      (if (:has-limit? body)
                                        (clamp candidate (:lower body) (:upper body)) candidate)))
                                  (range (:ndof cfg)) q dq)]
                 (recur (assoc current :q next-q) (inc iteration)))))))))))
