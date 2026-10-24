(ns line-messaging.async-signature
  "Cloudflare Workers / browser counterpart to `line-messaging.signature` --
  Web Crypto's `SubtleCrypto.sign` is Promise-based, so this is a plain
  `.cljs` namespace (no `:clj` branch to share), the same async-surface split
  `com-gmail` uses for `gmail.async-client` vs `gmail.client`.

  `raw-body` MUST be the exact bytes LINE sent (pre-JSON-parse) -- on a
  Cloudflare Worker that means reading `request.text()` (or `.arrayBuffer()`)
  BEFORE any `request.json()` call, since a Request body stream can only be
  consumed once."
  (:require [goog.crypt.base64 :as b64]))

(defn- ->key [secret]
  (.importKey js/crypto.subtle
              "raw"
              (.encode (js/TextEncoder.) secret)
              #js {:name "HMAC" :hash "SHA-256"}
              false
              #js ["sign"]))

(defn hmac-sha256-base64
  "base64(HMAC-SHA256(secret, raw-body)) -- returns a `js/Promise<string>`."
  [secret raw-body]
  (-> (->key secret)
      (.then (fn [key]
               (.sign js/crypto.subtle "HMAC" key
                      (.encode (js/TextEncoder.) raw-body))))
      (.then (fn [sig-buf] (b64/encodeByteArray (js/Uint8Array. sig-buf))))))

(defn valid-signature?
  "Same contract as `line-messaging.signature/valid-signature?`, async:
  returns a `js/Promise<boolean>`."
  [channel-secret raw-body x-line-signature]
  (-> (hmac-sha256-base64 channel-secret raw-body)
      (.then (fn [computed] (= computed (str x-line-signature))))))
