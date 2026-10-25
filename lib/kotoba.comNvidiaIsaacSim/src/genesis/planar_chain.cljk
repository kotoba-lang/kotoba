(ns genesis.planar-chain
  "Planar n-link revolute serial chain — generalizes double-pendulum to N
  joints. All revolute joints rotate about world +y; chain lies in the xz
  plane; gravity points along -z. Uniform-rod assumption (COM at half
  length, inertia about COM = m*l^2/12).

  Forward dynamics via M(q)*qddot = tau - h(q, qdot):
    - h is the RNEA bias force (qddot = 0)
    - M(q) is the CRBA joint-space inertia matrix
  Solved by in-place Cholesky LDL^T.

  At N=2 this reduces to `genesis.double-pendulum` (verified by
  `n2-matches-double-pendulum-dynamics` in the test suite).

  Restored from kotoba-lang/kami-engine `kami-genesis/src/planar_chain.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930.
  Ported 1:1 (fully portable pure math/data)."
  )

(defn uniform-config
  "A uniform N-link chain with each link mass=1.0 kg, length=1.0 m."
  [n]
  {:n n
   :masses (vec (repeat n 1.0))
   :lengths (vec (repeat n 1.0))
   :gravity 9.81
   :effort-limit 50.0
   :dt (/ 1.0 240.0)})

(defn zeros-state [n]
  {:q (vec (repeat n 0.0)) :qdot (vec (repeat n 0.0))})

(defn clamp [v lo hi] (max lo (min hi v)))

(defn- rnea-planar
  "Recursive Newton-Euler inverse dynamics for the planar chain. Returns
  tau[i] for i in 0..n. If `with-gravity?` is false, gravity is dropped
  (used inside CRBA where the gravity bias is not part of M)."
  [q qdot qddot {:keys [n lengths masses gravity]} with-gravity?]
  (let [g (if with-gravity? gravity 0.0)
        theta (double-array n)
        omega (double-array n)
        alpha (double-array n)
        a-com-x (double-array n)
        a-com-z (double-array n)
        a-joint-x (double-array (inc n))
        a-joint-z (double-array (inc n))
        p-com-x (double-array n)
        p-com-z (double-array n)
        p-joint-x (double-array (inc n))
        p-joint-z (double-array (inc n))]
    (loop [i 0 cum-theta 0.0 cum-omega 0.0 cum-alpha 0.0]
      (when (< i n)
        (let [cum-theta (+ cum-theta (nth q i))
              cum-omega (+ cum-omega (nth qdot i))
              cum-alpha (+ cum-alpha (nth qddot i))
              s (Math/sin cum-theta) c (Math/cos cum-theta)
              l (nth lengths i) lc (* l 0.5)
              prev-pjx (aget p-joint-x i) prev-pjz (aget p-joint-z i)
              prev-ajx (aget a-joint-x i) prev-ajz (aget a-joint-z i)]
          (aset theta i cum-theta) (aset omega i cum-omega) (aset alpha i cum-alpha)
          (aset p-com-x i (+ prev-pjx (* lc s)))
          (aset p-com-z i (- prev-pjz (* lc c)))
          (aset a-com-x i (+ prev-ajx (* lc (- (* cum-alpha c) (* cum-omega cum-omega s)))))
          (aset a-com-z i (+ prev-ajz (* lc (+ (* cum-alpha s) (* cum-omega cum-omega c)))))
          (let [pj-next-x (+ prev-pjx (* l s))
                pj-next-z (- prev-pjz (* l c))
                aj-next-x (+ prev-ajx (* l (- (* cum-alpha c) (* cum-omega cum-omega s))))
                aj-next-z (+ prev-ajz (* l (+ (* cum-alpha s) (* cum-omega cum-omega c))))]
            (aset p-joint-x (inc i) pj-next-x) (aset p-joint-z (inc i) pj-next-z)
            (aset a-joint-x (inc i) aj-next-x) (aset a-joint-z (inc i) aj-next-z))
          (recur (inc i) cum-theta cum-omega cum-alpha))))
    (vec
      (for [i (range n)]
        (reduce
          (fn [tau-i k]
            (let [m (nth masses k) lk (nth lengths k)
                  i-com (/ (* m lk lk) 12.0)
                  f-x (* m (aget a-com-x k))
                  f-z (* m (+ (aget a-com-z k) g))
                  r-x (- (aget p-com-x k) (aget p-joint-x i))
                  r-z (- (aget p-com-z k) (aget p-joint-z i))
                  torque-q (- (* r-x f-z) (* r-z f-x))]
              (+ tau-i torque-q (* i-com (aget alpha k)))))
          0.0
          (range i n))))))

(defn- mass-matrix-crba
  "Column j of M = RNEA(q, qdot=0, qddot=e_j, gravity=0)."
  [q {:keys [n] :as cfg}]
  (let [zero (vec (repeat n 0.0))
        cols (vec (for [j (range n)]
                     (rnea-planar q zero (assoc zero j 1.0) cfg false)))
        m (vec (for [i (range n)] (vec (for [j (range n)] (get-in cols [j i])))))]
    ;; symmetrize numerically
    (vec (for [i (range n)]
           (vec (for [j (range n)]
                  (if (= i j)
                    (get-in m [i j])
                    (* 0.5 (+ (get-in m [i j]) (get-in m [j i]))))))))))

(defn- solve-ldlt
  "Solve M*x = b for symmetric positive-definite M via LDL^T, returns x or
  nil if not SPD."
  [mat b]
  (let [n (count b)]
    (if (or (not= (count mat) n) (some #(not= (count %) n) mat))
      nil
      (let [a (to-array (map double-array mat))]
        (try
          (dotimes [j n]
            (let [ajj (aget ^doubles (aget a j) j)
                  sum (reduce (fn [s k]
                                (- s (* (aget ^doubles (aget a j) k)
                                        (aget ^doubles (aget a j) k)
                                        (aget ^doubles (aget a k) k))))
                              ajj (range j))]
              (when (< (Math/abs sum) 1e-12) (throw (ex-info "singular" {})))
              (aset ^doubles (aget a j) j sum)
              (doseq [i (range (inc j) n)]
                (let [s (reduce (fn [s k]
                                   (- s (* (aget ^doubles (aget a i) k)
                                           (aget ^doubles (aget a j) k)
                                           (aget ^doubles (aget a k) k))))
                                 (aget ^doubles (aget a i) j) (range j))]
                  (aset ^doubles (aget a i) j (/ s (aget ^doubles (aget a j) j)))))))
          (let [y (double-array n)]
            (dotimes [i n]
              (aset y i (reduce (fn [s k] (- s (* (aget ^doubles (aget a i) k) (aget y k))))
                                 (nth b i) (range i))))
            (let [z (double-array n)]
              (dotimes [i n] (aset z i (/ (aget y i) (aget ^doubles (aget a i) i))))
              (let [x (double-array n)]
                (doseq [i (reverse (range n))]
                  (aset x i (reduce (fn [s k] (- s (* (aget ^doubles (aget a k) i) (aget x k))))
                                     (aget z i) (range (inc i) n))))
                (vec x))))
          (catch #?(:clj Exception :cljs :default) _ nil))))))

(defn step
  "Semi-implicit Euler step under joint torques `tau` (clamped to
  ±effort-limit). Returns the next state."
  [{:keys [q qdot]} tau {:keys [n effort-limit dt] :as cfg}]
  (let [tau-clamped (mapv #(clamp % (- effort-limit) effort-limit) tau)
        h (rnea-planar q qdot (vec (repeat n 0.0)) cfg true)
        m (mass-matrix-crba q cfg)
        rhs (mapv - tau-clamped h)
        qddot (or (solve-ldlt m rhs) (vec (repeat n 0.0)))
        qdot' (vec (map + qdot (map #(* dt %) qddot)))
        q' (vec (map + q (map #(* dt %) qdot')))]
    {:q q' :qdot qdot'}))

(defn energy
  "Total mechanical energy (KE + PE)."
  [{:keys [q qdot]} {:keys [n lengths masses gravity]}]
  (loop [i 0 theta-cum 0.0 omega-cum 0.0
         pjx 0.0 pjz 0.0 vjx 0.0 vjz 0.0 ke 0.0 pe 0.0]
    (if (>= i n)
      (+ ke pe)
      (let [theta-cum (+ theta-cum (nth q i))
            omega-cum (+ omega-cum (nth qdot i))
            l (nth lengths i) lc (* l 0.5) m (nth masses i)
            s (Math/sin theta-cum) c (Math/cos theta-cum)
            p-com-z (- pjz (* lc c))
            v-com-x (+ vjx (* lc omega-cum c))
            v-com-z (+ vjz (* lc omega-cum s))
            i-com (/ (* m l l) 12.0)
            ke' (+ ke (* 0.5 m (+ (* v-com-x v-com-x) (* v-com-z v-com-z)))
                   (* 0.5 i-com omega-cum omega-cum))
            pe' (+ pe (* m gravity p-com-z))]
        (recur (inc i) theta-cum omega-cum
               (+ pjx (* l s)) (- pjz (* l c))
               (+ vjx (* l omega-cum c)) (+ vjz (* l omega-cum s))
               ke' pe')))))
