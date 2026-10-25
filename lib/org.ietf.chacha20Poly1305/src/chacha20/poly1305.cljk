(ns chacha20.poly1305
  "[RFC 8439](https://www.rfc-editor.org/rfc/rfc8439) §2.5 Poly1305, in
  portable `.cljc`.

  ## The arithmetic, and why these limbs

  Poly1305 works modulo 2^130 - 5, which neither runtime has a type for. The
  usual implementation (poly1305-donna) uses five 26-bit limbs and 64-bit
  intermediates — correct on the JVM and **not exact under ClojureScript**,
  where the products reach about 2^56 and a JavaScript number stops being an
  exact integer at 2^53.

  So the limbs here are **thirteen of ten bits**, which is 130 exactly. A
  product of two limbs is under 2^20, a column sum of thirteen under 2^24,
  and the fold that follows multiplies by five — nothing approaches 2^53 or
  2^63. The modulus falling on a limb boundary is also what makes the
  reduction a single multiply-by-five rather than a shift-and-mask across a
  limb.

  ## What this is not

  Not constant-time. The final conditional reduction selects on a borrow, and
  timing is a property of machine code that no portable Clojure controls. See
  `chacha20.aead`, which says the same where a caller reads it."
  (:refer-clojure :exclude [key]))

(def limbs 13)
(def ^:private limb-mask 1023)

;; 2^130 - 5 in these limbs: 1024 - 5 in the low limb, all ones above.
(def ^:private p-limbs (into [1019] (repeat 12 1023)))

(defn- bit-of [bs p]
  (let [i (quot p 8)]
    (if (>= i (count bs))
      0
      (bit-and (unsigned-bit-shift-right (nth bs i) (rem p 8)) 1))))

(defn- bytes->limbs
  "Little-endian bytes to thirteen 10-bit limbs. Bytes past the end read as
  zero, so a short final block needs no padding of its own."
  [bs]
  (mapv (fn [i]
          (reduce (fn [acc j]
                    (bit-or acc (bit-shift-left (bit-of bs (+ (* 10 i) j)) j)))
                  0 (range 10)))
        (range limbs)))

(defn- limbs->bytes [l n]
  (mapv (fn [k]
          (reduce (fn [acc j]
                    (let [p (+ (* 8 k) j)
                          li (quot p 10)
                          lb (rem p 10)]
                      (bit-or acc (bit-shift-left
                                   (bit-and (unsigned-bit-shift-right (nth l li 0) lb) 1)
                                   j))))
                  0 (range 8)))
        (range n)))

(defn- carry [h]
  (loop [h h i 0 c 0 passes 0]
    (cond
      (> passes 4) h                       ; cannot happen; a floor, not a fix
      (= i limbs) (if (zero? c)
                    h
                    ;; A carry out of limb 12 has weight 2^130, and 2^130 = 5
                    ;; in this field, so it re-enters at limb 0 times five.
                    (recur (update h 0 + (* 5 c)) 0 0 (inc passes)))
      :else (let [v (+ (nth h i) c)]
              (recur (assoc h i (bit-and v limb-mask)) (inc i) (quot v 1024) passes)))))

(defn- carry-plain
  "Propagate carries WITHOUT the modular wrap.

  The final `h + s` of §2.5.1 is ordinary addition truncated to 128 bits, not
  addition in the field. Folding a carry out of bit 130 back in as five --
  which is correct everywhere else in this file -- makes the tag exactly five
  too large whenever the sum crosses 2^130.

  `s` is uniform below 2^128 and `h` is below 2^130, so that happens for
  roughly one message in eight. It did not show up against the RFC's own
  vector, and it did not show up in the AEAD suite at all, because the AEAD's
  Poly1305 input is always padded to a multiple of sixteen bytes and those
  particular inputs happened not to cross. It took a differential run over a
  spread of message lengths to see it."
  [h]
  (loop [h h i 0 c 0]
    (if (= i limbs)
      h                     ; anything above bit 130 is outside the 128 we keep
      (let [v (+ (nth h i) c)]
        (recur (assoc h i (bit-and v limb-mask)) (inc i) (quot v 1024))))))

(defn- add-limbs [a b]
  (carry (mapv + a b)))

(defn- mul-mod [a b]
  (let [t (reduce (fn [t i]
                    (reduce (fn [t j] (update t (+ i j) + (* (nth a i) (nth b j))))
                            t (range limbs)))
                  (vec (repeat 25 0))
                  (range limbs))
        ;; Limb 13+i has weight 2^(130 + 10i), which is 5 * 2^(10i).
        t (reduce (fn [t i] (update t i + (* 5 (nth t (+ i limbs))))) t (range 12))]
    (carry (vec (take limbs t)))))

(defn- final-reduce
  "Subtract the modulus once if the accumulator is at least the modulus.

  Carrying leaves a value below 2^130, and the modulus is 2^130 - 5, so one
  conditional subtraction is enough — but it is not optional: without it two
  accumulators differing by exactly the modulus produce different tags."
  [h]
  (let [[g borrow]
        (loop [g [] i 0 borrow 0]
          (if (= i limbs)
            [g borrow]
            (let [v (- (nth h i) (nth p-limbs i) borrow)]
              (recur (conj g (bit-and v limb-mask)) (inc i) (if (neg? v) 1 0)))))]
    (if (zero? borrow) g h)))

(defn clamp
  "RFC 8439 §2.5: r has 22 bits cleared before use.

  The clamping is what bounds the intermediate products; an implementation
  that skips it is not slower or weaker, it computes a different function."
  [r]
  (let [r (vec r)]
    (-> r
        (assoc 3 (bit-and (nth r 3) 15))
        (assoc 7 (bit-and (nth r 7) 15))
        (assoc 11 (bit-and (nth r 11) 15))
        (assoc 15 (bit-and (nth r 15) 15))
        (assoc 4 (bit-and (nth r 4) 252))
        (assoc 8 (bit-and (nth r 8) 252))
        (assoc 12 (bit-and (nth r 12) 252)))))

(defn mac
  "The 16-byte tag of `msg` under a 32-byte one-time `k`.

  Returns `{:status :ok :tag […]}` or `{:status :error :reason kw}`. The key
  is one-time by construction of the AEAD above it: reusing it across two
  messages reveals `r` and forgery becomes arithmetic."
  [k msg]
  (let [k (vec k) msg (vec msg)]
    (if (not= 32 (count k))
      {:status :error :reason :bad-key-length :length (count k)}
      (let [r (bytes->limbs (clamp (subvec k 0 16)))
            s (bytes->limbs (subvec k 16 32))
            n (count msg)
            h (loop [h (vec (repeat limbs 0)) off 0]
                (if (>= off n)
                  h
                  (let [end (min n (+ off 16))
                        ;; The trailing 0x01 is the bit that makes the block a
                        ;; number one longer than its bytes, and it goes after
                        ;; the block's own length -- not at byte 16 -- so a
                        ;; short final block is distinguishable from a padded
                        ;; full one.
                        blk (conj (subvec msg off end) 1)]
                    (recur (mul-mod (add-limbs h (bytes->limbs blk)) r) (+ off 16)))))]
        {:status :ok :tag (limbs->bytes (carry-plain (mapv + (final-reduce h) s)) 16)}))))

(defn mac!
  [k msg]
  (let [r (mac k msg)]
    (if (= :ok (:status r))
      (:tag r)
      (throw (ex-info (str "poly1305: " (name (:reason r))) r)))))
