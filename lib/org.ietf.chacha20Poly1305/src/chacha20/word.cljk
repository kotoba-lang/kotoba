(ns chacha20.word
  "32-bit words, on two runtimes that disagree about what a bitwise operator
  returns.

  ChaCha20 is defined over 32-bit unsigned words with wrapping addition,
  exclusive-or, and rotation. The JVM has 64-bit longs, so a sum can exceed
  32 bits and a shift does not truncate. JavaScript's operators truncate to
  32 bits and return a SIGNED result. Neither is the unsigned 32-bit word the
  specification describes, so every operation here ends in `u32`."
  (:refer-clojure :exclude [+]))

(defn u32
  "Reduce to 0..2^32-1. A mask on the JVM; `x >>> 0` under ClojureScript,
  whose ToUint32 coercion takes the value mod 2^32."
  [x]
  #?(:clj (bit-and x 0xFFFFFFFF)
     :cljs (unsigned-bit-shift-right x 0)))

(defn add [a b] (u32 (clojure.core/+ a b)))
(defn xor [a b] (u32 (bit-xor a b)))

(defn rotl
  "Rotate left by `n`, 0 < n < 32.

  The shift counts stay in 1..31 on purpose. ClojureScript takes a shift
  count mod 32, so `<< 32` is silently `<< 0` -- ChaCha20 never asks for 32,
  but writing the guard as a range rather than trusting the inputs is what
  keeps that true when someone adds a variant."
  [x n]
  (u32 (bit-or (bit-shift-left x n) (unsigned-bit-shift-right (u32 x) (clojure.core/- 32 n)))))

(defn le32
  "Four little-endian bytes at `off` as a word."
  [bs off]
  (clojure.core/+ (nth bs off)
                  (clojure.core/* 256 (nth bs (clojure.core/+ off 1)))
                  (clojure.core/* 65536 (nth bs (clojure.core/+ off 2)))
                  (clojure.core/* 16777216 (nth bs (clojure.core/+ off 3)))))

(defn word->le
  "A word as four little-endian bytes."
  [w]
  [(bit-and w 0xFF)
   (bit-and (quot w 256) 0xFF)
   (bit-and (quot w 65536) 0xFF)
   (bit-and (quot w 16777216) 0xFF)])

(defn le64
  "A non-negative integer below 2^53 as eight little-endian bytes. Used for
  the two lengths in the AEAD's Poly1305 input."
  [n]
  (into (word->le (u32 n)) (word->le (u32 (quot n 4294967296)))))
