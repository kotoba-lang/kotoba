(ns feishu.async-signature
  "Promise-returning shim over `feishu.signature`, kept for callers that already
  `await` this API.

  It used to be a second implementation of the same SHA-256, written because
  `SubtleCrypto.digest` is Promise-based. The digest now comes from
  `kotoba.bytes.sha256`, which is synchronous on both runtimes, so there is
  nothing left here but the Promise wrapper. New code should call
  `feishu.signature` directly."
  (:require [feishu.signature :as sig]))

(defn sha256-hex
  "→ `js/Promise<string>`. See `feishu.signature/sha256-hex`."
  [s]
  (js/Promise.resolve (sig/sha256-hex s)))

(defn valid-signature?
  "→ `js/Promise<boolean>`. See `feishu.signature/valid-signature?`."
  [params signature]
  (js/Promise.resolve (sig/valid-signature? params signature)))
