(ns zstd.xxhash
  "XXH64 — the checksum a zstd frame carries (RFC 8878 §3.1.1, low 32 bits of the
   64-bit hash over the decompressed content).

   XXH64 is defined entirely in terms of 64-bit wrapping multiplication and
   rotation, which ClojureScript does not have: `Number` loses bits above 2^53 and
   the bitwise operators are 32-bit. So everything here is a `[hi lo]` pair of
   unsigned 32-bit halves, and the multiply is a schoolbook 16-bit limb product.

   `mod`/`quot` rather than `bit-and`/`bit-shift-left` throughout the multiply:
   the partial products reach ~1.7e10, and a bitwise operation would truncate
   them to int32 first."
  (:refer-clojure :exclude [bytes]))

(defn- u32 [x] (if (neg? x) (+ x 4294967296) x))

(def ^:private pow2
  (vec (reductions * 1 (repeat 32 2))))

(def ^:private p1 [0x9e3779b1 0x85ebca87])
(def ^:private p2 [0xc2b2ae3d 0x27d4eb4f])
(def ^:private p3 [0x165667b1 0x9e3779f9])
(def ^:private p4 [0x85ebca77 0xc2b2ae63])
(def ^:private p5 [0x27d4eb2f 0x165667c5])

(defn- add [[h1 l1] [h2 l2]]
  (let [lo (+ l1 l2)]
    [(mod (+ h1 h2 (if (>= lo 4294967296) 1 0)) 4294967296)
     (mod lo 4294967296)]))

(defn- sub [[h1 l1] [h2 l2]]
  (let [lo (- l1 l2)]
    [(mod (- h1 h2 (if (neg? lo) 1 0)) 4294967296)
     (mod lo 4294967296)]))

(defn- xor* [[h1 l1] [h2 l2]]
  [(u32 (bit-xor h1 h2)) (u32 (bit-xor l1 l2))])

(defn- mul [a b]
  (let [al [(mod (nth a 1) 65536) (quot (nth a 1) 65536)
            (mod (nth a 0) 65536) (quot (nth a 0) 65536)]
        bl [(mod (nth b 1) 65536) (quot (nth b 1) 65536)
            (mod (nth b 0) 65536) (quot (nth b 0) 65536)]
        p0 (* (nth al 0) (nth bl 0))
        p1* (+ (* (nth al 0) (nth bl 1)) (* (nth al 1) (nth bl 0)))
        p2* (+ (* (nth al 0) (nth bl 2)) (* (nth al 1) (nth bl 1)) (* (nth al 2) (nth bl 0)))
        p3* (+ (* (nth al 0) (nth bl 3)) (* (nth al 1) (nth bl 2))
               (* (nth al 2) (nth bl 1)) (* (nth al 3) (nth bl 0)))
        c0 p0
        l0 (mod c0 65536)
        c1 (+ p1* (quot c0 65536))
        l1 (mod c1 65536)
        c2 (+ p2* (quot c1 65536))
        l2 (mod c2 65536)
        c3 (+ p3* (quot c2 65536))
        l3 (mod c3 65536)]
    [(+ (* l3 65536) l2) (+ (* l1 65536) l0)]))

(defn- shl32 [x n] (mod (* x (nth pow2 n)) 4294967296))

(defn- rotl [[hi lo] n]
  (let [n (mod n 64)]
    (cond
      (zero? n) [hi lo]
      (= n 32)  [lo hi]
      (< n 32)  [(u32 (bit-or (shl32 hi n) (unsigned-bit-shift-right lo (- 32 n))))
                 (u32 (bit-or (shl32 lo n) (unsigned-bit-shift-right hi (- 32 n))))]
      :else     (recur [lo hi] (- n 32)))))

(defn- shr [[hi lo] n]
  (cond
    (zero? n) [hi lo]
    (< n 32)  [(unsigned-bit-shift-right hi n)
               (u32 (bit-or (unsigned-bit-shift-right lo n) (shl32 hi (- 32 n))))]
    (= n 32)  [0 hi]
    :else     [0 (unsigned-bit-shift-right hi (- n 32))]))

(defn- rd64 [v i]
  ;; little-endian
  [(+ (nth v (+ i 4)) (* 256 (nth v (+ i 5)))
      (* 65536 (nth v (+ i 6))) (* 16777216 (nth v (+ i 7))))
   (+ (nth v i) (* 256 (nth v (+ i 1)))
      (* 65536 (nth v (+ i 2))) (* 16777216 (nth v (+ i 3))))])

(defn- rd32 [v i]
  [0 (+ (nth v i) (* 256 (nth v (+ i 1)))
        (* 65536 (nth v (+ i 2))) (* 16777216 (nth v (+ i 3))))])

(defn- round [acc input]
  (mul (rotl (add acc (mul input p2)) 31) p1))

(defn- merge-round [acc val]
  (let [val (round [0 0] val)]
    (add (mul (xor* acc val) p1) p4)))

(defn xxh64
  "XXH64 of `data` → `[hi lo]`."
  ([data] (xxh64 data [0 0]))
  ([data seed]
   (let [v   (vec data)
         n   (count v)
         h   (if (>= n 32)
               (let [[v1 v2 v3 v4]
                     (loop [i 0
                            v1 (add (add seed p1) p2)
                            v2 (add seed p2)
                            v3 seed
                            v4 (sub seed p1)]
                       (if (> (+ i 32) n)
                         [v1 v2 v3 v4]
                         (recur (+ i 32)
                                (round v1 (rd64 v i))
                                (round v2 (rd64 v (+ i 8)))
                                (round v3 (rd64 v (+ i 16)))
                                (round v4 (rd64 v (+ i 24))))))
                     h (add (add (rotl v1 1) (rotl v2 7))
                            (add (rotl v3 12) (rotl v4 18)))]
                 (-> h (merge-round v1) (merge-round v2)
                     (merge-round v3) (merge-round v4)))
               (add seed p5))
         h   (add h [0 (mod n 4294967296)])
         tail-start (* 32 (quot n 32))
         ;; 8-byte, then 4-byte, then single-byte tails
         [h i] (loop [h h i tail-start]
                 (if (<= (+ i 8) n)
                   (recur (add (mul (rotl (xor* h (round [0 0] (rd64 v i))) 27) p1) p4)
                          (+ i 8))
                   [h i]))
         [h i] (if (<= (+ i 4) n)
                 [(add (mul (rotl (xor* h (mul (rd32 v i) p1)) 23) p2) p3) (+ i 4)]
                 [h i])
         h     (loop [h h i i]
                 (if (>= i n)
                   h
                   (recur (mul (rotl (xor* h (mul [0 (nth v i)] p5)) 11) p1) (inc i))))
         ;; avalanche
         h (xor* h (shr h 33))
         h (mul h p2)
         h (xor* h (shr h 29))
         h (mul h p3)
         h (xor* h (shr h 32))]
     h)))

(defn xxh64-low32
  "The low 32 bits, which is what a zstd frame stores."
  [data]
  (nth (xxh64 data) 1))
