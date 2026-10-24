(ns kotoba.sm.vector-field
  "Four-vector fields: the restricted Lorentz group SO(3,1)+ acting on rank-1
  tensors (boosts, rotations), and a finite-difference four-gradient over field
  functions R^4 -> V. Fields are plain Clojure functions of a spacetime point
  `[t x y z]` -- there is no symbolic differentiation layer in this library;
  derivatives are either numeric (this namespace) or supplied analytically by
  the caller (e.g. an exact plane-wave solution in `kotoba.sm.spinor`)."
  (:require [kotoba.sm.tensor :as tensor]))

#?(:clj (defn- sqrt [x] (Math/sqrt x))
   :cljs (defn- sqrt [x] (.sqrt js/Math x)))
#?(:clj (defn- cos [x] (Math/cos x))
   :cljs (defn- cos [x] (.cos js/Math x)))
#?(:clj (defn- sin [x] (Math/sin x))
   :cljs (defn- sin [x] (.sin js/Math x)))
(defn- abs-num [x] (if (neg? x) (- x) x))

;; ---------------------------------------------------------------------------
;; four-vector constructors
;; ---------------------------------------------------------------------------

(defn four-vector [t x y z] [t x y z])

(defn three-momentum [v] (subvec v 1 4))

(defn energy [v] (nth v 0))

;; ---------------------------------------------------------------------------
;; Lorentz transformations (acting on upper-index four-vectors v'^mu = L^mu_nu v^nu)
;; ---------------------------------------------------------------------------

(defn boost
  "General Lorentz boost matrix for velocity vector `beta` = [bx by bz]
  (units where c=1, |beta| < 1). Reduces to the textbook single-axis boost
  when only one component is nonzero."
  [[bx by bz]]
  (let [beta2 (+ (* bx bx) (* by by) (* bz bz))]
    (if (zero? beta2)
      [[1 0 0 0] [0 1 0 0] [0 0 1 0] [0 0 0 1]]
      (let [gamma (/ 1.0 (sqrt (- 1.0 beta2)))
            b [bx by bz]
            row0 (into [gamma] (mapv #(* (- gamma) %) b))
            spatial (vec (for [i (range 3)]
                           (into [(* (- gamma) (nth b i))]
                                 (vec (for [j (range 3)]
                                        (+ (if (= i j) 1.0 0.0)
                                           (* (- gamma 1.0) (nth b i) (nth b j) (/ 1.0 beta2))))))))]
        (into [row0] spatial)))))

(defn boost-x [beta] (boost [beta 0 0]))
(defn boost-y [beta] (boost [0 beta 0]))
(defn boost-z [beta] (boost [0 0 beta]))

(defn rotation-z
  "Rotation by angle theta (radians) about the z axis, t and z unchanged."
  [theta]
  [[1 0 0 0]
   [0 (cos theta) (- (sin theta)) 0]
   [0 (sin theta) (cos theta) 0]
   [0 0 0 1]])

(defn rotation-y [theta]
  [[1 0 0 0]
   [0 (cos theta) 0 (sin theta)]
   [0 0 1 0]
   [0 (- (sin theta)) 0 (cos theta)]])

(defn rotation-x [theta]
  [[1 0 0 0]
   [0 1 0 0]
   [0 0 (cos theta) (- (sin theta))]
   [0 0 (sin theta) (cos theta)]])

(defn apply-transform
  "Apply a 4x4 Lorentz matrix to an upper-index four-vector."
  [lambda v]
  (tensor/mat-vec lambda v))

(defn lorentz?
  "Check that `lambda` preserves the Minkowski inner product: Lambda^T eta Lambda = eta."
  ([lambda] (lorentz? lambda 1e-9))
  ([lambda eps]
   (let [lhs (tensor/mat-mat (tensor/mat-transpose lambda)
                             (tensor/mat-mat tensor/metric lambda))]
     (every? true?
             (for [i (range 4) j (range 4)]
               (< (abs-num (- (nth (nth lhs i) j) (nth (nth tensor/metric i) j))) eps))))))

;; ---------------------------------------------------------------------------
;; finite-difference four-gradient / four-divergence / d'Alembertian
;; ---------------------------------------------------------------------------

(def ^:dynamic *h* 1e-5)

(defn- shift [x mu dx]
  (update x mu + dx))

(defn four-gradient
  "d/dx^mu f(x) for a scalar field f: R^4 -> real, at point x, mu = 0..3.
  Returns the lower-index gradient [df/dt df/dx df/dy df/dz] via central
  differences."
  [f x]
  (vec (for [mu (range 4)]
         (/ (- (f (shift x mu *h*)) (f (shift x mu (- *h*))))
            (* 2 *h*)))))

(defn four-gradient-vec
  "d V^nu / d x^mu for a vector field V: R^4 -> four-vector, at point x.
  Returns a rank-2 tensor indexed [mu][nu]."
  [f x]
  (vec (for [mu (range 4)]
         (tensor/v-scale (/ 1.0 (* 2 *h*))
                          (tensor/v- (f (shift x mu *h*)) (f (shift x mu (- *h*))))))))

(defn four-divergence
  "d_mu V^mu for a vector field V: R^4 -> four-vector, at point x."
  [f x]
  (reduce + (for [mu (range 4)]
              (/ (- (nth (f (shift x mu *h*)) mu) (nth (f (shift x mu (- *h*))) mu))
                 (* 2 *h*)))))

(defn dalembertian
  "The wave operator d^mu d_mu f = d^2f/dt^2 - Laplacian(f) (mostly-minus metric),
  for a scalar field f: R^4 -> real, at point x, via second-order central
  differences."
  [f x]
  (reduce +
          (for [mu (range 4)]
            (let [second-deriv (/ (+ (f (shift x mu *h*)) (- (* 2 (f x))) (f (shift x mu (- *h*))))
                                   (* *h* *h*))]
              (* (nth (nth tensor/metric mu) mu) second-deriv)))))
