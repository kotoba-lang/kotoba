(ns lorawan.cmac
  "AES-CMAC — RFC 4493 — built on `aes.core/encrypt-block` from
  `kotoba-lang/org-nist-aes`, not a fresh cipher. LoRaWAN L2 1.0.4 §4.4
  names this exact construction for its message integrity code:

      CMAC = aes128_cmac(NwkSKey, B0 | msg)
      MIC  = CMAC[0..3]

  CMAC needs only the AES-128 *forward* cipher — one block encryption to
  derive the two subkeys, and one more per 16-byte message block — so this
  namespace adds nothing to `aes.core`'s scope, per its own README (\"no
  decryption here ... GCM, CTR and CCM never invoke the inverse cipher\").
  Every LoRaWAN MIC (data frame, Join-Request, Join-Accept) is CMAC of a
  different framing prefix over the forward cipher; only that prefix
  differs, never this algorithm.

  Verified against RFC 4493 §4's own worked examples — key
  `2b7e151628aed2a6abf7158809cf4f3c`, four messages of 0/16/40/64 bytes —
  fetched from rfc-editor.org 2026-08-30, not recalled from memory."
  (:require [aes.core]))

(defn- xor-bytes [a b] (mapv bit-xor a b))

(def ^:private Rb
  "RFC 4493 §2.3: the constant XORed in when the top bit of a left-shift
  falls off the end — R_128 = 0^120 10000111, i.e. 0x87 in the last byte."
  (assoc (vec (repeat 16 0)) 15 0x87))

(defn- left-shift-1
  "The 128-bit value `bs` shifted left by one bit, as 16 bytes. Every
  per-byte op stays inside 0..255 (`bit-shift-left`/`bit-and`/`bit-or` on a
  single byte, plus a 1-bit carry pulled from the next byte's top bit), so
  this needs none of `amqp.types`'s multi-byte-safety machinery — a CMAC
  block is 16 *bytes*, never combined into one JS number."
  [bs]
  (vec (for [i (range 16)]
         (let [carry (if (< (inc i) 16) (bit-and (unsigned-bit-shift-right (nth bs (inc i)) 7) 1) 0)]
           (bit-and 0xFF (bit-or (bit-shift-left (nth bs i) 1) carry))))))

(defn- msb-set? [bs] (= 1 (bit-and (unsigned-bit-shift-right (nth bs 0) 7) 1)))

(defn subkeys
  "RFC 4493 §2.3. `L = AES(K, 0^128)`; `K1`/`K2` are `L` doubled once/twice
  in GF(2^128), XORing `Rb` whenever the shift-out bit was 1 — the same
  \"double, conditionally XOR a fixed constant\" shape as `org-nist-aes`'s
  own GF(2^8) `xtime`, one dimension up."
  [key-schedule]
  (let [l (aes.core/encrypt-block key-schedule (vec (repeat 16 0)))
        k1 (if (msb-set? l) (xor-bytes (left-shift-1 l) Rb) (left-shift-1 l))
        k2 (if (msb-set? k1) (xor-bytes (left-shift-1 k1) Rb) (left-shift-1 k1))]
    {:k1 k1 :k2 k2}))

(defn- pad-block
  "RFC 4493 §2.4: append a single `0x80` then zeros out to 16 bytes. Used
  only for the final block when the message length is *not* a multiple of
  16 — the whole reason CMAC needs two different subkeys is to keep an
  exact-multiple-of-16 message and a padded one from ever colliding."
  [bs]
  (into (vec bs) (into [0x80] (repeat (- 15 (count bs)) 0))))

(defn cmac
  "AES-128-CMAC of `msg` (a byte sequence of any length, including zero)
  under `key` (16 bytes). Returns the full 16-byte MAC — callers wanting a
  LoRaWAN MIC take `(subvec (cmac key msg) 0 4)` themselves, since \"first
  four bytes of a CMAC\" is a LoRaWAN framing choice, not part of CMAC
  itself."
  [key msg]
  (let [sched (aes.core/expand-key key)]
    (if (= :error (:status sched))
      sched
      (let [{:keys [k1 k2]} (subkeys sched)
            msg (vec msg)
            ;; Ceiling division without `Math/ceil` (JVM-only) or a float —
            ;; `quot (n+15) 16` is exact integer arithmetic, portable, and
            ;; n=0 correctly maps to 1 block (CMAC of the empty message is
            ;; still one padded block).
            n-blocks (max 1 (quot (+ (count msg) 15) 16))
            complete? (and (pos? (count msg)) (zero? (mod (count msg) 16)))
            last-block (subvec msg (* 16 (dec n-blocks)) (count msg))
            m-last (if complete? (xor-bytes last-block k1) (xor-bytes (pad-block last-block) k2))]
        {:status :ok
         :mac (loop [i 0 x (vec (repeat 16 0))]
                (if (= i (dec n-blocks))
                  (aes.core/encrypt-block sched (xor-bytes m-last x))
                  (recur (inc i)
                         (aes.core/encrypt-block sched (xor-bytes (subvec msg (* 16 i) (* 16 (inc i))) x)))))}))))
