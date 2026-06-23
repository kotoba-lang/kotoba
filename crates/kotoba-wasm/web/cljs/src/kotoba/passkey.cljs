(ns kotoba.passkey
  "Passkey (WebAuthn PRF) unlock of the sovereign identity (docs/gftd-office doc b).

   The account's 32-byte Ed25519 seed is wrapped with an AES-GCM key DERIVED from the
   WebAuthn **PRF** extension output of a passkey. Only the passkey (held in the device
   authenticator / Secure Enclave) can produce that PRF secret, so only it can unwrap
   the seed. Only ciphertext is persisted (localStorage) — the seed never rests in the
   clear. `enroll!` registers a passkey + wraps a fresh identity; `unlock!` recovers the
   SAME identity on any device that has the passkey. Browser-only.

   NOTE on :advanced compilation: native browser APIs (navigator.credentials,
   SubtleCrypto, WebAuthn extension results) must be reached with `^js` hints and
   goog.object/get so the Closure compiler does not munge their method/property names."
  (:require [goog.object :as gobj]))

(def ^:private storage-key "kotoba.passkey.seed")

;; fixed app salt for the PRF eval (deterministic secret per passkey): "kotoba:prf:v1"
(def ^:private prf-salt
  (js/Uint8Array.from #js [107 111 116 111 98 97 58 112 114 102 58 118 49]))

(defn- rand-bytes [n]
  (let [a (js/Uint8Array. n)] (js/crypto.getRandomValues a) a))

(defn- byte->hex [b]
  (let [h (.toString b 16)] (if (== 1 (.-length h)) (str "0" h) h)))

(defn- buf->hex [buf]
  (let [a (js/Uint8Array. buf)]
    (areduce a i acc "" (str acc (byte->hex (aget a i))))))

(defn- buf->b64 [buf]
  (js/btoa (.apply js/String.fromCharCode nil (js/Uint8Array. buf))))

(defn- b64->u8 [s]
  (let [bin (js/atob s) n (.-length bin) a (js/Uint8Array. n)]
    (dotimes [i n] (aset a i (.charCodeAt bin i)))
    a))

(defn- credentials [] ^js (gobj/get js/navigator "credentials"))
(defn- subtle [] ^js (gobj/get js/crypto "subtle"))

(defn- prf-secret
  "Run a passkey assertion with a PRF eval and return Promise<Uint8Array(32)>."
  [rp-id]
  (-> (.get (credentials)
            #js {:publicKey #js {:challenge (rand-bytes 32)
                                 :rpId rp-id
                                 :userVerification "required"
                                 :extensions #js {:prf #js {:eval #js {:first prf-salt}}}
                                 :timeout 15000}})
      (.then (fn [assertion]
               (let [res   (.getClientExtensionResults ^js assertion)
                     first (some-> (gobj/get res "prf")
                                   (gobj/get "results")
                                   (gobj/get "first"))]
                 (if first
                   (js/Uint8Array. first)
                   (throw (js/Error. "passkey PRF extension not available"))))))))

(defn- import-aes [prf-bytes]
  (.importKey (subtle) "raw" prf-bytes #js {:name "AES-GCM"} false
              #js ["encrypt" "decrypt"]))

(defn- wrap-seed [prf-bytes seed-u8]
  (-> (import-aes prf-bytes)
      (.then (fn [key]
               (let [iv (rand-bytes 12)]
                 (-> (.encrypt (subtle) #js {:name "AES-GCM" :iv iv} key seed-u8)
                     (.then (fn [ct] (str (buf->b64 iv) ":" (buf->b64 ct))))))))))

(defn- unwrap-seed [prf-bytes blob]
  (let [parts (.split blob ":")
        iv (b64->u8 (aget parts 0))
        ct (b64->u8 (aget parts 1))]
    (-> (import-aes prf-bytes)
        (.then (fn [key]
                 (-> (.decrypt (subtle) #js {:name "AES-GCM" :iv iv} key ct)
                     (.then (fn [pt] (js/Uint8Array. pt)))))))))

(defn enroll!
  "Register a passkey and wrap a FRESH sovereign identity under its PRF secret.
   Activates the identity on `node` and persists only ciphertext. Returns
   Promise<account-did (z6Mk)>. `rp-id` is the site (e.g. \"localhost\"/\"docs.gftd.ai\")."
  [^js node rp-id user-name]
  (-> (.create (credentials)
               #js {:publicKey #js {:challenge (rand-bytes 32)
                                    :rp #js {:name "kotoba" :id rp-id}
                                    :user #js {:id (rand-bytes 16)
                                               :name user-name
                                               :displayName user-name}
                                    :pubKeyCredParams #js [#js {:type "public-key" :alg -7}
                                                           #js {:type "public-key" :alg -257}]
                                    :authenticatorSelection #js {:residentKey "required"
                                                                 :userVerification "required"}
                                    :extensions #js {:prf #js {}}
                                    :timeout 15000}})
      (.then (fn [_cred] (prf-secret rp-id)))
      (.then (fn [prf]
               (let [seed (rand-bytes 32)]
                 (.useIdentity node (buf->hex seed))
                 (-> (wrap-seed prf seed)
                     (.then (fn [blob]
                              (js/localStorage.setItem storage-key blob)
                              (.accountDid node)))))))))

(defn unlock!
  "Recover the wrapped identity via the passkey PRF and activate it on `node`.
   Returns Promise<account-did (z6Mk)> — equal to the enrolled account on any device
   holding the passkey."
  [^js node rp-id]
  (let [blob (js/localStorage.getItem storage-key)]
    (if-not blob
      (js/Promise.reject (js/Error. "no enrolled passkey on this device"))
      (-> (prf-secret rp-id)
          (.then (fn [prf] (unwrap-seed prf blob)))
          (.then (fn [seed]
                   (.useIdentity node (buf->hex seed))
                   (.accountDid node)))))))

(defn enrolled? [] (some? (js/localStorage.getItem storage-key)))

;; exports
(def ^:export enrollPasskey enroll!)
(def ^:export unlockPasskey unlock!)
(def ^:export passkeyEnrolled enrolled?)
