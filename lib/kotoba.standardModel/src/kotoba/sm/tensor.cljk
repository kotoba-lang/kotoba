(ns kotoba.sm.tensor
  "Minkowski tensor algebra. Metric signature is fixed to MOSTLY-MINUS
  eta = diag(1,-1,-1,-1) (Bjorken-Drell / 'west-coast' convention, the one used by
  Peskin & Schroeder and Halzen & Martin) -- the other common QFT-textbook choice
  (mostly-plus, diag(-1,1,1,1)) flips several signs downstream (Clifford algebra,
  field-strength contraction), so this is called out explicitly rather than left
  implicit.

  Rank-1 tensors (four-vectors) are plain 4-element real vectors [t x y z].
  Rank-2 tensors (F_mu-nu, T^mu-nu, ...) are 4x4 nested real vectors, component
  index order always mu then nu (row then column). Whether a given index is
  'upper' or 'lower' is bookkeeping the caller tracks; raise/lower move between
  them via the metric, which is its own inverse in this basis (eta eta = I).")

;; ---------------------------------------------------------------------------
;; metric
;; ---------------------------------------------------------------------------

(def metric
  "eta_mu-nu = eta^mu-nu = diag(1,-1,-1,-1)."
  [[1 0 0 0]
   [0 -1 0 0]
   [0 0 -1 0]
   [0 0 0 -1]])

;; ---------------------------------------------------------------------------
;; plain real vector/matrix helpers (tensors here are real-valued: metric,
;; field-strength, stress-energy -- complex algebra lives in kotoba.sm.complex
;; and is used only by spinor/gauge fields)
;; ---------------------------------------------------------------------------

(defn v+ [a b] (mapv + a b))
(defn v- [a b] (mapv - a b))
(defn v-neg [a] (mapv - a))
(defn v-scale [s v] (mapv #(* s %) v))
(defn v-dot
  "Plain Euclidean/Kronecker dot product (no metric) -- component sum, used
  internally by matrix ops. For the physical Minkowski inner product use `dot`."
  [a b]
  (reduce + (map * a b)))

(defn mat-vec [m v] (mapv #(v-dot % v) m))
(defn mat-transpose [m] (apply mapv vector m))
(defn mat-mat [a b]
  (let [bt (mat-transpose b)]
    (mapv (fn [row] (mapv #(v-dot row %) bt)) a)))
(defn mat-add [a b] (mapv v+ a b))
(defn mat-scale [s m] (mapv #(v-scale s %) m))
(defn mat-trace [m] (reduce + (map-indexed (fn [i row] (nth row i)) m)))

;; ---------------------------------------------------------------------------
;; general square-matrix determinant/inverse (adjugate/cofactor method).
;;
;; This is ORDINARY linear algebra -- the textbook Laplace-expansion
;; determinant and the classical-adjoint inverse formula m^-1 = adj(m)/det(m)
;; -- with no physics convention baked in (unlike `metric`/`lower`/`raise`
;; above, which are specific to this namespace's mostly-minus signature).
;; `kotoba.sm.gtg` uses this at N=4 to invert the position gauge field h and
;; build its reciprocal frame (`kotoba.sm.gtg/reciprocal-frame`); the
;; implementation itself works for any square N (recursive cofactor
;; expansion), not hard-coded to 4x4.
;; ---------------------------------------------------------------------------

(defn mat-minor
  "The (n-1)x(n-1) submatrix of square matrix `m` obtained by deleting row `i`
  and column `j` (0-indexed) -- the standard 'minor' of linear algebra."
  [m i j]
  (vec (for [row (concat (subvec m 0 i) (subvec m (inc i)))]
         (vec (concat (subvec row 0 j) (subvec row (inc j)))))))

(defn mat-det
  "Determinant of a square matrix, via Laplace/cofactor expansion along row 0
  (recursive; base cases 1x1 and 2x2). General N, not hard-coded to 4x4."
  [m]
  (let [n (count m)]
    (cond
      (= n 1) (get-in m [0 0])
      (= n 2) (- (* (get-in m [0 0]) (get-in m [1 1]))
                 (* (get-in m [0 1]) (get-in m [1 0])))
      :else (reduce +
                     (for [j (range n)]
                       (* (if (even? j) 1 -1)
                          (get-in m [0 j])
                          (mat-det (mat-minor m 0 j))))))))

(defn mat-adjugate
  "The adjugate (classical adjoint) of a square matrix: the transpose of its
  cofactor matrix, adj(m)[i][j] = (-1)^(i+j) * det(minor m j i) (the (j,i)
  cofactor, placed at (i,j) -- i.e. already transposed relative to the
  cofactor matrix itself, so `mat-inverse` does not need a separate
  `mat-transpose` step). Satisfies m . adj(m) = adj(m) . m = det(m) * I for
  any square m, invertible or not (the standard adjugate identity) --
  `mat-inverse` divides by `mat-det` to get the actual inverse when det != 0."
  [m]
  (let [n (count m)]
    (vec (for [i (range n)]
           (vec (for [j (range n)]
                  (* (if (even? (+ i j)) 1 -1)
                     (mat-det (mat-minor m j i)))))))))

(defn mat-inverse
  "The inverse of a square matrix `m`, via the adjugate/determinant method
  m^-1 = adj(m) / det(m). Throws `ex-info` if `det(m)` is ~0 (within `eps`),
  i.e. `m` is singular/non-invertible -- the same 'throw rather than silently
  divide by ~0' spirit as `kotoba.sm.gauge/diagonal-gram-real`'s guard on a
  ~0 Gram-matrix diagonal entry, applied here to a general matrix inverse
  instead of that function's Gram-matrix-diagonal special case.

  Uses `(/ 1 d)`, not `(/ 1.0 d)`, so that an exact-integer `m` (e.g. the
  identity matrix) with an exact-integer, nonzero determinant produces an
  EXACT (Clojure ratio/integer, not floating-point-rounded) result -- in
  particular `(mat-inverse identity-matrix)` is bit-for-bit the identity
  matrix again, not merely numerically close to it. For a floating-point `m`
  (the common case for a general position-gauge field h), `d` is already a
  double and `(/ 1 d)` behaves exactly like ordinary floating-point division.
  (This exactness is a `:clj`-only bonus: ClojureScript has no exact ratio
  type, so `(/ 1 d)` for an integer `d` other than +/-1 is already a rounded
  float there -- this namespace's OTHER exactness claims, e.g.
  `kotoba.sm.gtg`'s flat-limit metric checks, do not depend on ratios and
  hold on both platforms; only THIS specific exact-integer-inverse case is
  JVM-only, and only for divisors that are not +/-1.)"
  ([m] (mat-inverse m 1e-9))
  ([m eps]
   (let [d (mat-det m)]
     (when (<= (Math/abs (double d)) eps)
       (throw (ex-info
               (str "kotoba.sm.tensor/mat-inverse: matrix is singular (determinant "
                    d " is ~0, within eps=" eps ") -- not invertible.")
               {:kotoba.sm.tensor/reason :singular-matrix :det d :m m})))
     (mat-scale (/ 1 d) (mat-adjugate m)))))

;; ---------------------------------------------------------------------------
;; index raise/lower, invariant products (rank 1)
;; ---------------------------------------------------------------------------

(defn lower
  "v^mu -> v_mu = eta_mu-nu v^nu."
  [v]
  (mat-vec metric v))

(defn raise
  "v_mu -> v^mu = eta^mu-nu v_nu. Same operation as `lower` in this basis
  (eta is its own matrix inverse), kept as a distinct name for readability at
  call sites."
  [v]
  (mat-vec metric v))

(defn dot
  "Minkowski invariant inner product v.w = eta_mu-nu v^mu w^nu."
  [v w]
  (v-dot (lower v) w))

(defn norm2
  "Invariant p.p (mass^2 c^4 for a four-momentum, natural units)."
  [v]
  (dot v v))

;; ---------------------------------------------------------------------------
;; rank-2 tensors
;; ---------------------------------------------------------------------------

(defn outer
  "Rank-1 (x) rank-1 -> rank-2: (outer v w)[mu][nu] = v^mu w^nu."
  [v w]
  (mapv (fn [vi] (mapv #(* vi %) w)) v))

(defn transpose2 [t] (mat-transpose t))

(defn lower-first
  "T^mu-nu -> T_mu^nu (lower the first index)."
  [t]
  (mat-mat metric t))

(defn lower-second
  "T^mu-nu -> T^mu_nu (lower the second index)."
  [t]
  (mat-mat t metric))

(defn lower2
  "T^mu-nu -> T_mu-nu (lower both indices)."
  [t]
  (mat-mat metric (mat-mat t metric)))

(defn raise2
  "T_mu-nu -> T^mu-nu (raise both indices; same op as lower2 in this basis)."
  [t]
  (lower2 t))

(defn antisymmetrize
  "Build the antisymmetric part of a rank-2 tensor: 1/2 (T - T^T)."
  [t]
  (mat-scale (/ 1.0 2.0) (mat-add t (mat-scale -1 (transpose2 t)))))

(defn full-contract
  "Full double contraction of two rank-2 tensors with opposite index heights,
  e.g. F^mu-nu F_mu-nu = sum_mu-nu F^mu-nu F_mu-nu -- a Lorentz scalar."
  [t-upper t-lower]
  (reduce + (for [mu (range 4) nu (range 4)]
              (* (nth (nth t-upper mu) nu) (nth (nth t-lower mu) nu)))))

;; ---------------------------------------------------------------------------
;; Levi-Civita symbol (rank 4)
;; ---------------------------------------------------------------------------

(defn- permutation-parity
  "+1/-1 for an even/odd permutation of 4 distinct comparable elements
  (relative to their sorted order), via inversion-count parity."
  [xs]
  (let [arr (vec xs) n (count arr)
        inversions (reduce + (for [i2 (range n) j (range (inc i2) n)
                                    :when (> (nth arr i2) (nth arr j))]
                                1))]
    (if (even? inversions) 1 -1)))

(defn levi-civita4
  "epsilon^mu-nu-rho-sigma over indices 0..3, with epsilon^0123 = +1
  (identity permutation), totally antisymmetric, 0 if any index repeats."
  [a b c d]
  (if (= (sort [a b c d]) [0 1 2 3])
    (permutation-parity [a b c d])
    0))
