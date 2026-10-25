(ns kotoba.math
  "Floating-point and elementary math that answers the same on every host.

  Measured 2026-08-20 across amu / kotoba-kir / kotoba-native / kotoba-wasm /
  kototama / aiueos: 50 references to `Math/*`, in two repositories mainly,
  with nothing owning the surface. The frequency ranking is what shaped this
  namespace rather than a wish to mirror `java.lang.Math`:

      abs 14 · PI 8 · nextUp 4 · exp/log/pow 3 · ceil/floor/min/max/sqrt/rint 2
      · sin/nextDown/atan2 1

  **The three that justify a library rather than a reader conditional are
  `next-up`, `next-down` and `rint`.** JavaScript has no equivalent of any of
  them, so each cljs call site would otherwise hand-roll IEEE-754 bit
  manipulation -- and a hand-rolled `nextUp` that is subtly wrong still
  returns a plausible double. The rest are here so that a call site does not
  have to know which of the two categories it is in.

  Everything operates on host doubles. There is no wrapper type: these are
  used inside numeric loops where a box per operation would be paid on every
  one."
  (:refer-clojure :exclude [abs min max]))

(def PI #?(:clj Math/PI :cljs js/Math.PI))
(def E  #?(:clj Math/E  :cljs js/Math.E))

;; ---------------------------------------------------------------------------
;; Present on both hosts -- wrapped so a call site never has to branch.

(defn abs   [x] #?(:clj (Math/abs (double x))    :cljs (js/Math.abs x)))
(defn ceil  [x] #?(:clj (Math/ceil (double x))   :cljs (js/Math.ceil x)))
(defn floor [x] #?(:clj (Math/floor (double x))  :cljs (js/Math.floor x)))
(defn sqrt  [x] #?(:clj (Math/sqrt (double x))   :cljs (js/Math.sqrt x)))
(defn exp   [x] #?(:clj (Math/exp (double x))    :cljs (js/Math.exp x)))
(defn log   [x] #?(:clj (Math/log (double x))    :cljs (js/Math.log x)))
(defn sin   [x] #?(:clj (Math/sin (double x))    :cljs (js/Math.sin x)))
(defn cos   [x] #?(:clj (Math/cos (double x))    :cljs (js/Math.cos x)))
(defn pow   [x y] #?(:clj (Math/pow (double x) (double y)) :cljs (js/Math.pow x y)))
(defn atan2 [y x] #?(:clj (Math/atan2 (double y) (double x)) :cljs (js/Math.atan2 y x)))
(defn min   [x y] #?(:clj (Math/min (double x) (double y)) :cljs (js/Math.min x y)))
(defn max   [x y] #?(:clj (Math/max (double x) (double y)) :cljs (js/Math.max x y)))

;; ---------------------------------------------------------------------------
;; Absent from JavaScript entirely. These are the reason this namespace exists.

(defn rint
  "Round to the nearest integral double, ties to EVEN.

  `js/Math.round` is NOT this: it rounds ties toward +Infinity, so
  `(js/Math.round -0.5)` is `-0` and `(js/Math.round 2.5)` is `3`, while
  IEEE-754 round-half-to-even gives `-0` and `2`. Rounding mode is exactly the
  kind of difference that survives every round-trip test and then changes a
  content-addressed digest."
  [x]
  #?(:clj (Math/rint (double x))
     :cljs (let [f (js/Math.floor x)
                 d (- x f)]
             (cond
               (< d 0.5) f
               (> d 0.5) (inc f)
               ;; exactly .5 -- pick the even neighbour
               (zero? (mod f 2)) f
               :else (inc f)))))

(defn next-up
  "The least double strictly greater than X (IEEE-754 nextUp).

  JavaScript has no such operation, so this walks the bit pattern: a double's
  IEEE-754 encoding is ordered, so incrementing the magnitude bits of a
  positive value gives its successor. Done through a two-word view because JS
  bitwise operators truncate to int32 and cannot address the 64-bit pattern."
  [x]
  #?(:clj (Math/nextUp (double x))
     :cljs (cond
             (js/Number.isNaN x) x
             (= x js/Number.POSITIVE_INFINITY) x
             (zero? x) js/Number.MIN_VALUE
             :else
             (let [buf (js/ArrayBuffer. 8)
                   f (js/Float64Array. buf)
                   u (js/BigUint64Array. buf)]
               (aset f 0 x)
               (aset u 0 (if (> x 0)
                           (+ (aget u 0) (js/BigInt 1))
                           (- (aget u 0) (js/BigInt 1))))
               (aget f 0)))))

(defn next-down
  "The greatest double strictly less than X (IEEE-754 nextDown)."
  [x]
  #?(:clj (Math/nextDown (double x))
     :cljs (cond
             (js/Number.isNaN x) x
             (= x js/Number.NEGATIVE_INFINITY) x
             (zero? x) (- js/Number.MIN_VALUE)
             :else
             (let [buf (js/ArrayBuffer. 8)
                   f (js/Float64Array. buf)
                   u (js/BigUint64Array. buf)]
               (aset f 0 x)
               (aset u 0 (if (> x 0)
                           (- (aget u 0) (js/BigInt 1))
                           (+ (aget u 0) (js/BigInt 1))))
               (aget f 0)))))
