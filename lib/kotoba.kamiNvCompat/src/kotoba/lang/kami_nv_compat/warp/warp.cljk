(ns kotoba.lang.kami-nv-compat.warp.warp
  "NVIDIA Warp kernel-API parity stubs — JVM port of src/warp/warp.ts.
  Sequential single-threaded execution (for i < dim: kernel(inputs)).
  Covers: dtype sentinels, config, launch/tid/kernel/func, scalar math aliases,
  Vec3/Vec4/Quat/Transform value types (as plain vectors + standalone fns),
  WpArray mutable container, atomic ops. Wave 17 of ADR-2607020130.")

;; ── module constants ──────────────────────────────────────────────────────

(def ^:const pi Math/PI)

;; ── thread-local kernel state ─────────────────────────────────────────────

(def ^:dynamic ^{:doc "Thread index inside an in-flight kernel launch."} *tid* nil)

(defn tid
  "Thread index inside a kernel. Throws when called outside launch."
  ^long []
  (or *tid*
      (throw (ex-info "wp/tid called outside of wp/launch" {}))))

;; ── dtype sentinels ───────────────────────────────────────────────────────

(def dtype-names #{:float32 :float64 :int32 :int64 :uint32 :uint8 :bool})

(defn coerce-dtype
  "Coerce a value to the given dtype keyword."
  [dtype value]
  (case dtype
    (:float32 :float64) (double value)
    (:int32 :int64 :uint32 :uint8) (long value)
    :bool (boolean value)
    (double value)))

;; ── config + init ────────────────────────────────────────────────────────

(def config {:mode "release" :verify-cuda false :verify-fp false
             :print-launches false :cache-kernels true})

(defn init [] nil)

;; ── kernel / func / launch ────────────────────────────────────────────────

(defn kernel [fn] {:name "kernel" :fn fn})
(defn func [fn] fn)

(defn launch
  "Execute `:kernel` sequentially across the launch grid (`:dim`).
  `:inputs` / `:outputs` are concatenated and passed as args."
  [{:keys [kernel-fn dim inputs outputs]}]
  (let [total (if (number? dim) (long dim) (reduce * (map long dim)))
        _ (when (neg? total) (throw (ex-info "launch: dim must be >= 0" {:dim dim})))
        args (vec (concat (or inputs []) (or outputs [])))]
    (binding [*tid* nil]
      (dotimes [i total]
        (binding [*tid* i]
          (apply kernel-fn args))))))

;; ── scalar math aliases ──────────────────────────────────────────────────

(def sin Math/sin) (def cos Math/cos) (def tan Math/tan)
(def atan2 Math/atan2) (def sqrt Math/sqrt)
(def exp Math/exp) (def log Math/log)
(def floor Math/floor) (def ceil Math/ceil)

(defn wp-abs [x] (Math/abs (double x)))
(defn clamp [x low high] (max low (min high x)))

;; ── Vec3 / Vec4 (plain vectors [x y z] / [x y z w]) ──────────────────────

(defn vec3-add [a b] [(+ (a 0) (b 0)) (+ (a 1) (b 1)) (+ (a 2) (b 2))])
(defn vec3-sub [a b] [(- (a 0) (b 0)) (- (a 1) (b 1)) (- (a 2) (b 2))])
(defn vec3-mul [a b]
  (if (number? b)
    [(* (a 0) b) (* (a 1) b) (* (a 2) b)]
    [(* (a 0) (b 0)) (* (a 1) (b 1)) (* (a 2) (b 2))]))
(defn vec3-dot [a b] (+ (* (a 0) (b 0)) (* (a 1) (b 1)) (* (a 2) (b 2))))
(defn vec3-cross [a b]
  [(- (* (a 1) (b 2)) (* (a 2) (b 1)))
   (- (* (a 2) (b 0)) (* (a 0) (b 2)))
   (- (* (a 0) (b 1)) (* (a 1) (b 0)))])
(defn length [v] (Math/sqrt (reduce + (map #(* % %) v))))
(defn length-sq [v] (let [l (length v)] (* l l)))
(defn normalize [v]
  (let [n (length v)]
    (if (< n 1e-12) (vec (repeat (count v) 0))
        (vec (map #(/ % n) v)))))

;; ── Quaternion (plain vector [x y z w], Hamilton) ────────────────────────

(defn quat-identity [] [0.0 0.0 0.0 1.0])
(defn quat-from-axis-angle [axis angle]
  (let [n (length axis)]
    (if (< n 1e-12) [0.0 0.0 0.0 1.0]
        (let [u (vec (map #(/ % n) axis)) h (* angle 0.5) s (Math/sin h)]
          [(* (u 0) s) (* (u 1) s) (* (u 2) s) (Math/cos h)]))))
(defn quat-inverse [q] [(- (q 0)) (- (q 1)) (- (q 2)) (q 3)])
(defn quat-mul [a b]
  [(+ (* (a 3) (b 0)) (* (a 0) (b 3)) (* (a 1) (b 2)) (- (* (a 2) (b 1))))
   (- (* (a 3) (b 1)) (* (a 0) (b 2)) (* (a 1) (b 3)) (* (a 2) (b 0)))
   (+ (* (a 3) (b 2)) (* (a 0) (b 1)) (- (* (a 1) (b 0))) (* (a 2) (b 3)))
   (- (* (a 3) (b 3)) (* (a 0) (b 0)) (* (a 1) (b 1)) (* (a 2) (b 2)))])
(defn quat-rotate [q v]
  (let [tx (+ (- (* (q 1) (v 2)) (* (q 2) (v 1))) (* (q 3) (v 0)))
        ty (+ (- (* (q 2) (v 0)) (* (q 0) (v 2))) (* (q 3) (v 1)))
        tz (+ (- (* (q 0) (v 1)) (* (q 1) (v 0))) (* (q 3) (v 2)))]
    [(+ (v 0) (* 2.0 (- (* (q 1) tz) (* (q 2) ty))))
     (+ (v 1) (* 2.0 (- (* (q 2) tx) (* (q 0) tz))))
     (+ (v 2) (* 2.0 (- (* (q 0) ty) (* (q 1) tx))))]))
(defn quat-rotate-inv [q v] (quat-rotate (quat-inverse q) v))

;; ── Transform ({:p [x y z] :q [x y z w]}) ────────────────────────────────

(defn transform-identity [] {:p [0.0 0.0 0.0] :q (quat-identity)})
(defn transform-point [t p] (vec3-add (quat-rotate (:q t) p) (:p t)))
(defn transform-vector [t v] (quat-rotate (:q t) v))
(defn transform-get-translation [t] (:p t))
(defn transform-get-rotation [t] (:q t))
(defn transform-multiply [a b]
  {:q (quat-mul (:q a) (:q b))
   :p (vec3-add (quat-rotate (:q a) (:p b)) (:p a))})

;; ── WpArray (atom-backed mutable indexed array) ──────────────────────────

(defn wp-array
  "Build a mutable WpArray from a vector."
  ([data] (atom (vec data))))

(defn wp-zeros [dtype n] (atom (vec (repeat n 0))))
(defn wp-empty [dtype n] (atom (vec (repeat n 0))))
(defn wp-from-typed-array [data] (atom (vec data)))
(defn wp-get [arr i] (nth @arr i))
(defn wp-set [arr i v] (swap! arr assoc i v) v)
(defn wp-length [arr] (count @arr))
(defn wp-index-of [arr i] (wp-get arr i))

;; ── Atomic ops (single-threaded — semantically correct) ──────────────────

(defn atomic-add [arr i v] (let [old (wp-get arr i)] (wp-set arr i (+ old v)) old))
(defn atomic-sub [arr i v] (let [old (wp-get arr i)] (wp-set arr i (- old v)) old))
(defn atomic-max [arr i v] (let [old (wp-get arr i)] (wp-set arr i (max old v)) old))
(defn atomic-min [arr i v] (let [old (wp-get arr i)] (wp-set arr i (min old v)) old))
