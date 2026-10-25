(ns lorawan.crypt
  "LoRaWAN L2 1.0.4 §4.3.3 \"MAC frame payload encryption (FRMPayload)\" and
  §6.2.6's Join-Accept encryption, both built on `aes.core/encrypt-block`
  from `kotoba-lang/org-nist-aes` — no second cipher.

  ## FRMPayload: an AES-CTR-shaped keystream, not AES-CBC/ECB

  §4.3.3, verbatim: for `k = ceil(len(pld) / 16)`, build blocks `A_1..A_k`
  (Table 12), encrypt each independently with the forward cipher —
  `S_i = aes128_encrypt(K, A_i)` — concatenate into a keystream `S`, then

      FRMPayloadPad = (pld | pad16) xor S
      FRMPayload    = FRMPayloadPad[0..len(pld)-1]

  This is a per-block counter keystream XORed with the plaintext — the
  same shape as CTR mode, not ECB/CBC — which is *why* encryption and
  decryption are the **same operation**: XOR is its own inverse, and the
  keystream never depends on the plaintext or ciphertext, only on
  `(Dir, DevAddr, FCnt, i)`. `crypt-frm-payload` below is not two
  functions wearing one name; there is only one operation.

  ## Join-Accept: the one place this library needs the AES *inverse* cipher

  §6.2.6, verbatim: \"The Join-Accept frame itself SHALL be encrypted with
  the AppKey as follows: `aes128_decrypt(AppKey, JoinNonce | NetID |
  DevAddr | DLSettings | RXDelay | CFList | MIC)`\" — ECB, ciphering each
  16-byte block independently, no chaining (confirmed by the spec's own
  note: \"An AES decrypt operation in ECB mode encrypts the Join-Accept
  frame so that the end-device can use an AES *encrypt* operation to
  decrypt the frame. This way, an end-device has to implement only AES
  encrypt but not AES decrypt.\")

  That note describes exactly the gap this library has: `org-nist-aes`
  ships only the forward cipher, for the reason its own README gives (GCM/
  CTR/CMAC — and now LoRaWAN's FRMPayload/MIC — never need the inverse).
  An end-device's role — **decoding** a received Join-Accept — needs only
  `aes128_encrypt`, so `decrypt-join-accept` below is fully implemented
  and reuses `org-nist-aes` exactly as-is. A join server's role —
  **encoding** one — needs the true AES-128 inverse cipher (InvSubBytes,
  InvShiftRows, InvMixColumns, the key schedule read backwards), which
  neither `org-nist-aes` nor this library implements. `encrypt-join-accept`
  does not exist here. That is a real, bounded gap in the join-server
  direction only — not a hidden one, and not one this codec's own test
  suite needs to close, since the round-trip and negative tests exercise
  the decode side against a payload encrypted independently (see the
  `:oracle` alias, matching `org-nist-aes`'s own JDK-`javax.crypto`
  oracle-test pattern)."
  (:require [aes.core]
            [lorawan.bytes :as b]))

(defn- ai-block [dir dev-addr fcnt32 i]
  (-> [0x01] (into (repeat 4 0)) (conj dir)
      (into (b/le-n dev-addr 4)) (into (b/le-n fcnt32 4))
      (conj 0) (conj (bit-and i 0xFF))))

(defn crypt-frm-payload
  "Encrypts (or, identically, decrypts) `pld` under `key` — see the
  namespace docstring for why this one function is both directions.
  `dir` is `lorawan.mic/dir-uplink` or `dir-downlink`, `fcnt32` the full
  32-bit frame counter (see `lorawan.mic`'s docstring on why not the
  16-bit wire `FCnt`)."
  [key dir dev-addr fcnt32 pld]
  (let [sched (aes.core/expand-key key)]
    (if (= :error (:status sched))
      sched
      (let [pld (vec pld)
            k (max 1 (quot (+ (count pld) 15) 16))
            keystream (vec (mapcat #(aes.core/encrypt-block sched (ai-block dir dev-addr fcnt32 (inc %)))
                                    (range k)))]
        {:status :ok :bytes (subvec (b/xor-bytes (b/zero-pad pld (count keystream)) keystream) 0 (count pld))}))))

;; ── Join-Accept decode-side decryption ──────────────────────────────────────

(defn decrypt-join-accept
  "`ciphertext` is the Join-Accept body as received on the wire —
  `JoinNonce | NetID | DevAddr | DLSettings | RXDelay | CFList | MIC`,
  16 or 32 bytes (§6.2.6: 16 without `CFList`, 32 with). ECB: each 16-byte
  block goes through `aes128_encrypt(AppKey, block)` independently, no
  chaining, no IV — the recovered plaintext is that same field layout.
  `:lorawan/bad-join-accept-length` if `ciphertext` is not a whole number
  of 16-byte blocks."
  [app-key ciphertext]
  (let [ciphertext (vec ciphertext)]
    (if (or (zero? (count ciphertext)) (not (zero? (mod (count ciphertext) 16))))
      {:status :error :reason :lorawan/bad-join-accept-length :length (count ciphertext)}
      (let [sched (aes.core/expand-key app-key)]
        (if (= :error (:status sched))
          sched
          {:status :ok
           :bytes (vec (mapcat #(aes.core/encrypt-block sched %) (partition 16 ciphertext)))})))))
