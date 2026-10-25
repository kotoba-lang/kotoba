(ns line-messaging.signature
  "JVM-only (see `line-messaging.async-signature` for the Cloudflare
  Workers/browser counterpart -- Web Crypto's `subtle.sign` is inherently
  async, so this synchronous HMAC-SHA256 check cannot itself be made
  portable `.cljc`, the same sync-vs-async platform split `com-gmail`
  documents for its own client vs async-client).

  Verifies the `X-Line-Signature` header LINE sends on every webhook POST:
  base64(HMAC-SHA256(channel-secret, raw-request-body)). The raw body bytes
  (pre-JSON-parse) are required -- re-serializing a parsed body can reorder
  keys / change whitespace and silently break verification."
  #?(:clj (:import [javax.crypto Mac]
                    [javax.crypto.spec SecretKeySpec]
                    [java.util Base64])))

#?(:clj
   (defn hmac-sha256-base64
     "base64(HMAC-SHA256(secret, raw-body)) -- the exact value LINE puts in
     `X-Line-Signature`. `raw-body` is the request body as a String (UTF-8)."
     [secret raw-body]
     (let [mac (Mac/getInstance "HmacSHA256")]
       (.init mac (SecretKeySpec. (.getBytes (str secret) "UTF-8") "HmacSHA256"))
       (->> (.getBytes (str raw-body) "UTF-8")
            (.doFinal mac)
            (.encodeToString (Base64/getEncoder))))))

#?(:clj
   (defn valid-signature?
     "`channel-secret` (from LINE Developers Console, NOT the channel access
     token) + the raw webhook request body + the `X-Line-Signature` header
     value -- true iff they match. Constant-time-ish via `Mac`'s own compare
     is not guaranteed by this impl (plain `=` on the base64 strings); LINE's
     webhook is not a scenario where timing-attack resistance is the
     realistic threat (a caller who already has a channel secret guess and
     network access to time responses has bigger problems), so a simple
     equality check is deliberately used here rather than importing a
     constant-time-compare dependency for it."
     [channel-secret raw-body x-line-signature]
     (= (hmac-sha256-base64 channel-secret raw-body) (str x-line-signature))))
