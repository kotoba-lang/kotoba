(ns kotoba.sm.gauge
  "Generic Lie-algebra layer: generator sets for U(1)/SU(2)/SU(3) (compact),
  and -- via `kotoba.sm.gtg` -- the noncompact so(1,3) rotation-gauge sector,
  structure constants derived generically (not hard-coded) from ANY generator
  set whose own trace-Gram matrix K[A][B] = Tr(T_A T_B) is diagonal (see
  `structure-constants` below for the exact formula and scope), the gauge
  covariant derivative, and the non-abelian Yang-Mills field-strength tensor.

  Historically `structure-constants` hard-coded the compact-group convention
  Tr(T^aT^b) = 1/2 delta^ab (Pauli/2 for SU(2), Gell-Mann/2 for SU(3)) into
  its formula, f^abc = -2i Tr([T^a,T^b]T^c). That formula is only correct
  under that specific normalization -- it silently gives WRONG values (both
  wrong magnitude and, for indefinite-signature generator sets, wrong sign)
  for any generator set whose Gram matrix isn't a uniform +1/2 on the
  diagonal, e.g. so(1,3)'s noncompact bivector generators (`kotoba.sm.gtg`),
  whose Gram matrix is diagonal but +1 (rotation-type) or -1 (boost-type).
  `structure-constants` now computes the Gram matrix from the generators
  themselves and uses it in the formula, so it is correct for both cases (and
  numerically IDENTICAL to the old hard-coded formula in the compact-group
  case -- see gauge_test.cljc's `structure-constants-matches-legacy-*`
  regression tests)."
  (:require [kotoba.sm.complex :as c]
            [kotoba.sm.spinor :as spinor]))

;; ---------------------------------------------------------------------------
;; structure constants — generic: f^{ABD} = -i Tr([T_A,T_B]T_D) / K[D][D],
;; where K[A][B] = Tr(T_A T_B) is the generator set's OWN trace-Gram matrix
;; (not assumed to be 1/2 delta^AB).
;;
;; Derivation: [T_A,T_B] = i f^{ABC} T_C (sum over C); trace both sides
;; against T_D:
;;   Tr([T_A,T_B]T_D) = i f^{ABC} Tr(T_C T_D) = i f^{ABC} K[C][D]   (sum C)
;; If (and only if) K is DIAGONAL, K[C][D] = K[D][D] delta_{CD}, so the sum
;; over C collapses to the single C=D term:
;;   Tr([T_A,T_B]T_D) = i f^{ABD} K[D][D]  =>  f^{ABD} = -i Tr([T_A,T_B]T_D) / K[D][D]
;;
;; SCOPE: only a diagonal K is handled (checked below; throws otherwise). A
;; non-diagonal K would need the full f^{ABC} = -i Tr([T_A,T_B]T_E) (K^-1)[E][C]
;; contracted against a general matrix inverse, which is NOT implemented here
;; -- deliberately deferred, since every generator set actually used in this
;; codebase (U(1); SU(2) Pauli/2; SU(3) Gell-Mann/2; so(1,3)'s 6 bivector
;; generators, `kotoba.sm.gtg`) has a diagonal K, so this is not a practical
;; limitation today. Left as a documented future-work boundary, not silently
;; assumed away.
;;
;; The historical special case Tr(T^aT^b) = 1/2 delta^ab (Pauli/2, Gell-Mann/2)
;; has K[D][D] = 1/2 uniformly, for which -i/K[D][D] = -i/(1/2) = -2i, so this
;; reduces EXACTLY to the old hard-coded f^abc = -2i Tr([T^a,T^b]T^c) formula
;; -- gauge_test.cljc's `structure-constants-matches-legacy-*` tests prove
;; this bit-for-bit (within floating tolerance) against an independent
;; re-implementation of that old formula, on top of the pre-existing textbook
;; -value regression tests (`su2-structure-constants`/`su3-structure-constants`).
;; ---------------------------------------------------------------------------

(defn generator-gram
  "K[A][B] = Tr(T_A T_B) for a generator set, as raw complex scalars.
  `structure-constants` below uses only the real part (`diagonal-gram-real`);
  callers that want to double-check the imaginary part is numerically ~0 --
  which it always is, for every generator set actually used in this
  codebase -- can inspect these raw complex values directly (gauge_test.cljc
  and kotoba.sm.gtg-test both do exactly that)."
  [generators]
  (vec (for [A generators]
         (vec (for [B generators]
                (c/m-trace (c/m-mul A B)))))))

(defn diagonal-gram-real
  "Real part of `generator-gram`, AFTER checking it is actually diagonal
  (off-diagonal entries ~0, within `eps`) and has no ~0 diagonal entry (a
  degenerate/null direction under the trace pairing, which would make the
  f^{ABD} formula divide by ~0). Throws `ex-info` otherwise -- `structure-
  constants` only implements the diagonal, non-degenerate case (see the
  namespace-level SCOPE note above)."
  [generators eps]
  (let [n (count generators)
        K (generator-gram generators)
        Kre (mapv (fn [row] (mapv c/re row)) K)]
    (doseq [A (range n) B (range n) :when (not= A B)]
      (let [v (get-in Kre [A B])]
        (when (> (Math/abs (double v)) eps)
          (throw (ex-info
                  (str "kotoba.sm.gauge/structure-constants: generator trace-Gram "
                       "matrix K[A][B]=Tr(T_A T_B) is not diagonal (K[" A "][" B "] = "
                       v "); this generalization only supports diagonal Gram "
                       "matrices (orthogonal generator bases) -- non-orthogonal bases "
                       "are out of scope, see the kotoba.sm.gauge namespace docstring.")
                  {:kotoba.sm.gauge/reason :non-diagonal-gram :A A :B B :value v :K Kre})))))
    (doseq [D (range n)]
      (let [v (get-in Kre [D D])]
        (when (<= (Math/abs (double v)) eps)
          (throw (ex-info
                  (str "kotoba.sm.gauge/structure-constants: generator trace-Gram "
                       "matrix K[A][B]=Tr(T_A T_B) has a ~0 diagonal entry (K[" D "][" D "] = "
                       v "), a degenerate/null generator under the trace pairing -- "
                       "f^{ABD} = -i Tr([T_A,T_B]T_D)/K[D][D] is undefined for this D.")
                  {:kotoba.sm.gauge/reason :degenerate-gram-diagonal :D D :value v :K Kre})))))
    Kre))

(defn structure-constants
  "f[A][B][D] for ANY generator set whose own trace-Gram matrix
  K[A][B]=Tr(T_A T_B) is diagonal (checked via `diagonal-gram-real`, which
  throws if not -- see the namespace-level SCOPE note). Does NOT assume
  Tr(T^aT^b)=1/2delta^ab; it computes K from the generators themselves.

  f^{ABD} = -i Tr([T_A,T_B]T_D) / K[D][D].

  For the historical Tr(T^aT^b)=1/2delta^ab convention (Pauli/2, Gell-Mann/2)
  this is numerically identical to the old hard-coded f^{abc} =
  -2i Tr([T^a,T^b]T^c) formula -- see gauge_test.cljc for the regression
  proof (both against textbook values AND against a re-implementation of the
  old formula itself)."
  ([generators] (structure-constants generators 1e-9))
  ([generators eps]
   (let [n (count generators)
         K (diagonal-gram-real generators eps)]
     (vec (for [a (range n)]
            (vec (for [b (range n)]
                   (vec (for [d (range n)]
                          (let [comm (c/m-commutator (nth generators a) (nth generators b))
                                prod (c/m-mul comm (nth generators d))
                                tr (c/m-trace prod)
                                Kdd (get-in K [d d])
                                coeff (c/c 0 (- (/ 1.0 Kdd)))]
                            (c/re (c/c* coeff tr))))))))))))

;; ---------------------------------------------------------------------------
;; U(1) — abelian hypercharge/electric-charge generator
;; ---------------------------------------------------------------------------

(defn u1-generators
  "A single U(1) generator = charge * identity, acting on a `dim`-component
  field of that charge. Structure constants are trivially all zero (abelian)."
  [charge dim]
  [(c/m-rscale charge (c/m-identity dim))])

;; ---------------------------------------------------------------------------
;; SU(2) — weak isospin, generators = Pauli/2 (fundamental/doublet rep)
;; ---------------------------------------------------------------------------

(def su2-generators (mapv #(c/m-rscale 0.5 %) spinor/sigmas))

;; ---------------------------------------------------------------------------
;; SU(3) — color, generators = Gell-Mann/2 (fundamental/triplet rep)
;; ---------------------------------------------------------------------------

#?(:clj (defn- sqrt3 [] (Math/sqrt 3.0))
   :cljs (defn- sqrt3 [] (.sqrt js/Math 3.0)))

(def gell-mann
  (let [ii c/i neg-i (c/c 0 -1) z c/zero o c/one neg-o (c/c -1 0)
        s (/ 1.0 (sqrt3))]
    [[[z o z] [o z z] [z z z]]                                   ; lambda-1
     [[z neg-i z] [ii z z] [z z z]]                               ; lambda-2
     [[o z z] [z neg-o z] [z z z]]                                ; lambda-3
     [[z z o] [z z z] [o z z]]                                    ; lambda-4
     [[z z neg-i] [z z z] [ii z z]]                               ; lambda-5
     [[z z z] [z z o] [z o z]]                                    ; lambda-6
     [[z z z] [z z neg-i] [z ii z]]                                ; lambda-7
     [[(c/c s) z z] [z (c/c s) z] [z z (c/c (* -2 s))]]]))         ; lambda-8

(def su3-generators (mapv #(c/m-rscale 0.5 %) gell-mann))

;; ---------------------------------------------------------------------------
;; covariant derivative
;; ---------------------------------------------------------------------------

(defn gauge-correction
  "-i g sum_a A_mu^a (T^a psi) -- the pure gauge-interaction term, i.e. the part
  of the covariant derivative beyond the ordinary partial derivative. Kept
  separate from `covariant-derivative` so `kotoba.sm.standard-model` can sum
  the corrections from all three SM factor groups against a single partial
  derivative instead of nesting three additions of it."
  [Ts A-mu g psi]
  (if (empty? Ts)
    (vec (repeat (count psi) c/zero))
    (let [zero-vec (vec (repeat (count psi) c/zero))]
      (reduce c/v-add zero-vec
              (map (fn [Ta Aa]
                     (c/v-scale (c/c 0 (- (* g Aa))) (c/m-vec Ta psi)))
                   Ts A-mu)))))

(defn covariant-derivative
  "D_mu psi = d_mu psi - i g sum_a A_mu^a (T^a psi). `d-mu-psi` is the ordinary
  partial derivative of psi along this direction (numeric or supplied
  analytically); `Ts` are the generator matrices for psi's representation;
  `A-mu` is the vector of gauge-field components A_mu^a at this spacetime
  point, one per generator; `g` is the coupling constant."
  [d-mu-psi Ts A-mu g psi]
  (c/v-add d-mu-psi (gauge-correction Ts A-mu g psi)))

;; ---------------------------------------------------------------------------
;; field strength
;; ---------------------------------------------------------------------------

(defn gauge-field-gradient
  "Given a gauge-field function A-field: R^4 -> (vector-of-4 vector-of-n reals,
  A[nu][a] = A_nu^a(x)), compute d-A[mu][nu][a] = d/dx^mu A_nu^a(x) via central
  finite differences."
  ([A-field x] (gauge-field-gradient A-field x 1e-5))
  ([A-field x h]
   (vec (for [mu (range 4)]
          (let [xp (update x mu + h)
                xm (update x mu - h)
                Ap (A-field xp)
                Am (A-field xm)]
            (vec (for [nu (range 4)]
                   (mapv (fn [ap am] (/ (- ap am) (* 2 h))) (nth Ap nu) (nth Am nu)))))))))

(defn- self-interaction-term
  "g sum_b,c f^bca A_mu^b A_nu^c, for one generator index a.

  Slot order matters here and must match `structure-constants`'s own
  convention: that function defines f[A][B][D] from [T_A,T_B] = i f^{ABD} T_D,
  i.e. D -- the index of the generator T_D the commutator is expanded
  against -- is the OUTPUT/target index, and it sits in the THIRD array
  slot, `f-abc[A][B][D]`. In `g f^abc A_mu^b A_nu^c`, the free index `a`
  (the component of F_mu-nu^a being computed) plays that same target-index
  role -- it is the generator the self-interaction term is a coefficient
  of -- while `b` and `c` are the summed-over indices of A_mu and A_nu,
  matching the commutator's A and B slots. So the correct lookup is
  `(get-in f-abc [b cc a])`, NOT `(get-in f-abc [a b cc])`.

  This distinction is invisible for a totally antisymmetric f^ABC (true for
  every compact generator set actually used here -- U(1)/SU(2)/SU(3), whose
  uniform Tr(T^aT^b)=1/2delta^ab Gram matrix makes f^ABC fully antisymmetric
  under ANY permutation of its three indices, so which slot holds `a` makes
  no numerical difference -- see gauge_test.cljc's `self-interaction-term-*`
  slot-order regression tests). It matters once the Gram matrix K[A][B] is
  diagonal but non-uniform (rotation-type +1 vs boost-type -1 entries, as in
  so(1,3)'s bivector generators, `kotoba.sm.gtg`): there f^ABC is only
  antisymmetric under swapping its FIRST TWO indices (inherited from
  [T_A,T_B]=-[T_B,T_A]), not under moving the third index elsewhere, so
  reading the output index `a` out of the wrong slot silently breaks the
  physically required F_mu-nu^a = -F_nu-mu^a antisymmetry of the field
  strength. See `kotoba.sm.gtg-test`'s
  `rotation-field-strength-self-interaction-now-antisymmetric-*` tests."
  [f-abc g A mu nu a n]
  (let [A-mu (nth A mu)
        A-nu (nth A nu)]
    (* g (reduce +
                 (for [b (range n) cc (range n)]
                   (* (get-in f-abc [b cc a]) (nth A-mu b) (nth A-nu cc)))))))

(defn field-strength
  "F_mu-nu^a = d_mu A_nu^a - d_nu A_mu^a + g f^abc A_mu^b A_nu^c.
  `f-abc` are structure constants (see `structure-constants`, all-zero for
  abelian U(1)); `d-A[mu][nu][a]` = d_mu A_nu^a; `A[mu][a]` = A_mu^a."
  [f-abc g d-A A]
  (let [n (count (first A))]
    (vec
     (for [mu (range 4)]
       (vec
        (for [nu (range 4)]
          (vec
           (for [a (range n)]
             (let [curl (- (get-in d-A [mu nu a]) (get-in d-A [nu mu a]))
                   self (self-interaction-term f-abc g A mu nu a n)]
               (+ curl self))))))))))
