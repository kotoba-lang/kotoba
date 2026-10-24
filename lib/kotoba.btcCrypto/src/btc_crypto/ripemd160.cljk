(ns btc-crypto.ripemd160
  "Pure RIPEMD-160 (Dobbertin/Bosselaers/Preneel, 1996). The JDK ships no
  provider for it (BouncyCastle-only), so — matching eth-crypto's Keccak-256
  self-contained style — this is a from-spec .cljc implementation: 5 rounds x
  16 steps, two parallel lines (left/right) that merge into the chaining
  value each 512-bit block. Verified against the reference test vectors
  (empty string, \"abc\", \"message digest\", the alphabet) — see
  test/btc_crypto/ripemd160_test.cljc.

  PORTABILITY: :clj-only (wrapped #?(:clj (do ...)) with a throwing :cljs
  stub of the same name, matching eth-crypto.core's precedent) — the bit
  math itself (bit-and/bit-or/bit-xor/bit-shift-left/
  unsigned-bit-shift-right) is already 32-bit-correct on cljs, but the
  byte-array/aget/aset-byte/System.arraycopy plumbing around it is
  JVM-only; porting that too is out of scope for this pass.")

#?(:clj
(do

(def ^:private MASK 0xFFFFFFFF)

(defn- mask32 ^long [^long x] (bit-and x MASK))

(defn- rotl32 ^long [^long x ^long n]
  (mask32 (bit-or (bit-shift-left x n) (unsigned-bit-shift-right (mask32 x) (- 32 n)))))

;; message-word selection order per step j=0..79 (left line / right line)
(def ^:private R
  [0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 7 4 13 1 10 6 15 3 12 0 9 5 2 14 11 8 3 10 14 4 9 15 8 1 2 7 0 6 13 11 5 12 1 9 11 10 0 8 12 4 13 3 7 15 14 5 6 2 4 0 5 9 7 12 2 10 14 1 3 8 11 6 15 13])
(def ^:private R'
  [5 14 7 0 9 2 11 4 13 6 15 8 1 10 3 12 6 11 3 7 0 13 5 10 14 15 8 12 4 9 1 2 15 5 1 3 7 14 6 9 11 8 12 2 10 0 4 13 8 6 4 1 3 11 15 0 5 12 2 13 9 7 10 14 12 15 10 4 1 5 8 7 6 2 13 14 0 3 9 11])
;; rotate-left amounts per step (left line / right line)
(def ^:private S
  [11 14 15 12 5 8 7 9 11 13 14 15 6 7 9 8 7 6 8 13 11 9 7 15 7 12 15 9 11 7 13 12 11 13 6 7 14 9 13 15 14 8 13 6 5 12 7 5 11 12 14 15 14 15 9 8 9 14 5 6 8 6 5 12 9 15 5 11 6 8 13 12 5 12 13 14 11 8 5 6])
(def ^:private S'
  [8 9 9 11 13 15 15 5 7 7 8 11 14 14 12 6 9 13 15 7 12 8 9 11 7 7 12 7 6 15 13 11 9 7 15 11 8 6 6 14 12 13 5 14 13 13 7 5 15 5 8 11 14 14 6 14 6 9 12 9 12 5 15 8 8 5 12 9 12 5 14 6 8 13 6 5 15 13 11 11])
;; per-round additive constants (round = step div 16)
(def ^:private K [0x00000000 0x5A827999 0x6ED9EBA1 0x8F1BBCDC 0xA953FD4E])
(def ^:private K' [0x50A28BE6 0x5C4DD124 0x6D703EF3 0x7A6D76E9 0x00000000])

;; boolean fns per round: left line rounds 0..4 use f0..f4; right line step j
;; uses f(79-j) — i.e. the round order f4,f3,f2,f1,f0, the standard RIPEMD-160
;; "mirrored" schedule.
(defn- bool-f ^long [^long round ^long x ^long y ^long z]
  (case (int round)
    0 (mask32 (bit-xor x y z))
    1 (mask32 (bit-or (bit-and x y) (bit-and (bit-not x) z)))
    2 (mask32 (bit-xor (bit-or x (bit-not y)) z))
    3 (mask32 (bit-or (bit-and x z) (bit-and y (bit-not z))))
    4 (mask32 (bit-xor x (bit-or y (bit-not z))))))

(defn- pad
  "MD-strengthening padding: 0x80, zeros, then 64-bit little-endian bit length."
  ^bytes [^bytes msg]
  (let [len (alength msg)
        bitlen (* 8 (long len))
        with-one (inc len)
        padded-len (long (* 64 (Math/ceil (/ (+ with-one 8) 64.0))))
        out (byte-array padded-len)]
    (System/arraycopy msg 0 out 0 len)
    (aset-byte out len (unchecked-byte 0x80))
    (dotimes [i 8]
      (aset-byte out (+ (- padded-len 8) i)
                 (unchecked-byte (unsigned-bit-shift-right bitlen (* 8 i)))))
    out))

(defn- word-le
  "Read a little-endian 32-bit word starting at byte offset `off`."
  ^long [^bytes b ^long off]
  (bit-or (bit-and (aget b off) 0xff)
          (bit-shift-left (bit-and (aget b (+ off 1)) 0xff) 8)
          (bit-shift-left (bit-and (aget b (+ off 2)) 0xff) 16)
          (bit-shift-left (bit-and (aget b (+ off 3)) 0xff) 24)))

(defn ripemd160
  "RIPEMD-160 of `input` (byte array). Returns a 20-byte digest."
  ^bytes [^bytes input]
  (let [msg (pad input)
        n-blocks (quot (alength msg) 64)]
    (loop [block 0 h0 0x67452301 h1 0xEFCDAB89 h2 0x98BADCFE h3 0x10325476 h4 0xC3D2E1F0]
      (if (= block n-blocks)
        (let [out (byte-array 20)]
          (doseq [[i h] (map-indexed vector [h0 h1 h2 h3 h4])]
            (dotimes [k 4]
              (aset-byte out (+ (* i 4) k) (unchecked-byte (unsigned-bit-shift-right h (* 8 k))))))
          out)
        (let [base (* block 64)
              X (mapv #(word-le msg (+ base (* 4 %))) (range 16))
              [A B C D E A' B' C' D' E']
              (loop [j 0 A h0 B h1 C h2 D h3 E h4 A' h0 B' h1 C' h2 D' h3 E' h4]
                (if (= j 80)
                  [A B C D E A' B' C' D' E']
                  (let [round (quot j 16)                    ; K/K' progress j=0..79 in normal round order
                        bool-round' (quot (- 79 j) 16)        ; right-line boolean fn is mirrored: f5,f4,f3,f2,f1
                        T (mask32 (+ (rotl32 (mask32 (+ A (bool-f round B C D) (nth X (nth R j)) (nth K round))) (nth S j)) E))
                        T' (mask32 (+ (rotl32 (mask32 (+ A' (bool-f bool-round' B' C' D') (nth X (nth R' j)) (nth K' round))) (nth S' j)) E'))]
                    (recur (inc j)
                           E T B (rotl32 C 10) D
                           E' T' B' (rotl32 C' 10) D'))))]
          (recur (inc block)
                 (mask32 (+ h1 C D'))
                 (mask32 (+ h2 D E'))
                 (mask32 (+ h3 E A'))
                 (mask32 (+ h4 A B'))
                 (mask32 (+ h0 B C'))))))))

) ;; end do
:cljs
(defn ripemd160 [& _]
  (throw (ex-info "btc-crypto.ripemd160/ripemd160 is :clj-only (JVM byte-array/System.arraycopy math)" {}))))
