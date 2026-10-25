(ns srtp.kdf
  "SRTP key derivation — [RFC 3711] §4.3 — the function that turns one
  master key + master salt into the separate cipher key, cipher salt and
  auth key each stream actually uses, so that a single provisioned
  secret never appears on the wire in more than the derived form.

  §4.3.1's own definition:

     r = index DIV key_derivation_rate
     key_id = <label> || r
     x = key_id XOR master_salt
     session_key = PRF_n(k_master, x)

  and §4.3.3 pins the PRF: \"PRF_n(k_master,x) SHALL be AES in Counter
  Mode ... with the counter value initialized to x\" — i.e. exactly
  `srtp.aes-cm/keystream`, seeded at `x * 2^16` (`* 2^16` because
  `key_id XOR master_salt` produces a 112-bit — 14-octet — value, and
  the AES-CM IV is 128 bits: the multiply-by-2^16 in §4.3.3 is what pads
  it out, by appending two zero octets, which also happens to be
  exactly where the SRTP-packet-encryption IV formula in §4.1.1 reserves
  its low 16 bits for a per-block counter).

  The label constants — SRTP encryption 0x00, SRTP auth 0x01, SRTP salt
  0x02, SRTCP encryption 0x03, SRTCP auth 0x04, SRTCP salt 0x05 — are
  §4.3's own table, reproduced as `labels` below rather than left as
  bare integers scattered through call sites.")

(require '[aes.core :as aes]
         '[srtp.aes-cm :as cm])

(def labels
  "[RFC 3711] §4.3's label byte for each of the six session keys a
  master key can derive."
  {:srtp-encryption 0x00
   :srtp-authentication 0x01
   :srtp-salting 0x02
   :srtcp-encryption 0x03
   :srtcp-authentication 0x04
   :srtcp-salting 0x05})

(defn- u48be
  "The 48-bit `r = index DIV key_derivation_rate` (or the 48-bit SRTP
  packet index elsewhere in this codec) as 6 big-endian bytes."
  [n]
  (vec (for [shift [40 32 24 16 8 0]] (bit-and (unsigned-bit-shift-right n shift) 0xFF))))

(defn- kdf-input
  "The 16-byte AES-CM seed for one derived key: XOR `key_id` (label ||
  r, 7 bytes) into the low-order 7 bytes of the 14-byte `master-salt`,
  then left-pad-by-shift with two zero bytes (the `x * 2^16` step).
  [RFC 3711] Appendix B.3 walks this exact construction with worked
  hex — including that only the salt's low 7 bytes ever change, since
  `key_id`'s own first six index bytes are zero whenever `r` is zero."
  [master-salt label r]
  (let [key-id (into [label] (u48be r))
        xored (reduce (fn [salt i] (update salt (+ 7 i) bit-xor (nth key-id i)))
                       (vec master-salt) (range 7))]
    (conj (vec xored) 0 0)))

(defn derive-key
  "One derived session key, `n-bytes` long. `index` is the current SRTP
  (or SRTCP) packet index; `kdr` is the key_derivation_rate (0 disables
  periodic re-derivation, per §4.3: \"Since this is the initial key
  derivation and the key derivation rate is equal to zero, the value of
  (index DIV key_derivation_rate) is zero\")."
  [master-key master-salt label index kdr n-bytes]
  (let [r (if (zero? kdr) 0 (quot index kdr))
        seed (kdf-input master-salt label r)
        schedule (aes/expand-key master-key)]
    (cm/keystream schedule seed n-bytes)))

(defn derive-srtp-keys
  "The three keys one SRTP stream needs, per the default
  AES_CM_128_HMAC_SHA1_80 crypto suite ([RFC 3711] §8.2): a 16-byte
  cipher key, a 14-byte cipher salt (the low-order two bytes of the
  16-byte PRF output are simply discarded — Appendix B.3's own
  `cipher salt` line does exactly this truncation), and a 20-byte
  (160-bit) HMAC-SHA1 auth key."
  ([master-key master-salt] (derive-srtp-keys master-key master-salt 0 0))
  ([master-key master-salt index kdr]
   {:cipher-key (derive-key master-key master-salt (:srtp-encryption labels) index kdr 16)
    :cipher-salt (subvec (vec (derive-key master-key master-salt (:srtp-salting labels) index kdr 16)) 0 14)
    :auth-key (derive-key master-key master-salt (:srtp-authentication labels) index kdr 20)}))
