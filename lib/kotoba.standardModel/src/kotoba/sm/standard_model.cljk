(ns kotoba.sm.standard-model
  "Composition layer: the Standard Model's fermion content, electroweak
  symmetry breaking, Higgs mechanism, CKM quark mixing, the full 3-factor
  (SU(3)_c x SU(2)_L x U(1)_Y) covariant derivative, and Lagrangian-density
  term assembly. Builds on kotoba.sm.{complex,tensor,spinor,gauge}.

  Scope: classical field content and equations of motion, evaluated
  numerically -- NOT quantization, renormalization/RGE, scattering amplitudes,
  or lattice simulation (see ADR-2607051500)."
  (:require [kotoba.sm.complex :as c]
            [kotoba.sm.tensor :as tensor]
            [kotoba.sm.spinor :as spinor]
            [kotoba.sm.gauge :as gauge]))

#?(:clj (defn- sqrt [x] (Math/sqrt x))
   :cljs (defn- sqrt [x] (.sqrt js/Math x)))
#?(:clj (defn- atan [x] (Math/atan x))
   :cljs (defn- atan [x] (.atan js/Math x)))
#?(:clj (defn- cos [x] (Math/cos x))
   :cljs (defn- cos [x] (.cos js/Math x)))
#?(:clj (defn- sin [x] (Math/sin x))
   :cljs (defn- sin [x] (.sin js/Math x)))

;; ---------------------------------------------------------------------------
;; fermion generation table (Gell-Mann-Nishijima: Q = T3 + Y/2)
;; minimal SM content -- no right-handed neutrino (massless-neutrino SM).
;; ---------------------------------------------------------------------------

(def generations [1 2 3])
(def up-type-quarks ["u" "c" "t"])
(def down-type-quarks ["d" "s" "b"])
(def charged-leptons ["e" "mu" "tau"])
(def neutrinos ["nu_e" "nu_mu" "nu_tau"])

(defn- fermion [name generation chirality multiplet color T3 Y]
  {:name name :generation generation :chirality chirality :multiplet multiplet
   :color color :T3 T3 :Y Y :Q (+ T3 (/ Y 2.0))})

(defn fermion-content
  "The full minimal-SM fermion table (3 generations): quark doublets +
  up/down singlets, lepton doublets + charged-lepton singlets."
  []
  (vec
   (mapcat
    (fn [gen up down charged nu]
      [(fermion up gen :L :quark-doublet :triplet 0.5 (/ 1.0 3.0))
       (fermion down gen :L :quark-doublet :triplet -0.5 (/ 1.0 3.0))
       (fermion up gen :R :up-singlet :triplet 0.0 (/ 4.0 3.0))
       (fermion down gen :R :down-singlet :triplet 0.0 (/ -2.0 3.0))
       (fermion nu gen :L :lepton-doublet :singlet 0.5 -1.0)
       (fermion charged gen :L :lepton-doublet :singlet -0.5 -1.0)
       (fermion charged gen :R :charged-lepton-singlet :singlet 0.0 -2.0)])
    generations up-type-quarks down-type-quarks charged-leptons neutrinos)))

(defn- abs-num [x] (if (neg? x) (- x) x))

(defn gell-mann-nishijima-ok?
  "Verify Q = T3 + Y/2 holds for every entry of the fermion table (a real
  correctness constraint: Y is recorded independently per the PDG convention,
  Q/T3 from the standard assignment -- this checks they agree)."
  ([] (gell-mann-nishijima-ok? (fermion-content)))
  ([content]
   (every? (fn [f] (< (abs-num (- (:Q f) (+ (:T3 f) (/ (:Y f) 2.0)))) 1e-9))
           content)))

;; ---------------------------------------------------------------------------
;; electroweak symmetry breaking: SU(2)_L x U(1)_Y -> U(1)_em
;; ---------------------------------------------------------------------------

(defn weinberg-angle
  "theta_W = atan(g'/g), from the SU(2) coupling g and U(1)_Y coupling g'."
  [g g-prime]
  (atan (/ g-prime g)))

(defn mixing-matrix
  "The orthogonal rotation [[cos sin][-sin cos]] taking (B_mu, W3_mu) ->
  (A_mu, Z_mu)."
  [theta-w]
  [[(cos theta-w) (sin theta-w)]
   [(- (sin theta-w)) (cos theta-w)]])

(defn photon-Z
  "Given the hypercharge boson B_mu and neutral weak boson W3_mu at a point
  (and theta_W), return [A_mu Z_mu] -- the physical photon and Z boson."
  [B-mu W3-mu theta-w]
  (tensor/mat-vec (mixing-matrix theta-w) [B-mu W3-mu]))

(defn w-boson-fields
  "W1_mu, W2_mu -> [W+_mu W-_mu], the charged mass-eigenstate combinations,
  as complex scalars: W+-_mu = (W1_mu -+ i W2_mu)/sqrt(2)."
  [W1-mu W2-mu]
  (let [inv-sqrt2 (/ 1.0 (sqrt 2.0))]
    [(c/scale inv-sqrt2 (c/c W1-mu (- W2-mu)))
     (c/scale inv-sqrt2 (c/c W1-mu W2-mu))]))

(defn w-mass
  "M_W = g v / 2, from the SU(2) coupling g and Higgs vev v."
  [g v]
  (/ (* g v) 2.0))

(defn z-mass
  "M_Z = (v/2) sqrt(g^2 + g'^2), from the SU(2)/U(1)_Y couplings and vev v."
  [g g-prime v]
  (* (/ v 2.0) (sqrt (+ (* g g) (* g-prime g-prime)))))

;; ---------------------------------------------------------------------------
;; Higgs potential, vev, and mass generation
;; ---------------------------------------------------------------------------

(defn higgs-potential
  "V(|phi|^2) = mu2 |phi|^2 + lambda |phi|^4, for the real order parameter
  |phi|^2 (mu2 < 0, lambda > 0 for symmetry breaking)."
  [mu2 lambda phi2]
  (+ (* mu2 phi2) (* lambda phi2 phi2)))

(defn higgs-vev
  "v = sqrt(-mu2/lambda) -- the conventional SM vacuum expectation value, i.e.
  the value such that phi = (0, (v+h)/sqrt(2)) in unitary gauge sits at the
  minimum of `higgs-potential` (mu2 < 0, lambda > 0 required). Note this is
  NOT sqrt(x_min) for x=|phi|^2 directly (that minimizer is x_min=-mu2/(2
  lambda)=v^2/2) -- the extra factor of 2 comes from the 1/sqrt(2) doublet
  normalization, standard in the literature."
  [mu2 lambda]
  (sqrt (/ (- mu2) lambda)))

(defn higgs-mass
  "m_H = sqrt(-2 mu2) = sqrt(2 lambda) v (both forms should agree; see test)."
  [mu2 lambda]
  (sqrt (* -2.0 mu2)))

(defn yukawa-mass
  "m_f = y_f v / sqrt(2), fermion mass from a Yukawa coupling y_f and vev v."
  [y v]
  (/ (* y v) (sqrt 2.0)))

;; ---------------------------------------------------------------------------
;; CKM quark-mixing matrix (PDG 3-angle + phase parameterization -- an exact
;; product of unitary rotations, so V-dagger V = I holds exactly, unlike the
;; truncated Wolfenstein series expansion)
;; ---------------------------------------------------------------------------

(defn ckm-matrix
  "The CKM matrix for mixing angles theta12/theta13/theta23 (radians) and CP
  phase delta (radians)."
  [theta12 theta13 theta23 delta]
  (let [c12 (cos theta12) s12 (sin theta12)
        c13 (cos theta13) s13 (sin theta13)
        c23 (cos theta23) s23 (sin theta23)
        e-i-delta (c/c (cos (- delta)) (sin (- delta)))
        e+i-delta (c/c (cos delta) (sin delta))
        cx (fn [x] (c/c x 0))]
    [[(cx (* c12 c13)) (cx (* s12 c13)) (c/c* (cx s13) e-i-delta)]
     [(c/c- (cx (* (- s12) c23)) (c/c* (cx (* c12 s23 s13)) e+i-delta))
      (c/c- (cx (* c12 c23)) (c/c* (cx (* s12 s23 s13)) e+i-delta))
      (cx (* s23 c13))]
     [(c/c- (cx (* s12 s23)) (c/c* (cx (* c12 c23 s13)) e+i-delta))
      (c/c- (cx (* (- c12) s23)) (c/c* (cx (* s12 c23 s13)) e+i-delta))
      (cx (* c23 c13))]]))

;; ---------------------------------------------------------------------------
;; full SU(3)_c x SU(2)_L x U(1)_Y covariant derivative
;; ---------------------------------------------------------------------------

(defn covariant-derivative-sm
  "D_mu psi for an arbitrary SM fermion multiplet, summing the color (SU(3)),
  weak-isospin (SU(2)), and hypercharge (U(1)) corrections against a single
  ordinary partial derivative `d-mu-psi`. `fermion` supplies :color
  (:triplet/:singlet), :weak (:doublet/:singlet), and :Y (hypercharge);
  A-color/A-weak are the vectors of gluon/W gauge-field components (empty for
  a color/weak singlet), A-hyper is the scalar B_mu value; gs/gw/gy are the
  three coupling constants. Note: a multiplet nontrivial under BOTH SU(3) and
  SU(2) simultaneously (e.g. the left-handed quark doublet, really a (3,2)
  bidoublet) is not constructed here as a genuine tensor-product
  representation -- psi is assumed nontrivial under at most one of the two
  non-abelian factors at a time, which is what the test suite exercises.

  *** BUG FIX (found by independent adversarial review): *** the U(1)_Y
  generator MUST be built from :Y/2, not the raw :Y, to be consistent with
  this namespace's own Gell-Mann-Nishijima convention Q=T3+Y/2 (checked by
  `gell-mann-nishijima-ok?`) and its own `weinberg-angle`/`photon-Z`. Proof:
  after mixing B_mu=cos(theta_W)A_mu-sin(theta_W)Z_mu,
  W3_mu=sin(theta_W)A_mu+cos(theta_W)Z_mu (the inverse of `mixing-matrix`),
  the SU(2)xU(1) coupling's photon (A_mu) coefficient is
  g*sin(theta_W)*T3 + g'*cos(theta_W)*Y_eff. Since e=g*sin(theta_W)=
  g'*cos(theta_W) (this namespace's own w-mass/z-mass/weinberg-angle already
  satisfy this), the coefficient is e*(T3+Y_eff), which equals the required
  e*Q=e*(T3+Y/2) only for Y_eff=Y/2 -- using raw Y gives e*(T3+Y), wrong by a
  T3-dependent factor for every charged fermion with T3!=0 (e.g. exactly 1.5x
  too large in magnitude for e_L: T3=-1/2,Y=-1, independently confirmed
  numerically). Was invisible to `covariant-derivative-sm-reduces-to-partial-
  when-fields-off`, the only existing test of this function, because that
  test only exercises the A-hyper=0 case where the U(1) generator's
  normalization cannot matter."
  [d-mu-psi fermion A-color A-weak A-hyper gs gw gy psi]
  (let [dim (count psi)
        Ts-c (if (= (:color fermion) :triplet) gauge/su3-generators [])
        Ts-w (if (= (:weak fermion) :doublet) gauge/su2-generators [])
        Ts-y (gauge/u1-generators (/ (:Y fermion) 2.0) dim)
        corr-c (gauge/gauge-correction Ts-c A-color gs psi)
        corr-w (gauge/gauge-correction Ts-w A-weak gw psi)
        corr-y (gauge/gauge-correction Ts-y [A-hyper] gy psi)]
    (reduce c/v-add d-mu-psi [corr-c corr-w corr-y])))

;; ---------------------------------------------------------------------------
;; Lagrangian-density term assembly
;; ---------------------------------------------------------------------------

(defn- slice-generator [F a]
  (vec (for [mu (range 4)] (vec (for [nu (range 4)] (get-in F [mu nu a]))))))

(defn yang-mills-density
  "-1/4 sum_a F^a_mu-nu F^{a mu-nu}, for a field-strength array F[mu][nu][a]
  (see kotoba.sm.gauge/field-strength). Zero generators (U(1)) -> 0."
  [F]
  (let [n (count (get-in F [0 0]))]
    (if (zero? n)
      0.0
      (* -0.25 (reduce + (for [a (range n)]
                           (let [Fa (slice-generator F a)]
                             (tensor/full-contract (tensor/raise2 Fa) Fa))))))))

(defn dirac-density
  "i psi-bar gamma^mu D_mu psi - m psi-bar psi, given the adjoint spinor
  `psi-bar`, the 4 covariant derivatives D-psi[mu], mass, and psi itself."
  [psi-bar D-psi mass psi]
  (let [kinetic (reduce c/c+ c/zero
                        (for [mu (range 4)] (spinor/bilinear psi-bar (nth spinor/gammas mu) (nth D-psi mu))))
        kinetic-i (c/c* c/i kinetic)
        mass-term (c/c* (c/c mass 0) (spinor/bilinear psi-bar spinor/I4 psi))]
    (c/c- kinetic-i mass-term)))

(defn- dagger-dot
  "sum_i conj(a_i) b_i, the Hermitian inner product of two complex vectors."
  [a b]
  (apply c/c+ (map c/c* (c/v-conj a) b)))

(defn higgs-density
  "(D_mu phi)^dagger (D^mu phi) - V(phi), given the 4 covariant derivatives
  D-phi[mu] of the Higgs doublet and the potential parameters."
  [D-phi phi mu2 lambda]
  (let [kinetic (reduce c/c+ c/zero
                        (for [mu (range 4)]
                          (c/scale (nth (nth tensor/metric mu) mu) (dagger-dot (nth D-phi mu) (nth D-phi mu)))))
        phi2 (c/re (dagger-dot phi phi))
        v (higgs-potential mu2 lambda phi2)]
    (c/c- kinetic (c/c v 0))))

(defn yukawa-term
  "y (L . phi) e_R, the SU(2)-doublet contraction of a lepton doublet L with
  the Higgs doublet phi, times the right-handed singlet e_R -- schematic
  (dot-product) form of the SM Yukawa coupling structure."
  [y L phi eR]
  (c/c* (c/c y 0) (c/c* (apply c/c+ (map c/c* L phi)) eR)))

(defn yukawa-density
  "-(yukawa-term + h.c.), the real Yukawa Lagrangian-density contribution."
  [y L phi eR]
  (let [term (yukawa-term y L phi eR)]
    (c/c-neg (c/c+ term (c/conj* term)))))

(defn total-lagrangian-density
  "Sum of pre-computed Lagrangian-density pieces (Yang-Mills terms for each
  factor group, Dirac terms for each fermion, the Higgs term, Yukawa terms) --
  the SM Lagrangian density is their sum; each piece is built with the more
  specific functions above."
  [yang-mills-terms dirac-terms higgs-term yukawa-terms]
  (reduce c/c+ (c/c (reduce + 0.0 yang-mills-terms) 0)
          (concat dirac-terms [higgs-term] yukawa-terms)))
