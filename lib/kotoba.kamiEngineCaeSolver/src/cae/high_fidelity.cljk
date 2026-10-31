(ns cae.high-fidelity
  "Portable high-fidelity reference kernels and parallelization contracts."
  (:require [cae.solver :as solver]))

(def ^:private gamma 1.4)
(defn- pressure [rho mom energy] (* (- gamma 1.0) (- energy (/ (* mom mom) (* 2.0 rho)))))
(defn- flux [u]
  (let [[rho mom energy] u p (pressure rho mom energy) vel (/ mom rho)]
    [mom (+ (* mom vel) p) (* (+ energy p) vel)]))
(defn- rusanov-flux [l r]
  (let [[rl ml el] l [rr mr er] r pl (pressure rl ml el) pr (pressure rr mr er)
        vl (/ ml rl) vr (/ mr rr) al (Math/sqrt (* gamma (/ pl rl))) ar (Math/sqrt (* gamma (/ pr rr))) s (max (+ (Math/abs vl) al) (+ (Math/abs vr) ar)) fl (flux l) fr (flux r)]
    (mapv #(* 0.5 %) (mapv - (mapv + fl fr) (mapv #(* s %) (mapv - r l))))))

(defn- totals [state dx]
  (mapv #(* dx %) (reduce (fn [a u] (mapv + a u)) [0.0 0.0 0.0] state)))

(defn- update-residual [before after]
  (let [delta (mapcat (fn [a b] (map - b a)) before after)
        scale (max 1.0e-30 (Math/sqrt (reduce + (map #(* % %) (mapcat identity before)))))]
    (/ (Math/sqrt (reduce + (map #(* % %) delta))) scale)))

(defmethod solver/solve :fvm-compressible [{:keys [cells dx-m dt-s steps initial-state initial-condition]}]
  (let [n (long cells) dx (double dx-m) dt (double dt-s)
        sod (when (= initial-condition :sod-shock-tube)
              (let [mid (quot n 2) left [1.0 0.0 (/ 1.0 (- gamma 1.0))] right [0.125 0.0 (/ 0.1 (- gamma 1.0))]]
                (vec (concat (repeat mid left) (repeat (- n mid) right)))))
        init (vec (or initial-state sod (repeat n [1.0 0.0 250000.0])))
        advance (fn [u]
                  (let [interfaces (vec (for [i (range (inc n))]
                                          (rusanov-flux (u (max 0 (dec i))) (u (min (dec n) i)))))
                        next (vec (for [i (range n)]
                                    (mapv - (u i) (mapv #(* (/ dt dx) %) (mapv - (interfaces (inc i)) (interfaces i))))))]
                    {:state next :left-flux (first interfaces) :right-flux (peek interfaces)}))
        initial-totals (totals init dx)
        run (loop [i 0 state init residuals [] boundary [0.0 0.0 0.0]]
              (if (= i (long steps)) {:state state :residuals residuals :boundary boundary}
                  (let [step-result (advance state) next-state (:state step-result)
                        left-flux (:left-flux step-result) right-flux (:right-flux step-result)]
                    (recur (inc i) next-state (conj residuals (update-residual state next-state))
                           (mapv + boundary (mapv #(* dt %) (mapv - right-flux left-flux)))))))
        state (:state run) final-totals (totals state dx)
        defect (mapv + (mapv - final-totals initial-totals) (:boundary run))]
    {:solver :fvm-compressible :state state :density-profile (mapv first state)
     :pressure-profile (mapv (fn [[r m e]] (pressure r m e)) state) :cells n
     :flux :rusanov :equation :euler-1d :gamma gamma :initial-condition initial-condition
     :diagnostics {:initial-conserved initial-totals :final-conserved final-totals
                   :boundary-outflow (:boundary run) :conservation-defect defect
                   :time-step-update-norm-history (:residuals run)}
     :fidelity :finite-volume-reference :status :screening-only}))

(defmethod solver/solve :turbulence-model [{:keys [velocity-m-s length-scale-m kinematic-viscosity-m2-s]}]
  (let [u (double velocity-m-s) l (double length-scale-m) nu (double kinematic-viscosity-m2-s) re (/ (* u l) nu) k (* 0.5 u u) eps (/ (Math/pow 0.09 0.75) l (Math/pow (max k 1e-12) 0.25))]
    {:solver :turbulence-model :reynolds-number re :turbulent-kinetic-energy-m2-s2 k :dissipation-m2-s3 eps :model :mixing-length :fidelity :closure-reference :status :screening-only}))

(defmethod solver/solve :rans-k-epsilon [{:keys [cells dx-m dt-s steps velocity-m-s density-kg-m3 viscosity-pa-s]}]
  (let [n (long cells) dx (double dx-m) dt (double dt-s) u (double velocity-m-s) rho (double density-kg-m3) nu (/ (double viscosity-pa-s) rho)
        c1 1.44 c2 1.92 sigma-k 1.0 sigma-e 1.3 init (vec (repeat n [1e-6 1e-6]))
        step (fn [state]
               (vec (for [i (range n)]
                      (let [[k e] (state i)
                            km (first (state (max 0 (dec i))))
                            kp (first (state (min (dec n) (inc i))))
                            em (second (state (max 0 (dec i))))
                            ep (second (state (min (dec n) (inc i))))
                            prod (* 0.09 (/ k (max e 1e-12)) u u (/ 1.0 (* dx dx)))
                            dk (* (/ nu sigma-k) (/ (+ km (* -2 k) kp) (* dx dx)))
                            de (* (/ nu sigma-e) (/ (+ em (* -2 e) ep) (* dx dx)))]
                        [(max 1e-12 (+ k (* dt (- prod e)) (* dt dk)))
                         (max 1e-12 (+ e (* dt (- (* c1 prod (/ e (max k 1e-12))) (* c2 (/ (* e e) (max k 1e-12))))) (* dt de)))]))))
        state (nth (iterate step init) (long steps))]
    {:solver :rans-k-epsilon :k-epsilon state :cells n :constants {:c1-epsilon c1 :c2-epsilon c2 :sigma-k sigma-k :sigma-epsilon sigma-e} :fidelity :rans-reference :status :screening-only}))

(defmethod solver/solve :combustion-reaction [{:keys [temperature-K fuel-mass-fraction dt-s steps pre-exponential-1-s activation-energy-J-mol heat-release-J-kg]}]
  (let [r 8.314462618 t (double temperature-K) y (double fuel-mass-fraction) dt (double dt-s) n (long steps) a (double pre-exponential-1-s) ea (double activation-energy-J-mol) q (double heat-release-J-kg)
        step (fn [[temp fuel]] (let [rate (* a fuel (Math/exp (- (/ ea (* r temp))))) consumed (min fuel (* dt rate))] [(+ temp (* q consumed)) (- fuel consumed)]))
        [temp fuel] (nth (iterate step [t y]) n)]
    {:solver :combustion-reaction :temperature-K temp :fuel-mass-fraction fuel :reaction-rate-1-s (* a fuel (Math/exp (- (/ ea (* r temp))))) :steps n :model :arrhenius-single-step :fidelity :reaction-reference :status :screening-only}))

(defmethod solver/solve :boundary-layer [{:keys [velocity-m-s density-kg-m3 viscosity-pa-s distance-m]}]
  (let [u (double velocity-m-s) rho (double density-kg-m3) mu (double viscosity-pa-s) x (double distance-m) re (/ (* rho u x) mu) cf (if (< re 5e5) (/ 0.664 (Math/sqrt re)) (/ 0.0592 (Math/pow re 0.2))) delta (* 5.0 x (Math/sqrt (/ mu (* rho u x))))]
    {:solver :boundary-layer :reynolds-number re :skin-friction-coefficient cf :boundary-layer-thickness-m delta :regime (if (< re 5e5) :laminar :turbulent) :fidelity :correlation-reference :status :screening-only}))

(defmethod solver/solve :adaptive-mesh [{:keys [coordinates field tolerance max-level]}]
  (let [tol (double (or tolerance 1e-3)) max-level (long (or max-level 1)) pairs (map vector coordinates (rest coordinates) field (rest field))
        marked (vec (keep-indexed (fn [i [[x0 x1] f0 f1]] (when (> (Math/abs (- f1 f0)) tol) i)) pairs))
        refined (vec (mapcat (fn [i] (let [x0 (nth coordinates i) x1 (nth coordinates (inc i)) xm (* 0.5 (+ x0 x1))] [x0 xm])) marked))]
    {:solver :adaptive-mesh :coordinates (if (pos? max-level) (vec (sort (distinct (concat coordinates refined)))) (vec coordinates)) :marked-elements marked :error-indicator :gradient :tolerance tol :fidelity :reference-adaptation :status :screening-only}))

(defmethod solver/solve :mpi-domain [{:keys [cells ranks rank ghost-width]}]
  (let [n (long cells) p (long ranks) r (long (or rank 0)) g (long (or ghost-width 1)) base (quot n p) rem (mod n p) start (+ (* r base) (min r rem)) count (+ base (if (< r rem) 1 0)) owned (vec (range start (+ start count))) ghosts (vec (concat (range (max 0 (- start g)) start) (range (+ start count) (min n (+ start count g)))))]
    {:solver :mpi-domain :rank r :ranks p :owned-indices owned :ghost-indices ghosts :neighbors (vec (concat (when (pos? r) [(dec r)]) (when (< r (dec p)) [(inc r)]))) :communication :halo-exchange :fidelity :parallel-contract :status :screening-only}))

(defmethod solver/solve :mpi-halo-exchange [{:keys [partitions]}]
  (let [partitions (vec partitions)
        synced (mapv (fn [i p]
                       (let [left (when (pos? i) (last (:owned (partitions (dec i)))))
                             right (when (< i (dec (count partitions))) (first (:owned (partitions (inc i)))))]
                         (assoc p :ghost-values (vec (remove nil? [left right])) :synchronized? true)))
                     (range (count partitions)) partitions)]
    {:solver :mpi-halo-exchange :partitions synced :messages (* 2 (max 0 (dec (count partitions)))) :communication :deterministic-halo :fidelity :parallel-reference :status :screening-only}))

(defmethod solver/solve :mpi-load-balance [{:keys [weights ranks]}]
  (let [weights (vec (map double weights)) p (long ranks) total (reduce + weights) target (/ total p)
        assignment (loop [i 0 r 0 acc [] load 0.0]
                     (if (= i (count weights)) acc
                       (let [w (weights i) next-load (+ load w) move? (and (< r (dec p)) (> next-load target) (pos? load))]
                         (recur (inc i) (if move? (inc r) r) (conj acc (if move? (inc r) r)) (if move? w next-load)))))]
    {:solver :mpi-load-balance :assignment assignment :rank-loads (mapv (fn [r] (reduce + (map (fn [[i a]] (if (= r a) (weights i) 0.0)) (map-indexed vector assignment)))) (range p)) :target-load target :algorithm :greedy-contiguous :fidelity :parallel-reference :status :screening-only}))

(defmethod solver/solve :fem-elastoplastic [{:keys [strain youngs-modulus-Pa yield-stress-Pa hardening-Pa]}]
  (let [e (double youngs-modulus-Pa) sy (double yield-stress-Pa) h (double (or hardening-Pa 0.0)) eps (double strain) trial (* e eps) plastic? (> (Math/abs trial) sy) sign (if (neg? trial) -1.0 1.0) plastic-strain (if plastic? (* sign (/ (- (Math/abs trial) sy) (+ e h))) 0.0) stress (if plastic? (* sign (+ sy (* h (Math/abs plastic-strain)))) trial)]
    {:solver :fem-elastoplastic :stress-Pa stress :plastic-strain plastic-strain :yielded? plastic? :tangent-modulus-Pa (if plastic? (/ (* e h) (+ e h 1e-30)) e) :algorithm :return-mapping :fidelity :nonlinear-reference :status :screening-only}))

(defmethod solver/solve :finite-strain-elastic [{:keys [stretch youngs-modulus-Pa poisson-ratio]}]
  (let [lambda (double stretch) e (double youngs-modulus-Pa) nu (double poisson-ratio) mu (/ e (* 2.0 (+ 1.0 nu))) kappa (/ e (* 3.0 (- 1.0 (* 2.0 nu)))) j lambda ;; uniaxial surrogate deformation gradient
        sigma (* (/ 1.0 j) (+ (* mu (- (* lambda lambda) 1.0)) (* kappa (Math/log j))))]
    {:solver :finite-strain-elastic :stretch lambda :cauchy-stress-Pa sigma :jacobian j :shear-modulus-Pa mu :bulk-modulus-Pa kappa :model :compressible-neo-hookean-1d :fidelity :finite-strain-reference :status :screening-only}))

(defmethod solver/solve :friction-contact [{:keys [normal-force-N tangential-force-N friction-coefficient penalty-stiffness-N-m]}]
  (let [n (double normal-force-N) t (double tangential-force-N) mu (double friction-coefficient) k (double penalty-stiffness-N-m) limit (* mu (Math/abs n)) slip? (> (Math/abs t) limit) traction (if slip? (* limit (if (neg? t) -1.0 1.0)) t)]
    {:solver :friction-contact :normal-force-N n :tangential-traction-N traction :friction-limit-N limit :sliding? slip? :penetration-m (/ (Math/abs n) k) :fidelity :contact-reference :status :screening-only}))

(defmethod solver/solve :friction-contact-3d [{:keys [normal-vector-N tangential-vector-N friction-coefficient penalty-stiffness-N-m]}]
  (let [[nx ny nz] (mapv double normal-vector-N) [tx ty tz] (mapv double tangential-vector-N) mu (double friction-coefficient) k (double penalty-stiffness-N-m)
        nmag (Math/sqrt (+ (* nx nx) (* ny ny) (* nz nz))) tmag (Math/sqrt (+ (* tx tx) (* ty ty) (* tz tz))) limit (* mu nmag) sliding? (> tmag limit) scale (if (and sliding? (pos? tmag)) (/ limit tmag) 1.0) traction [(* tx scale) (* ty scale) (* tz scale)]
        direction (if (pos? tmag) [(/ tx tmag) (/ ty tmag) (/ tz tmag)] [0.0 0.0 0.0])]
    {:solver :friction-contact-3d :normal-force-N nmag :tangential-force-N tmag :friction-limit-N limit :tangential-traction-vector-N traction :sliding? sliding? :sliding-direction direction :penetration-m (/ nmag k) :fidelity :contact-reference :status :screening-only}))

(defmethod solver/solve :fracture-criterion [{:keys [stress-Pa fracture-toughness-Pa-m stress-intensity-factor-Pa-sqrt-m]}]
  (let [s (double stress-Pa) k (double stress-intensity-factor-Pa-sqrt-m) kc (double fracture-toughness-Pa-m) ratio (/ k kc)]
    {:solver :fracture-criterion :stress-Pa s :stress-intensity-factor-Pa-sqrt-m k :utilization ratio :fractured? (>= ratio 1.0) :criterion :linear-elastic-fracture :fidelity :fracture-reference :status :screening-only}))

(defmethod solver/solve :benchmark-comparison [{:keys [computed expected tolerance metric]}]
  (let [c (double computed) e (double expected) tol (double tolerance) err (Math/abs (- c e)) rel (/ err (max (Math/abs e) 1e-30))]
    {:solver :benchmark-comparison :metric metric :computed c :expected e :absolute-error err :relative-error rel :passed? (<= err tol) :tolerance tol :status (if (<= err tol) :verified :failed) :fidelity :verification}))
