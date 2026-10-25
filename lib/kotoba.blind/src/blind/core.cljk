(ns blind.core
  "L1 crypto layer for the kotobase stack: a keyed deterministic MAC
  (`blind-fn`) and a deterministic AEAD (`encrypt-fn` / `decrypt-fn`).

  ## What this is for

  `arrangement.core`, `kotobase-peer.core` and `kotobase-server` all take
  `blind-fn` / `encrypt-fn` / `decrypt-fn` as INJECTED functions, with (in
  the server's words) no silent default. The security property the whole
  architecture rests on — index leaf keys are blinded, index leaf values
  are AEAD ciphertext, therefore a server holding the blocks cannot filter
  or range-scan on plaintext values — was, until this library existed,
  only ever exercised by helpers defined inside two test files. This
  namespace is the promotion of those working helpers into one reviewable
  place. It is NOT new cryptography: it composes two standard primitives
  (HMAC-SHA-256 and AES-256-GCM) exactly as those helpers already did.

  ## Platform contract: JVM is synchronous, ClojureScript returns Promises

  Every function here that touches a primitive returns its result DIRECTLY
  on the JVM (`javax.crypto` is synchronous) and returns a `js/Promise` of
  that result on ClojureScript (Web Crypto's `crypto.subtle` has no
  synchronous AEAD or HMAC, and a browser/Worker runtime has no other
  primitive to fall back to). This split is not an accident of this
  library — it is already baked into the callers: `arrangement.core/commit!`
  and `kotobase-peer.core/fold!` are documented as synchronous on the JVM
  and `js/Promise`-returning on cljs for exactly this reason. Papering
  over it here (by blocking, or by pretending) would either be impossible
  or would move the async boundary somewhere less honest.

  ## Deterministic nonce, and what it costs

  `encrypt-fn` derives its 12-byte GCM nonce from the plaintext —
  `nonce = HMAC-SHA-256(nonce-key, plaintext)[0..12)` — rather than
  drawing it at random. This is required, not stylistic:
  `kotobase-peer.core/fold!` promises that folding the identical state
  from ANY writer (a server cron, a browser at idle) yields the identical
  snapshot CID, which is what makes concurrent redundant folds safe and
  cheap. A random-nonce `encrypt-fn` makes byte-identical state encrypt to
  different bytes every time, so every fold produces a different CID, and
  that property is silently gone.

  THE COST, STATED PLAINLY: deterministic encryption leaks equality of
  plaintexts. Two identical plaintexts under the same keys produce
  identical ciphertext, so an observer holding the blocks learns which
  encrypted values are equal to each other (and can confirm a guessed
  plaintext by encrypting it, if they also hold the keys). It does not
  leak the plaintexts themselves. This is a real, named cost, accepted
  deliberately in exchange for the fold-convergence design above. If your
  threat model cannot accept it, do not use this library's default mode —
  and understand that the alternative (`:nonce :random`, below) breaks
  fold determinism.

  GCM's actual requirement — never reuse a nonce with the SAME key for a
  DIFFERENT plaintext — still holds: different plaintexts get different
  HMAC outputs and therefore different nonces, with overwhelming
  probability. Only identical plaintexts reuse a nonce, and that produces
  identical ciphertext rather than a catastrophic keystream reuse across
  two different messages.

  ## What this namespace does NOT do

  It takes key material as an explicit argument and nothing else. It does
  not read environment variables, files, keychains, or any other ambient
  source; it does not generate, derive, rotate, wrap, escrow, or persist
  keys; it never logs or prints key material or plaintext, and never puts
  either into an exception's message or `ex-data`. Key management is the
  caller's problem, on purpose."
  (:require [blind.bytes :as b])
  #?(:clj (:import [java.security SecureRandom]
                   [javax.crypto Cipher Mac]
                   [javax.crypto.spec GCMParameterSpec SecretKeySpec])))

(def nonce-length
  "GCM nonce length in bytes. 12 is the only length GCM uses directly
  without an extra derivation step, and is what both callers' existing
  wire format assumes."
  12)

(def tag-bits
  "GCM authentication tag length in bits (the maximum)."
  128)

(def dek-length
  "Data-encryption-key length in bytes. AES-256 only; this library does
  not offer a weaker option."
  32)

(def min-mac-key-length
  "Minimum accepted length for a `blind-key` / `nonce-key`. HMAC-SHA-256
  accepts any key length, but a keyed MAC whose key is shorter than its
  output is a footgun, so the FACTORIES here refuse it. The low-level
  `hmac-sha256` does not, so that published test vectors (RFC 4231 uses
  keys of 4 and 131 bytes) can be run against it."
  32)

;; ── argument checking ───────────────────────────────────────────────────────
;; Error data deliberately carries lengths and roles only — never bytes.

(defn- check-bytes! [role x]
  (when-not (b/bytes?* x)
    (throw (ex-info (str "blind: " (name role) " must be raw bytes"
                         #?(:clj " (byte[])" :cljs " (js/Uint8Array)"))
                    {:blind/error :not-bytes :blind/role role})))
  x)

(defn- check-length! [role x expected]
  (check-bytes! role x)
  (when-not (= (b/blength x) expected)
    (throw (ex-info (str "blind: " (name role) " must be exactly " expected " bytes")
                    {:blind/error :bad-key-length :blind/role role
                     :expected expected :actual (b/blength x)})))
  x)

(defn- check-min-length! [role x minimum]
  (check-bytes! role x)
  (when (< (b/blength x) minimum)
    (throw (ex-info (str "blind: " (name role) " must be at least " minimum " bytes")
                    {:blind/error :bad-key-length :blind/role role
                     :minimum minimum :actual (b/blength x)})))
  x)

;; ── HMAC-SHA-256 ────────────────────────────────────────────────────────────

#?(:cljs (defn- subtle [] (.-subtle js/crypto)))

#?(:cljs
   (defn- import-hmac-key [key-bytes]
     (.importKey (subtle) "raw" key-bytes
                 #js {:name "HMAC" :hash "SHA-256"} false #js ["sign"])))

#?(:cljs
   (defn- import-aes-key [dek]
     (.importKey (subtle) "raw" dek #js {:name "AES-GCM"} false
                 #js ["encrypt" "decrypt"])))

(defn hmac-sha256
  "HMAC-SHA-256 of `msg-bytes` under `key-bytes`. Returns the 32 raw MAC
  bytes on the JVM, a `js/Promise` of them on cljs.

  Accepts any key length (unlike the factories below), so that published
  vectors can be replayed against it verbatim."
  [key-bytes msg-bytes]
  (check-bytes! :key key-bytes)
  (check-bytes! :message msg-bytes)
  #?(:clj
     (let [mac (Mac/getInstance "HmacSHA256")]
       (.init mac (SecretKeySpec. ^bytes key-bytes "HmacSHA256"))
       (.doFinal mac ^bytes msg-bytes))
     :cljs
     (-> (import-hmac-key key-bytes)
         (.then (fn [k] (.sign (subtle) #js {:name "HMAC"} k msg-bytes)))
         (.then (fn [buf] (js/Uint8Array. buf))))))

;; ── AES-256-GCM ─────────────────────────────────────────────────────────────

(defn aes-gcm-seal
  "AES-256-GCM encrypt with an EXPLICIT nonce. Returns
  `ciphertext ++ tag` (the tag appended, which is what both `javax.crypto`
  and Web Crypto produce natively) — NOT including the nonce; see
  `encrypt-fn` for the framed wire form. Bytes on the JVM, a `js/Promise`
  of bytes on cljs.

  Low-level on purpose: exposed so that NIST CAVP GCM vectors, which
  supply their own IV, can be replayed against it. Application code should
  use `encrypt-fn`, which owns nonce derivation."
  [dek nonce plaintext]
  (check-length! :dek dek dek-length)
  (check-length! :nonce nonce nonce-length)
  (check-bytes! :plaintext plaintext)
  #?(:clj
     (let [cipher (Cipher/getInstance "AES/GCM/NoPadding")]
       (.init cipher Cipher/ENCRYPT_MODE
              (SecretKeySpec. ^bytes dek "AES")
              (GCMParameterSpec. tag-bits ^bytes nonce))
       (.doFinal cipher ^bytes plaintext))
     :cljs
     (-> (import-aes-key dek)
         (.then (fn [k]
                  (.encrypt (subtle)
                            #js {:name "AES-GCM" :iv nonce :tagLength tag-bits}
                            k plaintext)))
         (.then (fn [buf] (js/Uint8Array. buf))))))

(def ^:private auth-failed-msg
  "blind: AEAD authentication failed (wrong key, wrong nonce, or tampered ciphertext)")

(defn- auth-failed []
  (ex-info auth-failed-msg {:blind/error :auth-failed}))

(defn aes-gcm-open
  "Inverse of `aes-gcm-seal`: decrypt `ciphertext ++ tag` under `dek` and
  the explicit `nonce`. Bytes on the JVM, a `js/Promise` of bytes on cljs.

  On authentication failure throws (JVM) / rejects (cljs) with an
  `ex-info` carrying `{:blind/error :auth-failed}` and NOTHING else — no
  key, no nonce, no ciphertext."
  [dek nonce ciphertext]
  (check-length! :dek dek dek-length)
  (check-length! :nonce nonce nonce-length)
  (check-bytes! :ciphertext ciphertext)
  #?(:clj
     (let [cipher (Cipher/getInstance "AES/GCM/NoPadding")]
       (.init cipher Cipher/DECRYPT_MODE
              (SecretKeySpec. ^bytes dek "AES")
              (GCMParameterSpec. tag-bits ^bytes nonce))
       (try
         (.doFinal cipher ^bytes ciphertext)
         (catch javax.crypto.AEADBadTagException _ (throw (auth-failed)))
         (catch javax.crypto.BadPaddingException _ (throw (auth-failed)))
         (catch javax.crypto.IllegalBlockSizeException _ (throw (auth-failed)))))
     :cljs
     (-> (import-aes-key dek)
         (.then (fn [k]
                  (.decrypt (subtle)
                            #js {:name "AES-GCM" :iv nonce :tagLength tag-bits}
                            k ciphertext)))
         (.then (fn [buf] (js/Uint8Array. buf))
                (fn [_] (js/Promise.reject (auth-failed)))))))

;; ── nonces ──────────────────────────────────────────────────────────────────

(defn derive-nonce
  "The deterministic nonce this library's default mode uses:
  `HMAC-SHA-256(nonce-key, plaintext)` truncated to `nonce-length` bytes.
  Bytes on the JVM, a `js/Promise` of bytes on cljs.

  Truncating a MAC to 96 bits is safe for this purpose: the nonce is not a
  secret and not an authenticator, it only has to be (a) a deterministic
  function of the plaintext and (b) unlikely to collide across DIFFERENT
  plaintexts under the same key."
  [nonce-key plaintext]
  (check-min-length! :nonce-key nonce-key min-mac-key-length)
  (check-bytes! :plaintext plaintext)
  #?(:clj  (b/slice (hmac-sha256 nonce-key plaintext) 0 nonce-length)
     :cljs (-> (hmac-sha256 nonce-key plaintext)
               (.then (fn [mac] (b/slice mac 0 nonce-length))))))

(defn random-nonce
  "A fresh cryptographically-random `nonce-length`-byte nonce, from
  `SecureRandom` (JVM) / `crypto.getRandomValues` (cljs). Synchronous on
  BOTH platforms — Web Crypto's RNG is the one part of it that is not
  Promise-based.

  Only used by `encrypt-fn`'s opt-in `:nonce :random` mode. Note this
  generates a NONCE, not a key: this library never generates keys."
  []
  #?(:clj  (let [b (byte-array nonce-length)]
             (.nextBytes (SecureRandom.) b)
             b)
     :cljs (.getRandomValues js/crypto (js/Uint8Array. nonce-length))))

;; ── the three injected functions ────────────────────────────────────────────

(defn blind-fn
  "Build the `blind-fn` the index layer injects: a keyed, deterministic,
  one-way MAC over an index-key component.

  `(blind-fn blind-key)` returns `(fn [component] token)` where `token` is
  a base64 string on the JVM and a `js/Promise` of that string on cljs.
  Same component in, same token out — which is the point: a caller who
  knows a plaintext prefix can re-derive its token and seek on it, while a
  server holding only tokens cannot invert them.

  Options:
    `:serialize`  component -> string, default `pr-str` (what the existing
                  callers use). NOTE that `pr-str` is only guaranteed to
                  agree across JVM and cljs for values whose printed form
                  is platform-independent — strings, keywords, symbols,
                  integers. If you blind anything else, supply your own
                  serializer; a JVM writer and a browser writer that
                  disagree on the printed form will produce different
                  tokens for the same logical key and the index will
                  silently split.
    `:encode`     `:base64` (default, matches the existing callers) or
                  `:hex`.

  `blind-key` must be at least 32 bytes."
  ([blind-key] (blind-fn blind-key nil))
  ([blind-key {:keys [serialize encode] :or {serialize pr-str encode :base64}}]
   (check-min-length! :blind-key blind-key min-mac-key-length)
   (let [enc (case encode
               :base64 b/base64
               :hex b/hex
               (throw (ex-info "blind: :encode must be :base64 or :hex"
                               {:blind/error :bad-option :encode encode})))]
     (fn blind [component]
       (let [msg (b/utf8 (serialize component))]
         #?(:clj  (enc (hmac-sha256 blind-key msg))
            :cljs (-> (hmac-sha256 blind-key msg) (.then enc))))))))

(defn encrypt-fn
  "Build the `encrypt-fn` the index layer injects: an AEAD seal over an
  index leaf value.

  `(encrypt-fn {:dek dek :nonce-key nonce-key})` returns
  `(fn [plaintext-bytes] blob)` where `blob` is `nonce ++ ciphertext ++ tag`
  as ONE byte sequence (the same combined wire shape the existing callers
  already write), directly on the JVM and as a `js/Promise` on cljs.

  DEFAULT MODE — deterministic. The nonce is `derive-nonce`d from the
  plaintext, so the same plaintext always seals to the same bytes. This is
  what preserves `kotobase-peer.core/fold!`'s content-address convergence.
  It leaks equality of plaintexts; see this namespace's docstring, which
  states that tradeoff in full.

  OPT-IN MODE — `(encrypt-fn {:dek dek :nonce :random})`. Draws a fresh
  random nonce per call. CHOOSING THIS BREAKS FOLD DETERMINISM: identical
  state will fold to a different snapshot CID on every writer and every
  retry, so concurrent redundant folds stop converging and stop being
  free. Do not choose it merely because random nonces are the usual
  advice — choose it only if you have decided that plaintext-equality
  leakage is unacceptable AND that you can pay for non-convergent folds.

  `:dek` must be exactly 32 bytes (AES-256). `:nonce-key` must be at least
  32 bytes and MUST be a different key from `:dek` and from the blind key.
  Exactly one of `:nonce-key` / `:nonce :random` may be given."
  [{:keys [dek nonce-key nonce]}]
  (check-length! :dek dek dek-length)
  (when (and nonce-key nonce)
    (throw (ex-info "blind: give either :nonce-key (deterministic) or :nonce :random, not both"
                    {:blind/error :bad-option})))
  (when (and nonce (not= nonce :random))
    (throw (ex-info "blind: :nonce may only be :random"
                    {:blind/error :bad-option :nonce nonce})))
  (when-not (or nonce-key nonce)
    (throw (ex-info "blind: encrypt-fn needs :nonce-key (deterministic; see docstring) or :nonce :random (opt-in, breaks fold determinism)"
                    {:blind/error :bad-option})))
  (when nonce-key (check-min-length! :nonce-key nonce-key min-mac-key-length))
  (if nonce-key
    (fn encrypt [plaintext]
      (check-bytes! :plaintext plaintext)
      #?(:clj
         (let [n (derive-nonce nonce-key plaintext)]
           (b/concat-bytes n (aes-gcm-seal dek n plaintext)))
         :cljs
         (-> (derive-nonce nonce-key plaintext)
             (.then (fn [n]
                      (-> (aes-gcm-seal dek n plaintext)
                          (.then (fn [ct] (b/concat-bytes n ct)))))))))
    (fn encrypt-random [plaintext]
      (check-bytes! :plaintext plaintext)
      (let [n (random-nonce)]
        #?(:clj  (b/concat-bytes n (aes-gcm-seal dek n plaintext))
           :cljs (-> (aes-gcm-seal dek n plaintext)
                     (.then (fn [ct] (b/concat-bytes n ct)))))))))

(defn decrypt-fn
  "Build the `decrypt-fn` the index layer injects: the inverse of
  `encrypt-fn`. `(decrypt-fn {:dek dek})` returns
  `(fn [blob] plaintext-bytes)`, splitting the leading `nonce-length`
  bytes back off and opening the rest. Bytes on the JVM, a `js/Promise`
  of bytes on cljs.

  One `decrypt-fn` reads BOTH modes' output — the nonce is on the wire, so
  it does not need to know whether the writer derived it or drew it at
  random, and needs no `:nonce-key`.

  Throws / rejects with `{:blind/error :auth-failed}` on a tampered or
  wrong-key blob, and `{:blind/error :truncated}` on a blob too short to
  contain a nonce and a tag."
  [{:keys [dek]}]
  (check-length! :dek dek dek-length)
  (fn decrypt [blob]
    (check-bytes! :blob blob)
    (let [min-len (+ nonce-length (quot tag-bits 8))]
      (if (< (b/blength blob) min-len)
        (let [e (ex-info "blind: blob too short to be a sealed value"
                         {:blind/error :truncated
                          :minimum min-len :actual (b/blength blob)})]
          #?(:clj (throw e) :cljs (js/Promise.reject e)))
        (let [n (b/slice blob 0 nonce-length)
              ct (b/slice blob nonce-length)]
          (aes-gcm-open dek n ct))))))
