(ns kotoba.sm.complex
  "Complex scalar + complex matrix algebra — the shared foundation `kotoba.sm.spinor`
  (4x4 gamma matrices) and `kotoba.sm.gauge` (2x2/3x3 Lie-algebra generators) both
  build their fixed-size matrices on top of, instead of each reimplementing matmul.

  A complex scalar is a 2-vector `[re im]`. A complex matrix is a vector of row
  vectors of complex scalars: `[[c00 c01 ...] [c10 c11 ...] ...]`.")

;; ---------------------------------------------------------------------------
;; scalars
;; ---------------------------------------------------------------------------

(defn c
  "Build a complex scalar from real/imaginary parts (imaginary defaults to 0)."
  ([re] [re 0])
  ([re im] [re im]))

(def zero [0 0])
(def one [1 0])
(def i [0 1])

(defn re [[a _]] a)
(defn im [[_ b]] b)

(defn c+
  ([] zero)
  ([x] x)
  ([[a b] [c2 d]] [(+ a c2) (+ b d)])
  ([x y & more] (reduce c+ (c+ x y) more)))

(defn c-neg [[a b]] [(- a) (- b)])

(defn c-
  ([x] (c-neg x))
  ([x y] (c+ x (c-neg y)))
  ([x y & more] (reduce c- (c- x y) more)))

(defn c*
  ([] one)
  ([x] x)
  ([[a b] [c2 d]] [(- (* a c2) (* b d)) (+ (* a d) (* b c2))])
  ([x y & more] (reduce c* (c* x y) more)))

(defn conj* [[a b]] [a (- b)])

(defn abs2
  "|z|^2 = z z-bar, returned as a real number."
  [[a b]]
  (+ (* a a) (* b b)))

#?(:clj (defn- sqrt [x] (Math/sqrt x))
   :cljs (defn- sqrt [x] (.sqrt js/Math x)))

(defn modulus [z] (sqrt (abs2 z)))

(defn scale
  "Real-scalar * complex-scalar."
  [s [a b]]
  [(* s a) (* s b)])

(defn real?
  "True if the imaginary part is (numerically) zero."
  ([z] (real? z 1e-9))
  ([[_ b] eps] (< (* b b) (* eps eps))))

(defn approx=
  "Tolerance-based equality for complex scalars (used by tests)."
  ([x y] (approx= x y 1e-9))
  ([x y eps] (< (abs2 (c- x y)) (* eps eps))))

;; ---------------------------------------------------------------------------
;; matrices — vector of row vectors of complex scalars
;; ---------------------------------------------------------------------------

(defn m-zero [rows cols]
  (vec (repeat rows (vec (repeat cols zero)))))

(defn m-identity [n]
  (vec (for [r (range n)]
         (vec (for [c2 (range n)] (if (= r c2) one zero))))))

(defn m-real
  "Lift a real-number matrix (vector of vectors of numbers) to complex entries."
  [rows]
  (mapv (fn [row] (mapv c row)) rows))

(defn m-dims [m] [(count m) (count (first m))])

(defn m-add [a b]
  (mapv (fn [ra rb] (mapv c+ ra rb)) a b))

(defn m-sub [a b]
  (mapv (fn [ra rb] (mapv c- ra rb)) a b))

(defn m-scale
  "Complex-scalar * complex-matrix."
  [s m]
  (mapv (fn [row] (mapv #(c* s %) row)) m))

(defn m-rscale
  "Real-scalar * complex-matrix."
  [s m]
  (mapv (fn [row] (mapv #(scale s %) row)) m))

(defn transpose [m]
  (apply mapv vector m))

(defn m-conj [m]
  (mapv (fn [row] (mapv conj* row)) m))

(defn m-dagger
  "Conjugate transpose (Hermitian adjoint), A -> A^dagger."
  [m]
  (m-conj (transpose m)))

(defn m-mul
  ([] nil)
  ([a] a)
  ([a b]
   (let [bt (transpose b)]
     (mapv (fn [row] (mapv (fn [col] (apply c+ (map c* row col))) bt)) a)))
  ([a b & more] (reduce m-mul (m-mul a b) more)))

(defn m-vec
  "Complex matrix * complex column vector -> complex column vector."
  [m v]
  (mapv (fn [row] (apply c+ (map c* row v))) m))

(defn m-trace [m]
  (apply c+ (map-indexed (fn [idx row] (nth row idx)) m)))

(defn m-commutator
  "[A,B] = AB - BA."
  [a b]
  (m-sub (m-mul a b) (m-mul b a)))

(defn m-hermitian?
  ([m] (m-hermitian? m 1e-9))
  ([m eps]
   (every? true?
           (for [r (range (count m)) c2 (range (count m))]
             (approx= (nth (nth m r) c2) (conj* (nth (nth m c2) r)) eps)))))

;; ---------------------------------------------------------------------------
;; complex vectors (spinors, gauge-multiplet components) — vector of complex scalars
;; ---------------------------------------------------------------------------

(defn v-add [a b] (mapv c+ a b))
(defn v-sub [a b] (mapv c- a b))

(defn v-scale
  "Complex-scalar * complex-vector (component-wise)."
  [s v]
  (mapv #(c* s %) v))

(defn v-conj [v] (mapv conj* v))

(defn v-approx=
  ([a b] (v-approx= a b 1e-9))
  ([a b eps] (every? true? (map #(approx= %1 %2 eps) a b))))

(defn m-approx=
  ([a b] (m-approx= a b 1e-9))
  ([a b eps]
   (every? true? (map #(v-approx= %1 %2 eps) a b))))
