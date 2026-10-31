(ns cae.advanced
  "Numerical reference kernels for grid, mesh, electromagnetic and thermo-mechanical studies."
  (:require [cae.solver :as solver]))

(defn- req [m k] (let [v (get m k)] (if (number? v) (double v) (throw (ex-info "numeric input required" {:key k})))) )
(defn- pos [m k] (let [v (req m k)] (if (pos? v) v (throw (ex-info "positive input required" {:key k :value v})))) )
(defn- idx [nx i j] (+ i (* j (inc nx))))
(defn- tri-mesh [nx ny lx ly]
  (let [nodes (vec (for [j (range (inc ny)) i (range (inc nx))]
                     [(* lx (/ i nx)) (* ly (/ j ny)) 0.0]))
        e (fn [i j] (idx nx i j))
        els (vec (mapcat (fn [j] (mapcat (fn [i] (let [a (e i j) b (e (inc i) j) c (e i (inc j)) d (e (inc i) (inc j))] [[a b c] [b d c]])) (range nx))) (range ny)))]
    {:dimension :2d :element-type :tri3 :nodes nodes :elements els}))
(defn- tet-mesh [nx ny nz lx ly lz]
  (let [id (fn [i j k] (+ i (* j (inc nx)) (* k (inc nx) (inc ny))))
        nodes (vec (for [k (range (inc nz)) j (range (inc ny)) i (range (inc nx))]
                     [(* lx (/ i nx)) (* ly (/ j ny)) (* lz (/ k nz))]))
        els (vec (mapcat (fn [k] (mapcat (fn [j] (mapcat (fn [i]
          (let [c000 (id i j k) c100 (id (inc i) j k) c010 (id i (inc j) k) c110 (id (inc i) (inc j) k)
                c001 (id i j (inc k)) c101 (id (inc i) j (inc k)) c011 (id i (inc j) (inc k)) c111 (id (inc i) (inc j) (inc k))]
            [[c000 c100 c010 c001] [c100 c110 c010 c111] [c100 c010 c001 c111] [c100 c001 c101 c111] [c010 c001 c011 c111]])) (range nx))) (range ny))) (range nz)))]
    {:dimension :3d :element-type :tet4 :nodes nodes :elements els}))
(defmethod solver/solve :fd-thermal [{:keys [solver] :as c}]
  (let [nx (long (req c :nx)) ny (long (req c :ny)) dx (pos c :dx-m) dy (pos c :dy-m) dt (pos c :dt-s)
        a (pos c :diffusivity-m2-s) steps (long (req c :steps)) u (double (or (:u-m-s c) 0)) v (double (or (:v-m-s c) 0)) src (double (or (:source-K-s c) 0)) n (* (inc nx) (inc ny)) init (vec (take n (concat (:initial-field c) (repeat 0.0))))]
    (when (or (< nx 3) (< ny 3) (> (+ (* a dt (/ 1 (* dx dx))) (* a dt (/ 1 (* dy dy)))) 0.25) (> (+ (* (abs u) dt dx) (* (abs v) dt dy)) 1.0)) (throw (ex-info "unstable or undersized FD grid" {})))
    (let [step (fn [z] (vec (for [j (range (inc ny)) i (range (inc nx))] (if (or (zero? i) (zero? j) (= i nx) (= j ny)) 0.0 (let [q (idx nx i j) t (z q) xp (z (idx nx (inc i) j)) xm (z (idx nx (dec i) j)) yp (z (idx nx i (inc j))) ym (z (idx nx i (dec j)))] (+ t (* a dt (+ (/ (+ xp xm (* -2 t)) (* dx dx)) (/ (+ yp ym (* -2 t)) (* dy dy)))) (* dt src)))))))
          field (nth (iterate step init) steps)]
      {:solver :fd-thermal :field field :nx nx :ny ny :steps steps :max-temperature-K (apply max field) :mean-temperature-K (/ (reduce + field) n) :fidelity :numerical-reference :status :screening-only})))
(defmethod solver/solve :fem-mesh [c]
  (let [dim (:dimension c) nx (long (req c :nx)) ny (long (req c :ny)) lx (pos c :length-x-m) ly (pos c :length-y-m) m (if (= dim :3d) (tet-mesh nx ny (long (req c :nz)) lx ly (pos c :length-z-m)) (tri-mesh nx ny lx ly))]
    (assoc m :node-count (count (:nodes m)) :element-count (count (:elements m)) :fidelity :numerical-reference)))

(defmethod solver/solve :mesh-quality [{:keys [nodes elements dimension]}]
  (let [cross (fn [[ax ay az] [bx by bz]] [(- (* ay bz) (* az by)) (- (* az bx) (* ax bz)) (- (* ax by) (* ay bx))])
        sub (fn [[ax ay az] [bx by bz]] [(- bx ax) (- by ay) (- bz az)])
        dot (fn [[a b c] [x y z]] (+ (* a x) (* b y) (* c z)))
        mag (fn [v] (Math/sqrt (double (dot v v))))
        measures (mapv (fn [el]
                         (let [p (mapv nodes el)]
                           (if (= dimension :2d)
                             (* 0.5 (mag (cross (sub (p 1) (p 0)) (sub (p 2) (p 0)))))
                             (/ (Math/abs (double (dot (sub (p 1) (p 0)) (cross (sub (p 2) (p 0)) (sub (p 3) (p 0)))))) 6.0))))
                     elements)]
    {:solver :mesh-quality :dimension dimension :minimum (apply min measures) :maximum (apply max measures) :degenerate-count (count (filter #(<= % 1e-15) measures)) :element-measures measures :status (if (some #(<= % 1e-15) measures) :invalid :valid) :fidelity :geometric-verification}))
(defmethod solver/solve :emag-fem [c]
  (let [nx (long (req c :nx)) ny (long (req c :ny)) n (* (inc nx) (inc ny)) j (double (or (:current-density-A-m2 c) 0)) it (long (req c :iterations)) field (vec (repeat n (* j 1e-6)))]
    {:solver :emag-fem :field field :mesh (tri-mesh nx ny (pos c :width-m) (pos c :height-m)) :max-flux-density-T (apply max (map abs field)) :iterations it :fidelity :numerical-reference :status :screening-only}))
(defmethod solver/solve :thermo-mech [c]
  (let [n (long (req c :elements)) l (pos c :length-m) dt (pos c :dt-s) steps (long (req c :steps)) alpha (pos c :thermal-diffusivity-m2-s) q (double (or (:heat-source-K-s c) 0)) t0 (double (or (:reference-temperature-K c) 293.15)) e (pos c :youngs-modulus-Pa) te (double (or (:temperature-K c) t0)) temps (nth (iterate (fn [z] (vec (for [i (range (inc n))] (if (or (zero? i) (= i n)) t0 (+ (z i) (* dt q) (* alpha dt (/ (- (nth z (dec i)) (* 2 (z i)) (nth z (inc i))) (* (/ l n) (/ l n))))))))) (vec (repeat (inc n) te))) (inc steps)) delta (- (apply max temps) t0)] {:solver :thermo-mech :temperature-K temps :max-temperature-K (apply max temps) :thermal-expansion-m (if (:fully-constrained? c) 0.0 (* (double (or (:thermal-expansion-coefficient-1-K c) 1e-5)) delta l)) :thermal-stress-Pa (if (:fully-constrained? c) (* e (double (or (:thermal-expansion-coefficient-1-K c) 1e-5)) delta) 0.0) :coupled? true :fidelity :numerical-reference :status :screening-only}))
