(ns viber.async-signature
  "Promise-returning shim over `viber.signature`, kept for callers that already
  `await` this API (cloud-manimani's Viber Worker).

  It used to be a second implementation of the same HMAC, written because
  `SubtleCrypto.sign` is Promise-based. The signature now comes from
  `kotoba.bytes.sha256`, which is synchronous on both runtimes, so there is
  nothing left here but the Promise wrapper. New code should call
  `viber.signature` directly."
  (:require [viber.signature :as sig]))

(defn hmac-sha256-hex
  "→ `js/Promise<string>`. See `viber.signature/hmac-sha256-hex`."
  [bot-token raw-body]
  (js/Promise.resolve (sig/hmac-sha256-hex bot-token raw-body)))

(defn valid-signature?
  "→ `js/Promise<boolean>`. See `viber.signature/valid-signature?`."
  [bot-token raw-body x-viber-content-signature]
  (js/Promise.resolve (sig/valid-signature? bot-token raw-body x-viber-content-signature)))
