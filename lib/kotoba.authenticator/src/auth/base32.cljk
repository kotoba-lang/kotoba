(ns auth.base32
  "RFC 4648 Base32 — the encoding TOTP/HOTP shared secrets are exchanged in
  (the string you read off a QR code's `secret=` field).

  Pure .cljc: bytes are represented as Clojure vectors of unsigned ints in
  [0,255], so no host byte-array type leaks across the JVM/Node boundary."
  (:require [kotoba.lang.text :as str]))

(def ^:private alphabet "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")

(def ^:private char->val
  (into {} (map-indexed (fn [i c] [c i]) alphabet)))

(defn decode
  "Decodes a Base32 string into a vector of unsigned bytes (ints 0–255).
  Lower-case input, padding `=` and whitespace are tolerated; any other
  out-of-alphabet character is skipped (authenticator apps often print the
  secret in spaced groups)."
  [s]
  (loop [cs  (seq (str/upper (str s)))
         buf 0      ; bit accumulator
         n   0      ; bits currently in buf
         out (transient [])]
    (if (empty? cs)
      (persistent! out)
      (let [v (char->val (first cs))]
        (if (nil? v)
          (recur (rest cs) buf n out)                ; skip '=', spaces, junk
          (let [buf (+ (* buf 32) v)
                n   (+ n 5)]
            (if (>= n 8)
              (let [n'   (- n 8)
                    byte (bit-and (quot buf (bit-shift-left 1 n')) 0xff)]
                (recur (rest cs)
                       (mod buf (bit-shift-left 1 n'))
                       n'
                       (conj! out byte)))
              (recur (rest cs) buf n out))))))))

(defn encode
  "Encodes a vector of unsigned bytes (ints 0–255) into an unpadded Base32
  string. Inverse of `decode` for whole-byte inputs."
  [bytes]
  (loop [bs  (seq bytes)
         buf 0      ; bit accumulator
         n   0      ; bits currently in buf
         out (transient [])]
    (cond
      ;; emit a full 5-bit group whenever we have one
      (>= n 5)
      (let [n' (- n 5)]
        (recur bs
               (mod buf (bit-shift-left 1 n'))
               n'
               (conj! out (bit-and (quot buf (bit-shift-left 1 n')) 0x1f))))
      ;; otherwise pull in the next byte (8 more bits)
      (seq bs)
      (recur (rest bs) (+ (* buf 256) (first bs)) (+ n 8) out)
      ;; trailing <5 bits: left-shift to a full group, zero-pad the right
      (pos? n)
      (recur nil (* buf (bit-shift-left 1 (- 5 n))) 5 out)
      :else
      (apply str (map #(nth alphabet %) (persistent! out))))))
