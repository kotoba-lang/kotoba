(ns meta-webhook.async-signature
  "Promise-returning shim over `meta-webhook.signature`, kept for callers that
  already `await` this API (cloud-manimani's Instagram/WhatsApp/Messenger
  Workers).

  It used to be a second implementation of the same HMAC, written because
  `SubtleCrypto.sign` is Promise-based. The signature now comes from
  `kotoba.bytes.sha256`, which is synchronous on both runtimes, so there is
  nothing left here but the Promise wrapper. New code should call
  `meta-webhook.signature` directly."
  (:require [meta-webhook.signature :as sig]))

(defn hmac-sha256-hex
  "→ `js/Promise<string>`. See `meta-webhook.signature/hmac-sha256-hex`."
  [secret raw-body]
  (js/Promise.resolve (sig/hmac-sha256-hex secret raw-body)))

(defn valid-signature?
  "→ `js/Promise<boolean>`. See `meta-webhook.signature/valid-signature?`."
  [app-secret raw-body x-hub-signature-256]
  (js/Promise.resolve (sig/valid-signature? app-secret raw-body x-hub-signature-256)))
