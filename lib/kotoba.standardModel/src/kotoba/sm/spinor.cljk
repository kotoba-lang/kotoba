(ns kotoba.sm.spinor
  "Dirac spinor fields. Pauli matrices, Dirac gamma matrices in the Dirac
  (standard) representation built from them, chirality projectors, bilinear
  covariants, the free-particle plane-wave solution, and a Dirac-equation
  residual check via finite differences (kotoba.sm.tensor's mostly-minus
  metric convention throughout)."
  (:require [kotoba.sm.complex :as c]
            [kotoba.sm.tensor :as tensor]))

#?(:clj (defn- sqrt [x] (Math/sqrt x))
   :cljs (defn- sqrt [x] (.sqrt js/Math x)))
#?(:clj (defn- cos [x] (Math/cos x))
   :cljs (defn- cos [x] (.cos js/Math x)))
#?(:clj (defn- sin [x] (Math/sin x))
   :cljs (defn- sin [x] (.sin js/Math x)))

;; ---------------------------------------------------------------------------
;; Pauli matrices
;; ---------------------------------------------------------------------------

(def sigma1 [[c/zero c/one] [c/one c/zero]])
(def sigma2 [[c/zero (c/c 0 -1)] [(c/c 0 1) c/zero]])
(def sigma3 [[c/one c/zero] [c/zero (c/c -1 0)]])
(def sigmas [sigma1 sigma2 sigma3])
(def I2 (c/m-identity 2))
(def Z2 (c/m-zero 2 2))

;; ---------------------------------------------------------------------------
;; Dirac gamma matrices (Dirac / standard representation)
;; ---------------------------------------------------------------------------

(defn- block2
  "Assemble a 4x4 complex matrix from four 2x2 complex blocks (top-left,
  top-right, bottom-left, bottom-right)."
  [tl tr bl br]
  (vec (concat
        (mapv (fn [l r] (vec (concat l r))) tl tr)
        (mapv (fn [l r] (vec (concat l r))) bl br))))

(def gamma0 (block2 I2 Z2 Z2 (c/m-rscale -1 I2)))
(def gamma1 (block2 Z2 sigma1 (c/m-rscale -1 sigma1) Z2))
(def gamma2 (block2 Z2 sigma2 (c/m-rscale -1 sigma2) Z2))
(def gamma3 (block2 Z2 sigma3 (c/m-rscale -1 sigma3) Z2))
(def gammas [gamma0 gamma1 gamma2 gamma3])

(def gamma5
  "gamma^5 = i gamma^0 gamma^1 gamma^2 gamma^3, which in the Dirac
  representation reduces to the off-diagonal block form [[0 I][I 0]]."
  (block2 Z2 I2 I2 Z2))

(def I4 (c/m-identity 4))

(defn slash
  "Feynman slash of a real four-vector v^mu (upper index): v-slash = gamma^mu v_mu,
  i.e. gamma^mu contracted against the LOWERED components of v."
  [v]
  (let [v-lower (tensor/lower v)]
    (reduce c/m-add
            (c/m-zero 4 4)
            (for [mu (range 4)] (c/m-rscale (nth v-lower mu) (nth gammas mu))))))

(defn chirality-projector-L [] (c/m-rscale 0.5 (c/m-sub I4 gamma5)))
(defn chirality-projector-R [] (c/m-rscale 0.5 (c/m-add I4 gamma5)))

(defn sigma-munu
  "sigma^mu-nu = (i/2) [gamma^mu, gamma^nu], the antisymmetric tensor bilinear generator."
  [mu nu]
  (c/m-scale (c/c 0 0.5) (c/m-commutator (nth gammas mu) (nth gammas nu))))

;; ---------------------------------------------------------------------------
;; spinors and bilinear covariants
;; ---------------------------------------------------------------------------

(defn adjoint
  "Dirac adjoint psi-bar = psi^dagger gamma^0, returned as a row (plain vector
  of complex components, ready for `bilinear`)."
  [psi]
  (c/m-vec (c/transpose gamma0) (c/v-conj psi)))

(defn bilinear
  "psi1-bar . Gamma . psi2 -> a complex scalar, given psi1-bar already an
  adjoint spinor (see `adjoint`)."
  [psi1-bar gamma-matrix psi2]
  (let [g-psi2 (c/m-vec gamma-matrix psi2)]
    (apply c/c+ (map c/c* psi1-bar g-psi2))))

(defn scalar-bilinear [psi] (bilinear (adjoint psi) I4 psi))
(defn pseudoscalar-bilinear [psi] (bilinear (adjoint psi) gamma5 psi))
(defn vector-bilinear
  "[psi-bar gamma^0 psi, psi-bar gamma^1 psi, psi-bar gamma^2 psi, psi-bar gamma^3 psi]."
  [psi]
  (let [psi-bar (adjoint psi)]
    (mapv #(bilinear psi-bar % psi) gammas)))

;; ---------------------------------------------------------------------------
;; free-particle plane-wave solution (Dirac representation, Peskin & Schroeder 3.47)
;; u^s(p) = sqrt(E+m) [xi^s ; (sigma.p)/(E+m) xi^s], E = sqrt(|p|^2 + m^2)
;; ---------------------------------------------------------------------------

(def xi-up [c/one c/zero])
(def xi-down [c/zero c/one])

(defn energy-of [p m] (sqrt (+ (* (nth p 0) (nth p 0)) (* (nth p 1) (nth p 1)) (* (nth p 2) (nth p 2)) (* m m))))

(defn sigma-dot [p]
  (reduce c/m-add (c/m-zero 2 2) (map c/m-rscale p sigmas)))

(defn u-spinor
  "Free-particle plane-wave spinor u^s(p) for 3-momentum p=[px py pz], mass m,
  spin label s in #{:up :down}."
  [s p m]
  (let [e (energy-of p m)
        xi (case s :up xi-up :down xi-down)
        lower (c/m-vec (c/m-rscale (/ 1.0 (+ e m)) (sigma-dot p)) xi)
        norm (sqrt (+ e m))]
    (mapv #(c/scale norm %) (vec (concat xi lower)))))

(defn plane-wave
  "psi(x) = u^s(p) exp(-i p.x), a function R^4 -> spinor (4 complex components).
  An exact solution of the free Dirac equation (i gamma^mu d_mu - m) psi = 0."
  [s p m]
  (let [e (energy-of p m)
        p4 [e (nth p 0) (nth p 1) (nth p 2)]
        u (u-spinor s p m)]
    (fn [x]
      (let [phase (tensor/dot p4 x)
            phase-factor [(cos phase) (- (sin phase))]]
        (c/v-scale phase-factor u)))))

;; ---------------------------------------------------------------------------
;; Dirac equation residual (finite-difference check)
;; ---------------------------------------------------------------------------

(def ^:dynamic *h* 1e-6)

(defn- shift [x mu dx] (update x mu + dx))

(defn spinor-four-gradient
  "d psi / d x^mu for a spinor field psi: R^4 -> spinor, at point x.
  Returns a vector of 4 spinors (one per mu), central finite differences."
  [psi-field x]
  (vec (for [mu (range 4)]
         (c/v-scale (c/c (/ 1.0 (* 2 *h*)))
                    (c/v-sub (psi-field (shift x mu *h*)) (psi-field (shift x mu (- *h*))))))))

(defn dirac-residual
  "(i gamma^mu d_mu - m) psi(x), evaluated numerically. Should be ~0 (within
  finite-difference error) for any exact solution such as `plane-wave`."
  [psi-field m x]
  (let [dpsi (spinor-four-gradient psi-field x)
        terms (for [mu (range 4)] (c/m-vec (nth gammas mu) (nth dpsi mu)))
        slash-partial (reduce c/v-add (vec (repeat 4 c/zero)) terms)
        i-slash-partial (c/v-scale c/i slash-partial)
        m-psi (c/v-scale (c/c m 0) (psi-field x))]
    (c/v-sub i-slash-partial m-psi)))
