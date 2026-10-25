(ns kotoba.lang.kami-nv-compat.dynamics.articulated-dynamics
  "Featherstone-1983 articulated-body dynamics — JVM port of
  src/dynamics/articulated-dynamics.ts (the Python iter 68-70 reference, ported
  algorithm-for-algorithm). Pure, zero runtime deps (the in-browser pure-JS
  fallback for the kami-engine Rust->wasm32 substrate).

  Spatial-vector convention (Featherstone 2008):
    v = [angular_x angular_y angular_z linear_x linear_y linear_z]
  6×6 Plücker transforms + spatial inertias are nested vectors.

  WAVE 13 (foundation): 3×3 matrix helpers + spatial-inertia. The 6×6
  spatial-algebra helpers (mat66-*, vec6-*, outer6, spatial-cross-*, plucker,
  joint-motion-*), buildArticulation, forward-kinematics, geometric-Jacobian,
  and the ABA/RNEA/CRBA solvers land in the waves that consume them. Pure data
  shapes (UrdfLink/Joint/System are plain maps; see
  kotoba.lang.kami-nv-compat.dynamics.urdf-parser). ADR-2607020130.")

;; ── 3-vector / 3×3 matrix helpers ─────────────────────────────────────────

(defn skew3 [v]
  [[0 (- (v 2)) (v 1)]
   [(v 2) 0 (- (v 0))]
   [(- (v 1)) (v 0) 0]])

(defn mat3-mul [a b]
  (vec (for [i (range 3)]
         (vec (for [j (range 3)]
                (loop [k 0 s 0]
                  (if (>= k 3) s
                    (recur (inc k) (+ s (* (get-in a [i k]) (get-in b [k j])))))))))))

(defn mat3-t [a]
  [[(get-in a [0 0]) (get-in a [1 0]) (get-in a [2 0])]
   [(get-in a [0 1]) (get-in a [1 1]) (get-in a [2 1])]
   [(get-in a [0 2]) (get-in a [1 2]) (get-in a [2 2])]])

(defn mat3-add [a b]
  (vec (for [i (range 3)] (vec (for [j (range 3)] (+ (get-in a [i j]) (get-in b [i j])))))))

(defn mat3-scale [a s]
  (vec (for [i (range 3)] (vec (for [j (range 3)] (* (get-in a [i j]) s))))))

(defn rot-from-rpy [rpy]
  (let [[r p y] rpy
        cr (Math/cos r) sr (Math/sin r)
        cp (Math/cos p) sp (Math/sin p)
        cy (Math/cos y) sy (Math/sin y)]
    [[(* cy cp) (- (* cy sp sr) (* sy cr)) (+ (* cy sp cr) (* sy sr))]
     [(* sy cp) (+ (* sy sp sr) (* cy cr)) (- (* sy sp cr) (* cy sr))]
     [(- sp) (* cp sr) (* cp cr)]]))

(defn rodrigues-rotation [axis angle]
  (let [[ax ay az] axis
        c (Math/cos angle) s (Math/sin angle) oc (- 1 c)]
    [[(+ c (* ax ax oc)) (- (* ax ay oc) (* az s)) (+ (* ax az oc) (* ay s))]
     [(+ (* ay ax oc) (* az s)) (+ c (* ay ay oc)) (- (* ay az oc) (* ax s))]
     [(- (* az ax oc) (* ay s)) (+ (* az ay oc) (* ax s)) (+ c (* az az oc))]]))

;; ── spatial inertia from a link ───────────────────────────────────────────

(defn- zeros66 [] (vec (repeat 6 (vec (repeat 6 0)))))

(defn spatial-inertia-from-link
  "6×6 spatial inertia of a link (mass, full inertia tensor, COM offset)."
  [link]
  (let [{:keys [mass ixx iyy izz ixy ixz iyz]} (:inertia link)
        c (:xyz (:com (:inertia link)))
        Ic [[ixx ixy ixz] [ixy iyy iyz] [ixz iyz izz]]
        skC (skew3 c)
        pseudo (mat3-scale (mat3-mul skC (mat3-t skC)) mass)
        upper-left (mat3-add Ic pseudo)
        mSkC (mat3-scale skC mass)
        mSkCt (mat3-t mSkC)
        I (atom (zeros66))]
    (doseq [i (range 3) j (range 3)]
      (swap! I (fn [m] (-> m
                           (assoc-in [i j]             (get-in upper-left [i j]))
                           (assoc-in [i (+ j 3)]       (get-in mSkC [i j]))
                           (assoc-in [(+ i 3) j]       (get-in mSkCt [i j]))
                           (assoc-in [(+ i 3) (+ j 3)] (if (= i j) mass 0))))))
    @I))

;; ── Plücker transform + joint motion subspace (build helpers) ─────────────

(defn- plucker-transform [rot-child-to-parent r]
  (let [Rt (mat3-t rot-child-to-parent)
        RtSkr (mat3-mul Rt (skew3 r))
        out (atom (zeros66))]
    (doseq [i (range 3) j (range 3)]
      (swap! out (fn [m] (-> m
                             (assoc-in [i j]             (get-in Rt [i j]))
                             (assoc-in [(+ i 3) j]       (- (get-in RtSkr [i j])))
                             (assoc-in [(+ i 3) (+ j 3)] (get-in Rt [i j]))))))
    @out))

(defn- joint-motion-subspace [joint]
  (let [[ax ay az] (:axis joint)
        n (Math/sqrt (+ (* ax ax) (* ay ay) (* az az)))]
    (if (< n 1e-12)
      [0 0 0 0 0 0]
      (let [ux (/ ax n) uy (/ ay n) uz (/ az n)]
        (condp = (:kind joint)
          "revolute"   [ux uy uz 0 0 0]
          "continuous" [ux uy uz 0 0 0]
          "prismatic"  [0 0 0 ux uy uz]
          [0 0 0 0 0 0])))))                       ; fixed

;; ── BuiltArticulation ─────────────────────────────────────────────────────

(defn build-articulation
  "Build the runtime articulation model from a parsed URDF system. Fixed joints
  are fused; :parent-joint is -1 for joints rooted at the base link."
  [sys]
  (let [children (set (map :child (:joints sys)))
        base-links (filter #(not (contains? children (:name %))) (:links sys))]
    (when (not= 1 (count base-links))
      (throw (ex-info (str "build-articulation: expected exactly 1 base link; found "
                           (count base-links)) {:base-links (mapv :name base-links)})))
    (let [base-name (:name (first base-links))
          link-by-name (into {} (for [l (:links sys)] [(:name l) l]))
          moving (vec (filter #(not= (:kind %) "fixed") (:joints sys)))
          n (count moving)]
      (if (zero? n)
        {:n 0 :joint-names [] :joint-kinds [] :parent-joint [] :motion-subspace []
         :fixed-origin-transform [] :child-link-inertia [] :joint-damping []
         :joint-friction [] :rpy-rotation-matrix [] :xyz-translation [] :joint-axis []}
        (let [link->parent-joint (into {} (map-indexed (fn [i j] [(:child j) i]) moving))
              parent-joint (vec (for [j moving]
                                  (loop [cursor (:parent j) pidx -1 guard 0]
                                    (cond
                                      (or (>= guard 1000) (= cursor base-name)) pidx
                                      (link->parent-joint cursor)                (link->parent-joint cursor)
                                      :else (if-let [upstream (first (filter #(= (:child %) cursor) (:joints sys)))]
                                              (recur (:parent upstream) pidx (inc guard))
                                              pidx)))))
              joint-axis (vec (for [j moving]
                                (let [[ax ay az] (:axis j)
                                      an (Math/sqrt (+ (* ax ax) (* ay ay) (* az az)))]
                                  (if (< an 1e-12) [0 0 1] [(/ ax an) (/ ay an) (/ az an)]))))]
          {:n n
           :joint-names  (mapv :name moving)
           :joint-kinds  (mapv :kind moving)
           :parent-joint parent-joint
           :motion-subspace     (mapv joint-motion-subspace moving)
           :fixed-origin-transform (vec (for [j moving]
                                          (plucker-transform (rot-from-rpy (get-in j [:origin :rpy]))
                                                             (get-in j [:origin :xyz]))))
           :child-link-inertia   (vec (for [j moving]
                                        (let [link (link-by-name (:child j))]
                                          (when-not link
                                            (throw (ex-info (str "build-articulation: missing child link " (:child j)) {})))
                                          (spatial-inertia-from-link link))))
           :joint-damping   (mapv #(get % :damping 0) moving)
           :joint-friction  (mapv #(get % :friction 0) moving)
           :rpy-rotation-matrix (mapv #(rot-from-rpy (get-in % [:origin :rpy])) moving)
           :xyz-translation     (mapv #(get-in % [:origin :xyz]) moving)
           :joint-axis          joint-axis})))))

(defn make-zero-state
  "Zero generalized coords/velocities/accelerations for an n-DoF articulation."
  [n]
  {:q (vec (repeat n 0)) :qdot (vec (repeat n 0)) :qddot (vec (repeat n 0))})

;; ── Forward kinematics ────────────────────────────────────────────────────

(defn- mat3-vec [m v]
  (vec (for [i (range 3)]
         (+ (* (get-in m [i 0]) (v 0))
            (* (get-in m [i 1]) (v 1))
            (* (get-in m [i 2]) (v 2))))))

(defn forward-kinematics
  "World-frame pose {:R 3×3 :p 3} per joint, composing up the parent chain."
  [built q]
  (when (not= (count q) (:n built))
    (throw (ex-info (str "forward-kinematics: q length must be " (:n built)) {:got (count q)})))
  (loop [i 0 out []]
    (if (>= i (:n built))
      out
      (let [Rorigin (get-in built [:rpy-rotation-matrix i])
            porigin (get-in built [:xyz-translation i])
            axis    (get-in built [:joint-axis i])
            kind    (get-in built [:joint-kinds i])
            [Ri-in-parent pi-in-parent]
            (condp = kind
              "revolute"   [(mat3-mul Rorigin (rodrigues-rotation axis (q i))) porigin]
              "continuous" [(mat3-mul Rorigin (rodrigues-rotation axis (q i))) porigin]
              "prismatic"  [Rorigin (vec (map + porigin (mat3-vec Rorigin (mapv #(* (q i) %) axis))))]
              [Rorigin porigin])                                  ; fixed
            pidx (get-in built [:parent-joint i])
            [Rworld pworld]
            (if (neg? pidx)
              [Ri-in-parent pi-in-parent]
              (let [Rparent (get-in out [pidx :R])
                    pparent (get-in out [pidx :p])]
                [(mat3-mul Rparent Ri-in-parent)
                 (vec (map + (mat3-vec Rparent pi-in-parent) pparent))]))]
        (recur (inc i) (conj out {:R Rworld :p pworld}))))))

;; ── Geometric Jacobian ────────────────────────────────────────────────────

(defn- is-ancestor [built ancestor descendant]
  (loop [cur descendant]
    (cond
      (neg? cur)            false
      (= cur ancestor)      true
      :else                 (recur (get-in built [:parent-joint cur])))))

(defn geometric-jacobian
  "6×n geometric Jacobian (Featherstone [ω; v]: rows 0-2 angular, 3-5 linear)
  at `target-joint-idx`'s frame (optionally offset by `point-offset-body`)."
  ([built q target-joint-idx]
   (geometric-jacobian built q target-joint-idx nil))
  ([built q target-joint-idx point-offset-body]
   (let [n (:n built)]
     (when (or (neg? target-joint-idx) (>= target-joint-idx n))
       (throw (ex-info (str "geometric-jacobian: target-joint-idx=" target-joint-idx
                            " out of range [0, " n ")") {:target target-joint-idx :n n})))
     (let [poses (forward-kinematics built q)
           {Rtarget :R ptarget-orig :p} (poses target-joint-idx)
           ptarget (if point-offset-body
                     (do (when (not= 3 (count point-offset-body))
                           (throw (ex-info "point-offset-body must be 3-vec" {:got (count point-offset-body)})))
                         (vec (map + ptarget-orig (mat3-vec Rtarget point-offset-body))))
                     ptarget-orig)
           J (atom (vec (repeat 6 (vec (repeat n 0)))))]
       (doseq [i (range n)]
         (when (is-ancestor built i target-joint-idx)
           (let [{Rworld :R pworld :p} (poses i)
                 a-world (mat3-vec Rworld (get-in built [:joint-axis i]))
                 kind    (get-in built [:joint-kinds i])]
             (if (or (= kind "revolute") (= kind "continuous"))
               (let [dp     (vec (map - ptarget pworld))
                     linear [(- (* (a-world 1) (dp 2)) (* (a-world 2) (dp 1)))
                             (- (* (a-world 2) (dp 0)) (* (a-world 0) (dp 2)))
                             (- (* (a-world 0) (dp 1)) (* (a-world 1) (dp 0)))]]
                 (doseq [k (range 3)]
                   (swap! J assoc-in [k i]       (a-world k))
                   (swap! J assoc-in [(+ k 3) i] (linear k))))
               (when (= kind "prismatic")
                 (doseq [k (range 3)]
                   (swap! J assoc-in [(+ k 3) i] (a-world k))))))))
       @J))))

;; ── 6×6 spatial-matrix helpers ───────────────────────────────────────────

(defn- mat66-mul [a b]
  (vec (for [i (range 6)] (vec (for [j (range 6)]
    (loop [k 0 s 0] (if (>= k 6) s (recur (inc k) (+ s (* (get-in a [i k]) (get-in b [k j])))))))))))

(defn- mat66-t [a] (vec (for [i (range 6)] (vec (for [j (range 6)] (get-in a [j i]))))))

(defn- mat66-vec [a v]
  (vec (for [i (range 6)] (loop [k 0 s 0] (if (>= k 6) s (recur (inc k) (+ s (* (get-in a [i k]) (v k)))))))))

(defn- mat66-scale [a s] (vec (for [i (range 6)] (vec (for [j (range 6)] (* (get-in a [i j]) s))))))

(defn- mat66-sub [a b] (vec (for [i (range 6)] (vec (for [j (range 6)] (- (get-in a [i j]) (get-in b [i j])))))))

(defn- mat66-add [a b] (vec (for [i (range 6)] (vec (for [j (range 6)] (+ (get-in a [i j]) (get-in b [i j])))))))

(defn- vec6-add [a b] (vec (for [i (range 6)] (+ (a i) (b i)))))
(defn- vec6-scale [a s] (vec (for [i (range 6)] (* (a i) s))))
(defn- vec6-dot [a b] (loop [i 0 s 0] (if (>= i 6) s (recur (inc i) (+ s (* (a i) (b i)))))))
(defn- outer6 [a b] (vec (for [i (range 6)] (vec (for [j (range 6)] (* (a i) (b j)))))))

(defn- spatial-cross-motion [v]
  (let [skw (skew3 [(v 0) (v 1) (v 2)]) sku (skew3 [(v 3) (v 4) (v 5)]) out (atom (zeros66))]
    (doseq [i (range 3) j (range 3)]
      (swap! out (fn [m] (-> m (assoc-in [i j] (get-in skw [i j])) (assoc-in [(+ i 3) j] (get-in sku [i j])) (assoc-in [(+ i 3) (+ j 3)] (get-in skw [i j]))))))
    @out))

(defn- spatial-cross-force [v]
  (let [skw (skew3 [(v 0) (v 1) (v 2)]) sku (skew3 [(v 3) (v 4) (v 5)]) out (atom (zeros66))]
    (doseq [i (range 3) j (range 3)]
      (swap! out (fn [m] (-> m (assoc-in [i j] (get-in skw [i j])) (assoc-in [i (+ j 3)] (get-in sku [i j])) (assoc-in [(+ i 3) (+ j 3)] (get-in skw [i j]))))))
    @out))

(defn- identity3 [] [[1 0 0] [0 1 0] [0 0 1]])
(defn- identity6 [] (let [out (atom (zeros66))] (doseq [i (range 6)] (swap! out assoc-in [i i] 1)) @out))

(defn- joint-motion-transform [kind axis-unit q]
  (condp = kind
    "revolute"   (plucker-transform (rodrigues-rotation axis-unit q) [0 0 0])
    "continuous" (plucker-transform (rodrigues-rotation axis-unit q) [0 0 0])
    "prismatic"  (plucker-transform (identity3) [(* q (axis-unit 0)) (* q (axis-unit 1)) (* q (axis-unit 2))])
    (identity6)))

(defn- compute-joint-transforms [built q]
  (vec (for [i (range (:n built))]
    (mat66-mul (joint-motion-transform (get-in built [:joint-kinds i]) (get-in built [:joint-axis i]) (q i))
               (get-in built [:fixed-origin-transform i])))))

;; ── RNEA inverse dynamics ─────────────────────────────────────────────────

(defn- rnea-compute
  [built q qdot qddot gravity n]
  (let [X (compute-joint-transforms built q)
        v (atom []) a (atom []) f (atom [])
        a-base [0 0 0 (- (gravity 0)) (- (gravity 1)) (- (gravity 2))]]
    (dotimes [i n]
      (let [Si (get-in built [:motion-subspace i])
            Sq (vec6-scale Si (qdot i))
            Sqd (vec6-scale Si (qddot i))
            pidx (get-in built [:parent-joint i])
            vp-in (if (neg? pidx) [0 0 0 0 0 0] (mat66-vec (X i) (@v pidx)))
            ap-in (if (neg? pidx) (mat66-vec (X i) a-base) (mat66-vec (X i) (@a pidx)))
            vi (vec6-add vp-in Sq)]
        (swap! v conj vi)
        (swap! a conj (vec6-add (vec6-add ap-in Sqd) (mat66-vec (spatial-cross-motion vi) Sq)))
        (let [Ii (get-in built [:child-link-inertia i])]
          (swap! f conj (vec6-add (mat66-vec Ii (@a i)) (mat66-vec (spatial-cross-force vi) (mat66-vec Ii vi)))))))
    (let [tau (atom (vec (repeat n 0)))]
      (doseq [k (range n)]
        (let [i (- n 1 k) Si (get-in built [:motion-subspace i])]
          (swap! tau assoc i (+ (vec6-dot Si (@f i)) (* (get-in built [:joint-damping i]) (qdot i))))
          (let [pidx (get-in built [:parent-joint i])]
            (when (>= pidx 0)
              (let [Xt (mat66-t (X i))]
                (swap! f update pidx (fn [old] (vec6-add old (mat66-vec Xt (@f i))))))))))
      @tau)))

(defn rnea-inverse-dynamics
  ([built q qdot qddot]
   (rnea-inverse-dynamics built q qdot qddot [0 0 -9.81]))
  ([built q qdot qddot gravity]
   (let [n (:n built)]
     (if (zero? n) [] (rnea-compute built q qdot qddot gravity n)))))

(defn coriolis-gravity-vector
  ([built q qdot] (coriolis-gravity-vector built q qdot [0 0 -9.81]))
  ([built q qdot gravity] (rnea-inverse-dynamics built q qdot (vec (repeat (:n built) 0)) gravity)))

;; ── ABA forward dynamics ─────────────────────────────────────────────────

(defn- aba-pass2!
  [built X Ia pa c n tau]
  (let [U (atom (vec (repeat n nil))) D (atom (vec (repeat n 0))) u (atom (vec (repeat n 0)))]
    (doseq [k (range n)]
      (let [i (- n 1 k) Si (get-in built [:motion-subspace i])]
        (swap! U assoc i (mat66-vec (@Ia i) Si))
        (let [d0 (+ (vec6-dot Si (@U i)) (get-in built [:joint-damping i]))
              d (if (< (Math/abs d0) 1e-12) 1e-12 d0)]
          (swap! D assoc i d))
        (swap! u assoc i (- (tau i) (vec6-dot Si (@pa i))))
        (let [pidx (get-in built [:parent-joint i])]
          (when (>= pidx 0)
            (let [Di (@D i)
                  Uo (mat66-scale (outer6 (@U i) (@U i)) (/ 1.0 Di))
                  inner (mat66-sub (@Ia i) Uo)
                  Xt (mat66-t (X i))
                  contrib-i (mat66-mul (mat66-mul Xt inner) (X i))
                  Ia-c (mat66-vec (@Ia i) (@c i))
                  Uu (vec6-scale (@U i) (/ (@u i) Di))
                  sum-term (vec6-add (vec6-add (@pa i) Ia-c) Uu)
                  contrib-p (mat66-vec Xt sum-term)]
              (swap! Ia update pidx (fn [old] (mat66-add old contrib-i)))
              (swap! pa update pidx (fn [old] (vec6-add old contrib-p))))))))
    {:U @U :D @D :u @u}))

(defn- aba-compute
  [built q qdot tau gravity n]
  (let [X (compute-joint-transforms built q)
        v (atom []) c (atom [])
        Ia (atom (mapv (fn [m] (mapv vec m)) (:child-link-inertia built)))
        pa (atom [])]
    (dotimes [i n]
      (let [Si (get-in built [:motion-subspace i])
            Sq (vec6-scale Si (qdot i))
            pidx (get-in built [:parent-joint i])
            vp-in-i (if (neg? pidx) [0 0 0 0 0 0] (mat66-vec (X i) (@v pidx)))
            vi (vec6-add vp-in-i Sq)]
        (swap! v conj vi)
        (swap! c conj (mat66-vec (spatial-cross-motion vi) Sq))))
    (dotimes [i n]
      (let [Iv (mat66-vec (@Ia i) (@v i))]
        (swap! pa conj (mat66-vec (spatial-cross-force (@v i)) Iv))))
    (let [{:keys [U D u]} (aba-pass2! built X Ia pa c n tau)
          a-base [0 0 0 (- (gravity 0)) (- (gravity 1)) (- (gravity 2))]
          a (atom (vec (repeat n nil)))]
      (vec (for [i (range n)]
        (let [pidx (get-in built [:parent-joint i])
              ap-in (if (neg? pidx) (mat66-vec (X i) a-base) (mat66-vec (X i) (@a pidx)))
              a-prime (vec6-add ap-in (@c i))
              qddot-i (/ (- (u i) (vec6-dot (U i) a-prime)) (D i))]
          (swap! a assoc i (vec6-add a-prime (vec6-scale (get-in built [:motion-subspace i]) qddot-i)))
          qddot-i))))))

(defn aba-forward
  ([built q qdot tau] (aba-forward built q qdot tau [0 0 -9.81]))
  ([built q qdot tau gravity]
   (let [n (:n built)]
     (if (zero? n) [] (aba-compute built q qdot tau gravity n)))))

(defn articulated-step
  ([built state tau dt] (articulated-step built state tau dt [0 0 -9.81]))
  ([built state tau dt gravity]
   (let [{:keys [q qdot]} state
         qddot (aba-forward built q qdot tau gravity)
         qdot' (vec (map-indexed (fn [i qd] (+ qd (* dt (qddot i)))) qdot))
         q' (vec (map-indexed (fn [i qi] (+ qi (* dt (qdot' i)))) q))]
     {:q q' :qdot qdot' :qddot qddot})))

;; ── CRBA: joint-space inertia matrix ──────────────────────────────────────

(defn crba-mass-matrix [built q]
  (let [n (:n built)]
    (assert (= (count q) n) (str "crba-mass-matrix: q length must be " n))
    (if (zero? n) []
      (let [X (compute-joint-transforms built q)
            Ic (atom (mapv (fn [m] (mapv vec m)) (:child-link-inertia built)))]
        (doseq [k (range n)]
          (let [i (- n 1 k) pidx (get-in built [:parent-joint i])]
            (when (>= pidx 0)
              (let [Xt (mat66-t (X i)) contrib (mat66-mul (mat66-mul Xt (@Ic i)) (X i))]
                (swap! Ic update pidx (fn [old] (mat66-add old contrib)))))))
        (let [M (atom (vec (repeat n (vec (repeat n 0)))))]
          (dotimes [i n]
            (let [Si (get-in built [:motion-subspace i]) F0 (mat66-vec (@Ic i) Si)]
              (swap! M assoc-in [i i] (vec6-dot Si F0))
              (loop [j i F F0]
                (let [pj (get-in built [:parent-joint j])]
                  (when (>= pj 0)
                    (let [F' (mat66-vec (mat66-t (X j)) F) Sj (get-in built [:motion-subspace pj])
                          m-ij (vec6-dot Sj F')]
                      (swap! M assoc-in [i pj] m-ij)
                      (swap! M assoc-in [pj i] m-ij)
                      (recur pj F')))))))
          @M)))))

(defn kinetic-energy [built q qdot]
  (let [M (crba-mass-matrix built q) n (:n built)]
    (* 0.5 (reduce + (for [i (range n)]
      (* (qdot i) (reduce + (for [j (range n)] (* (get-in M [i j]) (qdot j))))))))))
