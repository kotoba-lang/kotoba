(ns torihiki.keccak
  "Keccak-256, the hash Ethereum addresses storage with.

  `torihiki.evm.interp` needs it and stopped short of it deliberately: Solidity
  computes a mapping slot by hashing the key with the slot number, so a
  contract that uses a mapping cannot run without one. Approximating it is not
  an option — a hash that is not keccak gives a different slot for the same
  key, and the contract would read and write real storage at addresses no
  other implementation agrees with. Wrong quietly, and only for the contracts
  that hold the most.

  ## 32-bit halves, not big integers

  A Keccak lane is 64 bits. JavaScript has no 64-bit integer except BigInt,
  and BigInt arithmetic in this namespace would be both slow and — as this
  session has now measured twice — the place where the two runtimes stop
  agreeing. So a lane is a PAIR of 32-bit values and every operation is
  `bit-and`, `bit-xor` and the shifts, masked to 32 bits.

  Those are exact on both sides: ClojureScript's bit operations are 32-bit by
  definition, and masking a JVM long to `0xFFFFFFFF` makes it the same number.
  There is no arithmetic here at all, which is the point — nothing to coerce.

  Not the sponge in general and not SHA3: Keccak-256 with the original
  padding, which is what Ethereum uses and what `keccak256` in Solidity means."
  (:require [kotoba.lang.text :as str]))

(def ^:private ^:const m32 0xFFFFFFFF)

;; No type hint: `^long` on a `.cljc` fn is a JVM class hint that
;; ClojureScript has no meaning for, and it made the JVM reader fail here too.
(defn- u32 [x] (bit-and x m32))

(defn- rotl
  "Rotate a 64-bit lane, given as `[hi lo]`, left by `n`.

  Two cases and they are not symmetric: below 32 the halves shift into each
  other, at or above 32 they swap first. Writing one branch and hoping is how
  a hash comes out plausible and wrong."
  [[hi lo] n]
  (let [n (mod n 64)]
    (cond
      (zero? n) [hi lo]
      (< n 32) [(u32 (bit-or (bit-shift-left hi n) (unsigned-bit-shift-right lo (- 32 n))))
                (u32 (bit-or (bit-shift-left lo n) (unsigned-bit-shift-right hi (- 32 n))))]
      (= n 32) [lo hi]
      :else (let [n (- n 32)]
              [(u32 (bit-or (bit-shift-left lo n) (unsigned-bit-shift-right hi (- 32 n))))
               (u32 (bit-or (bit-shift-left hi n) (unsigned-bit-shift-right lo (- 32 n))))]))))

(defn- x2 [[ah al] [bh bl]] [(bit-xor ah bh) (bit-xor al bl)])

(def ^:private rho-offsets
  [0 1 62 28 27 36 44 6 55 20 3 10 43 25 39 41 45 15 21 8 18 2 61 56 14])

(def ^:private pi-index
  ;; Where lane i comes FROM. Precomputed rather than derived in the loop: the
  ;; derivation is two modular multiplications and getting it subtly wrong
  ;; produces a permutation that still looks like a hash.
  [0 6 12 18 24 3 9 10 16 22 1 7 13 19 20 4 5 11 17 23 2 8 14 15 21])

(def ^:private round-constants
  ;; `[hi lo]` per round, the standard 24.
  [[0x00000000 0x00000001] [0x00000000 0x00008082] [0x80000000 0x0000808a]
   [0x80000000 0x80008000] [0x00000000 0x0000808b] [0x00000000 0x80000001]
   [0x80000000 0x80008081] [0x80000000 0x00008009] [0x00000000 0x0000008a]
   [0x00000000 0x00000088] [0x00000000 0x80008009] [0x00000000 0x8000000a]
   [0x00000000 0x8000808b] [0x80000000 0x0000008b] [0x80000000 0x00008089]
   [0x80000000 0x00008003] [0x80000000 0x00008002] [0x80000000 0x00000080]
   [0x00000000 0x0000800a] [0x80000000 0x8000000a] [0x80000000 0x80008081]
   [0x80000000 0x00008080] [0x00000000 0x80000001] [0x80000000 0x80008008]])

(defn- keccak-f
  "The permutation, 24 rounds over 25 lanes."
  [state]
  (reduce
   (fn [s rc]
     (let [;; theta
           c (vec (for [x (range 5)]
                    (reduce x2 (for [y (range 5)] (nth s (+ x (* 5 y)))))))
           d (vec (for [x (range 5)]
                    (x2 (nth c (mod (+ x 4) 5))
                        (rotl (nth c (mod (inc x) 5)) 1))))
           s (vec (for [i (range 25)] (x2 (nth s i) (nth d (mod i 5)))))
           ;; rho and pi together: lane i of the new state is lane
           ;; `pi-index[i]` of the old, rotated by its own offset.
           s (vec (for [i (range 25)]
                    (rotl (nth s (nth pi-index i)) (nth rho-offsets (nth pi-index i)))))
           ;; chi, row by row
           s (vec (apply concat
                         (for [y (range 5)]
                           (let [row (subvec s (* 5 y) (+ 5 (* 5 y)))]
                             (for [x (range 5)]
                               (let [[ah al] (nth row x)
                                     [bh bl] (nth row (mod (inc x) 5))
                                     [ch cl] (nth row (mod (+ x 2) 5))]
                                 [(bit-xor ah (bit-and (u32 (bit-not bh)) ch))
                                  (bit-xor al (bit-and (u32 (bit-not bl)) cl))]))))))]
       ;; iota
       (assoc s 0 (x2 (nth s 0) rc))))
   state
   round-constants))

(def ^:private ^:const rate-bytes
  "136. Keccak-256's rate — 1088 bits of the 1600-bit state absorbed per
  block, the rest being the capacity that gives it its security."
  136)

(defn- absorb-block [state bytes]
  (keccak-f
   (reduce (fn [s i]
             (let [off (* 8 i)
                   lo (reduce (fn [a k] (bit-or a (bit-shift-left (nth bytes (+ off k)) (* 8 k))))
                              0 (range 4))
                   hi (reduce (fn [a k] (bit-or a (bit-shift-left (nth bytes (+ off 4 k)) (* 8 k))))
                              0 (range 4))]
               (assoc s i (x2 (nth s i) [(u32 hi) (u32 lo)]))))
           state
           (range (quot rate-bytes 8)))))

(defn- pad
  "The ORIGINAL Keccak padding — `0x01` then zeros then `0x80`.

  Not SHA-3's `0x06`. They differ in one byte and produce entirely different
  digests, and Ethereum uses this one; a `keccak256` that quietly computed
  SHA3-256 would agree with nothing on any chain."
  [bytes]
  (let [n (count bytes)
        pad-len (- rate-bytes (mod n rate-bytes))
        tail (vec (concat [0x01] (repeat (- pad-len 2) 0) [0x80]))]
    (vec (concat bytes (if (= 1 pad-len) [0x81] tail)))))

(defn- hex-byte [b]
  (let [h #?(:clj (Integer/toHexString b) :cljs (.toString b 16))]
    (if (= 1 (count h)) (str "0" h) h)))

(defn digest-bytes
  "Keccak-256 of a byte sequence, as a vector of 32 byte values."
  [bytes]
  (let [padded (pad (vec bytes))
        blocks (partition rate-bytes padded)
        final (reduce absorb-block (vec (repeat 25 [0 0])) (map vec blocks))]
    ;; Squeeze: the first 32 bytes, little-endian within each lane.
    (vec (for [i (range 32)]
           (let [[hi lo] (nth final (quot i 8))
                 k (mod i 8)
                 word (if (< k 4) lo hi)
                 shift (* 8 (mod k 4))]
             (bit-and (unsigned-bit-shift-right word shift) 0xFF))))))

(defn digest-hex
  "Keccak-256 as 64 hex characters, no `0x`."
  [bytes]
  (apply str (map hex-byte (digest-bytes bytes))))

(defn bytes->hex
  "Byte values to hex, no `0x`. The inverse of `hex->bytes`, and here so that
  callers do not each write their own zero-padding."
  [bytes]
  (apply str (map hex-byte bytes)))

(defn hex->bytes [s]
  (let [s (str/replace s #"^0x" "")]
    (vec (for [i (range (quot (count s) 2))]
           #?(:clj (Integer/parseInt (subs s (* 2 i) (+ 2 (* 2 i))) 16)
              :cljs (js/parseInt (subs s (* 2 i) (+ 2 (* 2 i))) 16))))))

(defn digest-of-hex
  "Keccak-256 of hex-encoded input, as hex. What a contract's calldata and a
  storage slot are both spelled in."
  [hex]
  (digest-hex (hex->bytes hex)))

(defn create2-address
  "Where CREATE2 puts code: the low 20 bytes of
  `keccak256(0xff ++ sender ++ salt ++ keccak256(code))`.

  Here rather than in the interpreter because the chain computes it too — a
  deploy transaction and the opcode have to land in the same place or a
  contract is at one address for the node and another for the consensus."
  [sender salt-hex code-hex]
  (str "0x" (subs (digest-of-hex (str "ff" (str/replace sender #"^0x" "")
                                      salt-hex (digest-of-hex code-hex)))
                  24)))
