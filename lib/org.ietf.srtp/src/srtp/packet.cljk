(ns srtp.packet
  "The SRTP packet transform — [RFC 3711] §3.1/§4.1/§4.2 — turning a
  plaintext RTP packet (bytes, as `org-ietf-rtp`'s `rtp.header` encodes
  and decodes) into an SRTP packet (encrypted payload + optional MKI +
  authentication tag) and back.

  Figure 1's layout, this codec's actual output shape:

    RTP header | encrypted RTP payload (incl. RTP padding) | MKI? | auth tag?
    |-------- Encrypted Portion --------|
    |------------------- Authenticated Portion -------------------|

  and §4.2's own definition of what actually gets authenticated: `M =
  Authenticated Portion || ROC` — the 32-bit rollover counter is
  concatenated onto the end *before* HMAC, even though ROC itself never
  appears on the wire. Omitting it is a bug that a same-process
  round-trip test cannot catch (both sides would agree with each other
  and disagree with a real SRTP implementation), which is why the
  header-length helper below matters more than it looks.

  **Why the header/payload split cannot always go through
  `rtp.header/decode`**: on the *encrypt* side the input is real
  plaintext RTP, so `rtp.header/decode` is used directly — including its
  own correct RTP-padding stripping. On the *decrypt* side the payload
  bytes are still ciphertext at the point the header/payload boundary
  needs to be located, and RTP's padding-count trailer octet (if the P
  bit is set) is inside that still-encrypted region: decoding padding
  from garbage ciphertext is a use-after-free-shaped bug, not a
  hypothetical one, so `header-length` below computes only the *offset*
  (12 fixed bytes + 4 per CSRC + the extension block if X is set — RFC
  3550 §5.3.1's own extension-length field), never the padding count.
  Once `unprotect` has decrypted the payload, the caller gets back a
  plain RTP packet and can hand it to `rtp.header/decode` — which is
  exactly where RTP-padding interpretation belongs.")

(require '[rtp.header :as rtp]
         '[kotoba.bytes.sha1 :as sha1]
         '[srtp.aes-cm :as cm]
         '[srtp.index :as idx]
         '[aes.core :as aes])

(defn header-length
  "Byte offset where the RTP payload begins: `12 + 4*CC` for the fixed
  header and CSRC list, plus `4 + 4*extension-length` if the extension
  bit (X) is set — RFC 3550 §5.3.1: the extension block is a 16-bit
  profile-defined identifier, a 16-bit length (in 32-bit words, NOT
  counting its own 4-byte header), then that many words of data.
  Deliberately does not touch the padding bit or any payload byte, for
  the reason in this namespace's docstring."
  [bs]
  (let [byte0 (bit-and (nth bs 0) 0xFF)
        cc (bit-and byte0 0x0F)
        x? (bit-test byte0 4)
        base (+ 12 (* 4 cc))]
    (if x?
      (let [ext-len (bit-or (bit-shift-left (bit-and (nth bs (+ base 2)) 0xFF) 8)
                             (bit-and (nth bs (+ base 3)) 0xFF))]
        (+ base 4 (* 4 ext-len)))
      base)))

(defn- u32be [n]
  [(bit-and (unsigned-bit-shift-right n 24) 0xFF) (bit-and (unsigned-bit-shift-right n 16) 0xFF)
   (bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])

;; ── the AES-CM IV for one SRTP packet ────────────────────────────────────
;;
;; [RFC 3711] §4.1.1: `IV = (k_s * 2^16) XOR (SSRC * 2^64) XOR (i * 2^16)`.
;; Built as three explicit 16-byte terms and XORed, matching the RFC's
;; own three-term sum rather than one opaque bit-twiddling expression:
;;   - `k_s * 2^16`: the 14-byte cipher salt, padded to 16 bytes by
;;     appending two zero bytes (this is the same "left-shift-by-16"
;;     construction `srtp.kdf`'s key-derivation seed uses).
;;   - `SSRC * 2^64`: the 32-bit SSRC placed at byte offset 4..7 of the
;;     16-byte block (bits 64..95).
;;   - `i * 2^16`: the 48-bit packet index placed at byte offset 8..13
;;     (bits 16..63) — leaving the low two bytes as AES-CM's own
;;     per-block counter, which is why *this* term also ends in two
;;     zero bytes rather than the index's own low bits.

(defn- term-salt [cipher-salt] (into (vec cipher-salt) [0 0]))
(defn- term-ssrc [ssrc] (into [0 0 0 0] (into (u32be ssrc) [0 0 0 0 0 0 0 0])))
(defn- u48be [n] (vec (for [shift [40 32 24 16 8 0]] (bit-and (unsigned-bit-shift-right n shift) 0xFF))))
(defn- term-index [index] (into [0 0 0 0 0 0 0 0] (into (u48be index) [0 0])))

(defn compute-iv [cipher-salt ssrc index]
  (mapv bit-xor (term-salt cipher-salt) (term-ssrc ssrc) (term-index index)))

(def default-tag-length
  "80 bits / 10 bytes — [RFC 3711] §4.2.1/§8.2's `AES_CM_128_HMAC_SHA1_80`,
  the crypto suite this codec's `protect`/`unprotect` defaults implement."
  10)

(defn- auth-tag
  "HMAC-SHA1(auth-key, Authenticated-Portion || ROC), truncated to
  `tag-len` bytes — §4.2's `M = Authenticated Portion || ROC` and
  §4.2.1's \"truncated to the n_tag left-most bits\"."
  [auth-key authenticated-portion roc tag-len]
  (subvec (sha1/hmac-sha1 auth-key (into (vec authenticated-portion) (u32be roc))) 0 tag-len))

(defn- constant-time= [a b]
  (if (not= (count a) (count b))
    false
    (zero? (reduce bit-or 0 (map bit-xor a b)))))

(defn protect
  "Encrypt + authenticate one plaintext RTP packet (bytes, as
  `rtp.header/encode` produces). `ctx` is `{:cipher-key .. :cipher-salt
  .. :auth-key .. :roc .. :tag-length 10}` (`:tag-length` optional,
  defaults to `default-tag-length`). Returns
  `{:status :ok :bytes <srtp-packet>}` — the RTP header, unmodified;
  then the AES-CM-encrypted payload (RTP padding included, per Figure
  1); then the HMAC-SHA1 tag over all of that plus the ROC."
  [rtp-bytes {:keys [cipher-key cipher-salt auth-key roc tag-length]
              :or {tag-length default-tag-length}}]
  (let [{:keys [status] :as decoded} (rtp/decode rtp-bytes)]
    (if (= status :error)
      {:status :error :reason :srtp/invalid-rtp-packet :context decoded}
      (let [hlen (header-length rtp-bytes)
            header (subvec (vec rtp-bytes) 0 hlen)
            plaintext-portion (subvec (vec rtp-bytes) hlen (count rtp-bytes))
            index (idx/sender-index roc (:sequence-number decoded))
            iv (compute-iv cipher-salt (:ssrc decoded) index)
            schedule (aes/expand-key cipher-key)
            ciphertext-portion (cm/xor-keystream schedule iv plaintext-portion)
            authenticated-portion (into header ciphertext-portion)
            tag (auth-tag auth-key authenticated-portion roc tag-length)]
        {:status :ok :bytes (into authenticated-portion tag)}))))

(defn unprotect
  "Verify + decrypt one SRTP packet. Same `ctx` shape as `protect`.
  Returns `{:status :ok :bytes <plaintext-rtp-packet>}` or
  `{:status :error :reason :srtp/authentication-failure}` — named per
  §4.2's own required audit message, not a generic decrypt failure —
  without ever decrypting a packet whose tag does not verify first
  (verify-then-decrypt, not decrypt-then-verify)."
  [srtp-bytes {:keys [cipher-key cipher-salt auth-key roc tag-length]
               :or {tag-length default-tag-length}}]
  (if (< (count srtp-bytes) tag-length)
    {:status :error :reason :srtp/packet-too-short}
    (let [n (count srtp-bytes)
          authenticated-portion (subvec (vec srtp-bytes) 0 (- n tag-length))
          received-tag (subvec (vec srtp-bytes) (- n tag-length) n)
          expected-tag (auth-tag auth-key authenticated-portion roc tag-length)]
      (if (not (constant-time= expected-tag received-tag))
        {:status :error :reason :srtp/authentication-failure}
        (let [hlen (header-length srtp-bytes)
              header (subvec (vec srtp-bytes) 0 hlen)
              ciphertext-portion (subvec (vec srtp-bytes) hlen (- n tag-length))
              seq (bit-or (bit-shift-left (bit-and (nth srtp-bytes 2) 0xFF) 8) (bit-and (nth srtp-bytes 3) 0xFF))
              ssrc (bit-or (bit-shift-left (bit-and (nth srtp-bytes 8) 0xFF) 24)
                           (bit-shift-left (bit-and (nth srtp-bytes 9) 0xFF) 16)
                           (bit-shift-left (bit-and (nth srtp-bytes 10) 0xFF) 8)
                           (bit-and (nth srtp-bytes 11) 0xFF))
              index (idx/sender-index roc seq)
              iv (compute-iv cipher-salt ssrc index)
              schedule (aes/expand-key cipher-key)
              plaintext-portion (cm/xor-keystream schedule iv ciphertext-portion)]
          {:status :ok :bytes (into header plaintext-portion)})))))
