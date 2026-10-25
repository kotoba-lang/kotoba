(ns riff.bytes
  "Little-endian primitives for RIFF, and portable IEEE-754.

   RIFF is little-endian throughout (it comes from the 8086 world), which makes
   it the odd one out among the container formats in this workspace — Ogg is the
   only other one, and everything else is big-endian.

   Floats are decoded and encoded **arithmetically** rather than through a
   `DataView` or a `ByteBuffer`: sign, exponent and mantissa are taken apart by
   division. That keeps `f32`/`f64` support portable to both runtimes with no
   typed arrays in the API, at the cost of being slower than a host conversion —
   the right trade for a library that must run under nbb."
  (:refer-clojure :exclude [bytes]))

(defn u8 [v i] (nth v i))

(defn u16 [v i] (+ (nth v i) (* 256 (nth v (+ i 1)))))

(defn u32 [v i]
  (+ (nth v i) (* 256 (nth v (+ i 1))) (* 65536 (nth v (+ i 2)))
     (* 16777216 (nth v (+ i 3)))))

(defn i16 [v i] (let [x (u16 v i)] (if (>= x 32768) (- x 65536) x)))

(defn i24 [v i]
  (let [x (+ (nth v i) (* 256 (nth v (+ i 1))) (* 65536 (nth v (+ i 2))))]
    (if (>= x 8388608) (- x 16777216) x)))

(defn i32 [v i] (let [x (u32 v i)] (if (>= x 2147483648) (- x 4294967296) x)))

(defn put-u16 [n] [(bit-and n 0xff) (bit-and (quot n 256) 0xff)])

(defn put-u32 [n]
  [(bit-and n 0xff) (bit-and (quot n 256) 0xff)
   (bit-and (quot n 65536) 0xff) (bit-and (quot n 16777216) 0xff)])

(defn put-i16 [n] (put-u16 (if (neg? n) (+ n 65536) n)))

(defn put-i24 [n]
  (let [x (if (neg? n) (+ n 16777216) n)]
    [(bit-and x 0xff) (bit-and (quot x 256) 0xff) (bit-and (quot x 65536) 0xff)]))

(defn put-i32 [n] (put-u32 (if (neg? n) (+ n 4294967296) n)))

(defn fourcc
  "Four bytes as a string, for chunk ids."
  [v i]
  (apply str (map char (subvec (vec v) i (+ i 4)))))

(defn ->fourcc
  "A four-character string as bytes."
  [s]
  (mapv #(#?(:clj int :cljs (fn [c] (.charCodeAt c 0))) %) (seq s)))

;; ---------------------------------------------------------------------------
;; IEEE-754, arithmetically
;; ---------------------------------------------------------------------------

(defn- ldexp
  "`a * 2^e`, applied in chunks so a subnormal result (or a subnormal input) does
   not go through an intermediate 2^e that has already underflowed to zero.
   `(pow2 -1074)` is 0, and dividing by it is how a naive version loops forever
   on the smallest denormal."
  [a e]
  (loop [a (double a) e (long e)]
    (cond
      (zero? e) a
      (pos? e) (let [step (min e 500)] (recur (* a (Math/pow 2 step)) (- e step)))
      :else (let [step (min (- e) 500)] (recur (/ a (Math/pow 2 step)) (+ e step))))))

(defn- assemble
  "Rebuild a double from its sign, biased exponent and mantissa."
  [sign exponent mantissa mantissa-bits exponent-bits]
  (let [bias (dec (int (Math/pow 2 (dec exponent-bits))))
        exp-div (Math/pow 2 mantissa-bits)]
    (cond
      ;; denormal: value = mantissa * 2^(1 - bias - mantissa-bits). The sign of
      ;; that exponent is easy to get backwards; `(inc bias)` gave +972 instead of
      ;; -1074 for f64, so the smallest denormal decoded as 4e292.
      (zero? exponent) (* sign (ldexp mantissa (- 1 bias mantissa-bits)))
      (= exponent (dec (int (Math/pow 2 exponent-bits))))
      (if (zero? mantissa)
        (* sign #?(:clj Double/POSITIVE_INFINITY :cljs js/Infinity))
        #?(:clj Double/NaN :cljs js/NaN))
      :else (* sign (ldexp (+ 1.0 (/ mantissa exp-div)) (- exponent bias))))))

(defn- take-apart
  "Sign, biased exponent and mantissa of a double, for a given IEEE-754 layout.

   Nothing here forms a value above 2^53: an earlier version assembled all eight
   bytes of an f64 into one integer, which loses the low mantissa bits — 0.1 came
   back as 0.10000000000000142."
  [x mantissa-bits exponent-bits]
  (let [bias (dec (int (Math/pow 2 (dec exponent-bits))))
        max-exp (dec (int (Math/pow 2 exponent-bits)))
        negative? (or (neg? x)
                      (and (zero? x)
                           (= (/ -1.0 (double x))
                              #?(:clj Double/NEGATIVE_INFINITY :cljs js/-Infinity))))
        a (Math/abs (double x))]
    (into [(if negative? 1 0)]
          (cond
            (zero? a) [0 0]
            #?(:clj (Double/isNaN a) :cljs (js/isNaN a))
            [max-exp (Math/pow 2 (dec mantissa-bits))]
            #?(:clj (Double/isInfinite a) :cljs (not (js/isFinite a))) [max-exp 0]
            ;; below the smallest normal — decided before any nudging, because the
            ;; nudge loop oscillates forever on the smallest denormal
            (< a (ldexp 1.0 (- 1 bias)))
            [0 (Math/round (ldexp a (- (+ bias mantissa-bits) 1)))]
            :else
            (let [e (loop [e (Math/floor (/ (Math/log a) (Math/log 2)))]
                      (cond (>= (ldexp a (- e)) 2) (recur (inc e))
                            (< (ldexp a (- e)) 1) (recur (dec e))
                            :else e))
                  ;; Scale the normalised value first, then subtract the implicit
                  ;; bit. Subtracting 1.0 first re-normalises into [0,1), gaining
                  ;; an exponent and therefore a bit: the product then lands on a
                  ;; half-integer and rounding drops it.
                  m (- (Math/round (ldexp (ldexp a (- e)) mantissa-bits))
                       (Math/pow 2 mantissa-bits))
                  biased (+ e bias)]
              (if (>= biased max-exp) [max-exp 0] [biased m]))))))

;; The two layouts are written out rather than derived, because a generic
;; bit-splitter is where this went wrong once already.

(defn f32
  "32-bit IEEE-754 at `i`, little-endian."
  [v i]
  (let [b0 (nth v i) b1 (nth v (+ i 1)) b2 (nth v (+ i 2)) b3 (nth v (+ i 3))]
    (assemble (if (>= b3 128) -1 1)
              (+ (quot b2 128) (* 2 (mod b3 128)))
              (+ b0 (* 256 b1) (* 65536 (mod b2 128)))
              23 8)))

(defn f64
  "64-bit IEEE-754 at `i`, little-endian."
  [v i]
  (let [b (mapv #(nth v (+ i %)) (range 8))
        low (loop [k 0 acc 0 scale 1]
              (if (= k 6) acc (recur (inc k) (+ acc (* scale (nth b k))) (* scale 256))))]
    (assemble (if (>= (nth b 7) 128) -1 1)
              (+ (quot (nth b 6) 16) (* 16 (mod (nth b 7) 128)))
              (+ low (* (mod (nth b 6) 16) 281474976710656))   ; 2^48
              52 11)))

(defn put-f32 [x]
  (let [[sign exponent mantissa] (take-apart x 23 8)]
    [(int (mod mantissa 256))
     (int (mod (Math/floor (/ mantissa 256)) 256))
     (int (+ (mod (Math/floor (/ mantissa 65536)) 128) (* 128 (mod exponent 2))))
     (int (+ (Math/floor (/ exponent 2)) (* 128 sign)))]))

(defn put-f64 [x]
  (let [[sign exponent mantissa] (take-apart x 52 11)
        low (mapv (fn [k] (int (mod (Math/floor (/ mantissa (Math/pow 256 k))) 256)))
                  (range 6))]
    (conj low
          (int (+ (Math/floor (/ mantissa 281474976710656)) (* 16 (mod exponent 16))))
          (int (+ (Math/floor (/ exponent 16)) (* 128 sign))))))
