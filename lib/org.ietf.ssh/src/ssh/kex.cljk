(ns ssh.kex
  "The server side of the SSH-2 curve25519-sha256 key exchange reply (RFC 5656
  §3, §4; RFC 8731): the `ecdsa-sha2-nistp256` host-key blob `K_S`, the signature
  blob, and the `SSH_MSG_KEX_ECDH_REPLY` and `SSH_MSG_NEWKEYS` payloads.

  Like `ssh.transport`, this is pure byte assembly: the caller supplies the host
  public key point, the ephemeral public key `Q_S`, and the `(r, s)` of an ECDSA
  signature over `H`. It computes no crypto and does no I/O. It is the single
  source of truth for these wire encodings, mirrored byte-for-byte by the aiueos
  kernel's `net_ssh_kex` (which supplies the crypto from its Kotoba objects:
  X25519 for `Q_S`/`K`, SHA-256 for `H`, and the ECDSA-P256 sign object for
  `(r, s)`).

  A note on what the host key signs: the exchange hash is `H = SHA256(transcript)`
  (`ssh.transport/exchange-hash`). The `ecdsa-sha2-nistp256` algorithm then signs
  `H` as an ECDSA-with-SHA-256 message, so the ECDSA digest fed to the signer is
  `SHA256(H)` -- see `ecdsa-digest`."
  (:require [ssh.transport :as t]))

(def msg-kex-ecdh-reply t/msg-kex-ecdh-reply)  ; 31
(def msg-newkeys t/msg-newkeys)                 ; 21

(def host-key-algorithm "ecdsa-sha2-nistp256")
(def host-key-curve "nistp256")

(defn ec-point
  "The SEC1 uncompressed point encoding of an EC public key: 0x04 || X || Y,
  with X and Y each 32 bytes for P-256. `x` and `y` are 32-byte big-endian
  vectors."
  [x y]
  (into (into [0x04] x) y))

(defn host-key-blob
  "K_S -- the `ecdsa-sha2-nistp256` public host key blob (RFC 5656 §3.1):
     string  \"ecdsa-sha2-nistp256\"
     string  \"nistp256\"
     string  Q            (the SEC1 uncompressed point, 65 bytes)
  `point` is the 65-byte 0x04||X||Y encoding (see `ec-point`)."
  [point]
  (-> []
      (into (t/string-bytes (t/str->bytes host-key-algorithm)))
      (into (t/string-bytes (t/str->bytes host-key-curve)))
      (into (t/string-bytes point))))

(defn signature-blob
  "The `ecdsa-sha2-nistp256` signature blob (RFC 5656 §3.1.2):
     string  \"ecdsa-sha2-nistp256\"
     string  ( mpint r || mpint s )      <- the inner blob is itself a string
  `r` and `s` are 32-byte big-endian vectors (the ECDSA signature scalars)."
  [r s]
  (let [inner (into (t/mpint r) (t/mpint s))]
    (-> []
        (into (t/string-bytes (t/str->bytes host-key-algorithm)))
        (into (t/string-bytes inner)))))

(defn kex-ecdh-reply-payload
  "The SSH_MSG_KEX_ECDH_REPLY payload (RFC 5656 §4):
     byte    SSH_MSG_KEX_ECDH_REPLY (31)
     string  K_S            (server public host key, see host-key-blob)
     string  Q_S            (server ephemeral public key -- 32 bytes for curve25519)
     string  signature      (see signature-blob)"
  [k-s q-s sig-blob]
  (-> [msg-kex-ecdh-reply]
      (into (t/string-bytes k-s))
      (into (t/string-bytes q-s))
      (into (t/string-bytes sig-blob))))

(defn newkeys-payload
  "The SSH_MSG_NEWKEYS payload: just the message number (RFC 4253 §7.3)."
  []
  [msg-newkeys])

(defn ecdsa-digest
  "The ECDSA message digest for `ecdsa-sha2-nistp256`: SHA-256 of the exchange
  hash H. `sha256` is supplied by the caller; `h` is the 32-byte exchange hash."
  [sha256 h]
  (sha256 h))
