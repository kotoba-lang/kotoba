(ns ssh.keys
  "The post-NEWKEYS key derivation (RFC 4253 §7.2) for a curve25519-sha256
  session. Once the exchange hash `H` and the shared secret `K` are agreed, both
  sides derive per-direction keys and IVs from them:

     IV  client->server = HASH(K || H || \"A\" || session_id)
     IV  server->client = HASH(K || H || \"B\" || session_id)
     key client->server = HASH(K || H || \"C\" || session_id)
     key server->client = HASH(K || H || \"D\" || session_id)

  where HASH is SHA-256 (for curve25519-sha256), `K` is encoded as an `mpint`,
  `H` and `session_id` are the raw 32-byte hash values, and the letter is one
  byte. `session_id` is `H` from the FIRST key exchange (it never changes across
  rekeys). For `aes128-gcm@openssh.com` the key is the first 16 bytes and the IV
  the first 12 bytes of the derived material (one SHA-256 gives 32, so no key
  expansion is needed).

  Pure: the caller supplies SHA-256. The aiueos kernel mirrors this to derive the
  same keys from its X25519 `K` and SHA-256 `H`."
  (:require [ssh.transport :as t]))

(defn derive
  "One derived value: HASH(mpint(K) || H || letter || session_id), truncated to
  `n` bytes. `sha256` is supplied by the caller. `k`/`h`/`session-id` are byte
  vectors; `h` and `session-id` are the raw 32-byte hashes; `k` is the raw shared
  secret (encoded here as mpint, exactly as it was in the exchange hash). `letter`
  is the one-character string \"A\"..\"F\" -- via str->bytes because (int \\A) is
  0 under ClojureScript, not 65."
  [sha256 k h session-id letter n]
  (subvec (sha256 (-> (t/mpint k) (into h) (into (t/str->bytes letter)) (into session-id))) 0 n))

(def aes128-key-len 16)
(def gcm-iv-len 12)

(defn session-keys
  "All four aes128-gcm@openssh.com session parameters as a map. `session-id` is
  H from the first kex (pass `h` itself for the first session)."
  [sha256 k h session-id]
  {:iv-c->s  (derive sha256 k h session-id "A" gcm-iv-len)
   :iv-s->c  (derive sha256 k h session-id "B" gcm-iv-len)
   :key-c->s (derive sha256 k h session-id "C" aes128-key-len)
   :key-s->c (derive sha256 k h session-id "D" aes128-key-len)})
