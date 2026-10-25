(ns nagare.linsolve
  "Sparse linear solvers over the mesh adjacency — pure Clojure, no BLAS.

  Every `fvm` operator assembles the *same* sparse shape: a dense **diagonal**
  (one coefficient per cell) plus two off-diagonal arrays indexed by internal
  face — `upper[f]` is the owner-row/neighbour-column coupling and `lower[f]` the
  neighbour-row/owner-column coupling. That is exactly enough to multiply the
  matrix by a vector without ever materialising it: sweep the faces, scattering
  `upper[f]*x[neighbour]` into the owner and `lower[f]*x[owner]` into the
  neighbour. This is the finite-volume analogue of a CSR matvec, and it is the
  only kernel the Krylov methods need.

  ## Which solver for which system
  - **PCG** — for the **symmetric positive-definite** pressure-Poisson matrix
    (`upper == lower`). Conjugate gradients with a Jacobi (diagonal)
    preconditioner; the right tool because the discrete Laplacian is SPD.
  - **BiCGStab** — for the **asymmetric** momentum matrix, where upwind convection
    makes `upper != lower`. Stabilised bi-conjugate gradients, Jacobi-preconditioned.
  - **Jacobi / Gauss-Seidel** — the classic stationary smoothers, kept both as a
    fallback and as the conceptual bridge (a single GS sweep is one multigrid
    smoothing step).

  All return `{:x <double-array> :residual <relative> :iterations <n>}`. Vectors
  are primitive `double[]` so the inner loops stay allocation-free and fast enough
  to run in a browser tab."
  #?(:clj (:require [kotoba.lang.text])))

;; ---------------------------------------------------------------------------
;; Primitive vector helpers
;; ---------------------------------------------------------------------------

(defn- dot ^double [^doubles a ^doubles b]
  (areduce a i s 0.0 (+ s (* (aget a i) (aget b i)))))

(defn- norm ^double [^doubles a] (Math/sqrt (dot a a)))

(defn- copy ^doubles [^doubles a]
  #?(:clj (java.util.Arrays/copyOf a (alength a))
     :cljs (let [n (alength a) r (double-array n)]
             (dotimes [i n] (aset r i (aget a i))) r)))

(defn- zeros ^doubles [n] (double-array n))

;; y <- A x   (matvec into preallocated y)
(defn- matvec! [matrix ^doubles x ^doubles y]
  (let [n (int (:n matrix))
        ^doubles diag (:diag matrix)
        ^ints    own  (:owner matrix)
        ^ints    nei  (:neighbour matrix)
        ^doubles up   (:upper matrix)
        ^doubles lo   (:lower matrix)
        nf (int (alength up))]
    (dotimes [i n] (aset y i (* (aget diag i) (aget x i))))
    (dotimes [f nf]
      (let [o (aget own f) p (aget nei f)]
        (aset y o (+ (aget y o) (* (aget up f) (aget x p))))
        (aset y p (+ (aget y p) (* (aget lo f) (aget x o))))))
    y))

(defn mat-vec
  "Public `A*x` returning a fresh `double-array` (used by tests)."
  [matrix x]
  (let [^doubles xx (double-array (seq x))]
    (matvec! matrix xx (zeros (:n matrix)))))

(defn- coerce
  "Normalise a matrix map's arrays to primitive `double[]`/`int[]`."
  [m]
  (assoc m
         :n         (int (:n m))
         :diag      (double-array (seq (:diag m)))
         :owner     (int-array (seq (:owner m)))
         :neighbour (int-array (seq (:neighbour m)))
         :upper     (double-array (seq (:upper m)))
         :lower     (double-array (seq (:lower m)))))

;; ---------------------------------------------------------------------------
;; Stationary smoothers
;; ---------------------------------------------------------------------------

(defn- row-adjacency
  "Build per-row CSR-ish adjacency from the face arrays: for each cell, the list of
  (column, coefficient) entries (owner faces give `(neighbour, upper)`, neighbour
  faces give `(owner, lower)`). Used by Gauss-Seidel, which needs in-order row
  access the face loop alone cannot give."
  [m]
  (let [n (int (:n m))
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles up (:upper m) ^doubles lo (:lower m)
        nf (int (alength up))
        cols (object-array n) coefs (object-array n)]
    (dotimes [i n] (aset cols i (transient [])) (aset coefs i (transient [])))
    (dotimes [f nf]
      (let [o (aget own f) p (aget nei f)]
        (aset cols o (conj! (aget cols o) p)) (aset coefs o (conj! (aget coefs o) (aget up f)))
        (aset cols p (conj! (aget cols p) o)) (aset coefs p (conj! (aget coefs p) (aget lo f)))))
    [(mapv #(int-array (persistent! %)) cols)
     (mapv #(double-array (persistent! %)) coefs)]))

(defn jacobi
  "Jacobi iteration: every cell updated *simultaneously* from the previous iterate.
  Converges for diagonally dominant systems; the simplest stationary smoother."
  [matrix b {:keys [max-iter tol x0] :or {max-iter 1000 tol 1e-8}}]
  (let [m (coerce matrix)
        n (int (:n m))
        ^doubles diag (:diag m)
        ^ints own (:owner m) ^ints nei (:neighbour m)
        ^doubles up (:upper m) ^doubles lo (:lower m)
        nf (int (alength up))
        ^doubles bb (double-array (seq b))
        ^doubles x (if x0 (copy (double-array (seq x0))) (zeros n))
        bnorm (max 1e-300 (norm bb))
        ^doubles off (zeros n) r (zeros n)]
    (loop [it 0]
      (dotimes [i n] (aset off i 0.0))
      (dotimes [f nf]
        (let [o (aget own f) p (aget nei f)]
          (aset off o (+ (aget off o) (* (aget up f) (aget x p))))
          (aset off p (+ (aget off p) (* (aget lo f) (aget x o))))))
      (dotimes [i n] (aset x i (/ (- (aget bb i) (aget off i)) (aget diag i))))
      (matvec! m x r)
      (dotimes [i n] (aset r i (- (aget bb i) (aget r i))))
      (let [res (/ (norm r) bnorm)]
        (if (or (< res tol) (>= it max-iter))
          {:x x :residual res :iterations it}
          (recur (inc it)))))))

(defn gauss-seidel
  "Gauss-Seidel: a forward sweep that uses the *most recent* neighbour values as it
  goes (`x[i]` updated in place before cell `i+1` reads it). Faster-converging than
  Jacobi and the canonical multigrid smoother."
  [matrix b {:keys [max-iter tol x0] :or {max-iter 1000 tol 1e-8}}]
  (let [m (coerce matrix)
        n (int (:n m))
        ^doubles diag (:diag m)
        [cols coefs] (row-adjacency m)
        ^doubles bb (double-array (seq b))
        ^doubles x (if x0 (copy (double-array (seq x0))) (zeros n))
        bnorm (max 1e-300 (norm bb))
        r (zeros n)]
    (loop [it 0]
      (dotimes [i n]
        (let [^ints ci (nth cols i) ^doubles ki (nth coefs i)
              s (areduce ci j acc 0.0 (+ acc (* (aget ki j) (aget x (aget ci j)))))]
          (aset x i (/ (- (aget bb i) s) (aget diag i)))))
      (matvec! m x r)
      (dotimes [i n] (aset r i (- (aget bb i) (aget r i))))
      (let [res (/ (norm r) bnorm)]
        (if (or (< res tol) (>= it max-iter))
          {:x x :residual res :iterations it}
          (recur (inc it)))))))

;; ---------------------------------------------------------------------------
;; PCG — symmetric positive-definite (pressure)
;; ---------------------------------------------------------------------------

(defn pcg
  "Preconditioned Conjugate Gradient for a **symmetric positive-definite** system,
  with a Jacobi (diagonal) preconditioner `M^-1 = 1/diag`. Assumes `upper==lower`."
  [matrix b {:keys [max-iter tol x0] :or {max-iter 2000 tol 1e-8}}]
  (let [m (coerce matrix)
        n (int (:n m))
        ^doubles diag (:diag m)
        ^doubles bb (double-array (seq b))
        ^doubles x  (if x0 (copy (double-array (seq x0))) (zeros n))
        ^doubles r  (zeros n)
        ^doubles z  (zeros n)
        ^doubles p  (zeros n)
        ^doubles Ap (zeros n)
        bnorm (max 1e-300 (norm bb))]
    ;; r = b - A x
    (matvec! m x r)
    (dotimes [i n] (aset r i (- (aget bb i) (aget r i))))
    ;; z = M^-1 r ; p = z
    (dotimes [i n] (let [zi (/ (aget r i) (aget diag i))] (aset z i zi) (aset p i zi)))
    (loop [it 0 rz (dot r z)]
      (let [res (/ (norm r) bnorm)]
        (if (or (< res tol) (>= it max-iter) (== rz 0.0))
          {:x x :residual res :iterations it}
          (do
            (matvec! m p Ap)
            (let [pAp (dot p Ap)
                  alpha (if (== pAp 0.0) 0.0 (/ rz pAp))]
              (dotimes [i n]
                (aset x i (+ (aget x i) (* alpha (aget p i))))
                (aset r i (- (aget r i) (* alpha (aget Ap i)))))
              (dotimes [i n] (aset z i (/ (aget r i) (aget diag i))))
              (let [rz' (dot r z)
                    beta (if (== rz 0.0) 0.0 (/ rz' rz))]
                (dotimes [i n] (aset p i (+ (aget z i) (* beta (aget p i)))))
                (recur (inc it) rz')))))))))

;; ---------------------------------------------------------------------------
;; BiCGStab — asymmetric (momentum)
;; ---------------------------------------------------------------------------

(defn bicgstab
  "Jacobi-preconditioned BiCGStab for a general (asymmetric) sparse system —
  the upwind momentum matrix where `upper != lower`."
  [matrix b {:keys [max-iter tol x0] :or {max-iter 2000 tol 1e-8}}]
  (let [m (coerce matrix)
        n (int (:n m))
        ^doubles diag (:diag m)
        ^doubles bb (double-array (seq b))
        ^doubles x  (if x0 (copy (double-array (seq x0))) (zeros n))
        ^doubles r  (zeros n)
        ^doubles rh (zeros n)
        ^doubles p  (zeros n)
        ^doubles v  (zeros n)
        ^doubles s  (zeros n)
        ^doubles t  (zeros n)
        ^doubles ph (zeros n)            ; preconditioned p
        ^doubles sh (zeros n)            ; preconditioned s
        bnorm (max 1e-300 (norm bb))
        prec! (fn [^doubles src ^doubles dst]
                (dotimes [i n] (aset dst i (/ (aget src i) (aget diag i)))))]
    (matvec! m x r)
    (dotimes [i n] (let [ri (- (aget bb i) (aget r i))] (aset r i ri) (aset rh i ri)))
    (loop [it 0 rho 1.0 alpha 1.0 omega 1.0]
      (let [res (/ (norm r) bnorm)]
        (if (or (< res tol) (>= it max-iter))
          {:x x :residual res :iterations it}
          (let [rho' (dot rh r)]
            (if (== rho' 0.0)
              {:x x :residual res :iterations it}          ; breakdown
              (let [beta (* (/ rho' rho) (/ alpha omega))]
                (dotimes [i n]
                  (aset p i (+ (aget r i) (* beta (- (aget p i) (* omega (aget v i)))))))
                (prec! p ph)
                (matvec! m ph v)
                (let [alpha' (/ rho' (dot rh v))]
                  (dotimes [i n] (aset s i (- (aget r i) (* alpha' (aget v i)))))
                  ;; early convergence on s
                  (prec! s sh)
                  (matvec! m sh t)
                  (let [tt (dot t t)
                        omega' (if (== tt 0.0) 0.0 (/ (dot t s) tt))]
                    (dotimes [i n]
                      (aset x i (+ (aget x i) (* alpha' (aget ph i)) (* omega' (aget sh i))))
                      (aset r i (- (aget s i) (* omega' (aget t i)))))
                    (if (== omega' 0.0)
                      {:x x :residual (/ (norm r) bnorm) :iterations (inc it)}
                      (recur (inc it) rho' alpha' omega'))))))))))))

;; ---------------------------------------------------------------------------
;; Convergence monitoring
;; ---------------------------------------------------------------------------

(defn scaled-residual
  "OpenFOAM-style **normalized** residual for a linear system `A x = b`:

      x̄          = mean(x)  (the uniform reference field)
      normFactor = Σ|A x − A x̄| + Σ|b − A x̄| + ε
      residual   = Σ|b − A x| / normFactor

  Scale-free: 1 means 'no better than the mean field', 0 means solved. Dividing
  by the same flux/coefficient scale on every mesh makes it the right per-equation
  convergence monitor for a SIMPLE/PISO run. Returns a double in [0, ~1]."
  [matrix b x]
  (let [n (int (:n matrix))
        ^doubles bb (double-array (seq b))
        ^doubles ax (mat-vec matrix x)
        xbar (/ (reduce + (map double (seq x))) (double n))
        ^doubles axref (mat-vec matrix (double-array n xbar))
        sum (fn [f] (loop [i 0 s 0.0] (if (< i n) (recur (inc i) (+ s (double (f i)))) s)))
        norm (+ (sum (fn [i] (Math/abs (- (aget ax i) (aget axref i)))))
                (sum (fn [i] (Math/abs (- (aget bb i) (aget axref i)))))
                1.0e-30)
        res  (sum (fn [i] (Math/abs (- (aget bb i) (aget ax i)))))]
    (/ res norm)))
