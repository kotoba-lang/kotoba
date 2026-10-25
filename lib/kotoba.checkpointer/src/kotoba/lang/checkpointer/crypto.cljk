(ns kotoba.lang.checkpointer.crypto
  "Per-cell AEAD envelope for checkpoint payloads at rest -- pure given key
  bytes (key persistence/lookup is kotoba.lang.checkpointer.keystore's job).
  Mirrors checkpointer.ts's #encryptPayload/#decryptPayload byte-for-byte:
  the RAW msgpack payload bytes are sealed as-is (not re-parsed), so decrypt
  hands the caller back the identical bytes with no schema awareness needed.

  Wraps kotoba.lang.pqh.crypto (XChaCha20-Poly1305, JVM-only via Bouncy
  Castle) -- the already-landed kotoba-lang/pqh port; no new crypto code
  here, just the envelope shape checkpointer.ts calls
  `_etz_encrypted`/nonce/ciphertext/keyId/sender/createdAt, msgpack-encoded.
  This is AEAD wrap/unwrap ORCHESTRATION only -- it never touches a raw
  crypto primitive itself, it calls into `pqh`'s own seam (`pqh/encrypt`/
  `pqh/decrypt`) for that, per this port's 'pure core + injected/reused
  capability' convention.

  Encryption is intentionally non-deterministic (a fresh AEAD nonce per
  call, matching pqh's `encrypt` default) -- this is orthogonal to the MST/
  CAR determinism contract, which only requires 'same (already-encrypted, if
  applicable) payload bytes => same rootCid', not 'same plaintext => same
  ciphertext' (nonce reuse would be the actual security bug).

  Portability: `.cljc`. `marker-key`/`encrypted-wrapper?` (structural,
  data-only) are portable and load under ClojureScript unconditionally.
  `encrypt-payload`/`decrypt-payload` are `#?(:clj (do ...))`-wrapped with
  throwing `:cljs` stubs, matching `kotoba.lang.checkpointer.dagcbor`'s
  precedent: they call `kotoba.lang.pqh.crypto`, which is itself JVM-only
  (Bouncy Castle, no Web Crypto XChaCha20-Poly1305 coverage, per `pqh`'s own
  README) and not yet ported to `.cljc` in the sibling `pqh` repo -- so a
  cljs AEAD path here is blocked upstream, not a shortcut taken in this
  namespace."
  #?(:clj (:require [kotoba.lang.checkpointer.msgpack :as msgpack]
                    [kotoba.lang.pqh.crypto :as pqh])))

(def marker-key "_etz_encrypted")

(defn- is-bytes?
  "Portable byte-array/binary-blob predicate -- `bytes?` is JVM-only
  (ClojureScript has no `bytes?`; a binary blob there is a `js/Uint8Array`)."
  [x]
  #?(:clj (bytes? x) :cljs (instance? js/Uint8Array x)))

(defn encrypted-wrapper?
  "Structural check mirroring checkpointer.ts's `isEncryptedWrapper`."
  [decoded]
  (and (map? decoded)
       (= 1 (get decoded marker-key))
       (is-bytes? (get decoded "nonce"))
       (is-bytes? (get decoded "ciphertext"))))

#?(:clj
(do

(defn encrypt-payload
  "key: 32-byte AEAD key (kotoba.lang.checkpointer.keystore).
  plaintext-bytes: raw msgpack payload bytes. Returns msgpack-encoded wrapper
  bytes ({_etz_encrypted:1, nonce, ciphertext, keyId, sender, createdAt})."
  ^bytes [^bytes key cell-did ^bytes plaintext-bytes]
  (let [envelope (pqh/encrypt {:key key :sender cell-did :plaintext plaintext-bytes})]
    (msgpack/encode
     {marker-key 1
      "nonce" (:nonce envelope)
      "ciphertext" (:ciphertext envelope)
      "keyId" (:key-id envelope)
      "sender" (:sender envelope)
      "createdAt" (:created-at envelope)})))

(defn decrypt-payload
  "Inverse of encrypt-payload. If `blob` doesn't decode to a recognized
  wrapper, returns it unchanged -- backwards-compat for plaintext checkpoints
  written before a cell was added to encryptCells (matches checkpointer.ts's
  comment on #decryptPayload)."
  ^bytes [^bytes key ^bytes blob]
  (let [decoded (msgpack/decode blob)]
    (if (encrypted-wrapper? decoded)
      (pqh/decrypt {:key key
                    :envelope {:v 1
                               :alg "xchacha20poly1305"
                               :nonce (get decoded "nonce")
                               :ciphertext (get decoded "ciphertext")
                               :key-id (get decoded "keyId")
                               :sender (get decoded "sender")
                               :created-at (get decoded "createdAt")}})
      blob)))

)) ;; end #?(:clj (do …))

;; ── ClojureScript: same public API, throwing (pqh's AEAD is :clj-only --
;; see namespace docstring) ─────────────────────────────────────────────────
#?(:cljs
(do
  (defn- nope [n] (throw (ex-info (str "kotoba.lang.checkpointer.crypto/" n " is :clj-only "
                                       "(wraps kotoba.lang.pqh.crypto, itself JVM-only via Bouncy Castle)") {})))
  (defn encrypt-payload [& _] (nope "encrypt-payload"))
  (defn decrypt-payload [& _] (nope "decrypt-payload"))))
