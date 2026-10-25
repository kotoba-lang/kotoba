(ns meta-webhook.signature
  "Verifies the `X-Hub-Signature-256` header Meta sends on every webhook POST —
  shared verbatim across the WhatsApp Business Cloud API, Messenger Platform,
  and Instagram Messaging (all Meta Graph API products use the identical
  scheme: `sha256=` + hex(HMAC-SHA256(app-secret, raw-body))).

  The raw body bytes (pre-JSON-parse) are required — re-serializing a parsed
  body can reorder keys or change whitespace and silently break verification.

  Portable. This used to be JVM-only, with a second implementation in
  `meta-webhook.async-signature` for Workers and the browser, because
  `SubtleCrypto.sign` is Promise-based and `javax.crypto.Mac` is not. Both
  halves hand-rolled their own hex encoder. `kotoba.bytes.sha256` is a pure
  implementation and therefore synchronous on both runtimes, so the fork has
  no reason to exist: the async namespace is now a shim over this one."
  (:require [kotoba.bytes :as b]
            [kotoba.bytes.sha256 :as sha]))

(defn hmac-sha256-hex
  "hex(HMAC-SHA256(secret, raw-body)) — the value after `sha256=` in
  `X-Hub-Signature-256`. `raw-body` is the request body as a UTF-8 String."
  [secret raw-body]
  (sha/hmac-sha256-hex (str secret) (str raw-body)))

(defn valid-signature?
  "`app-secret` (Meta App dashboard → Settings → Basic → App Secret) + the raw
  webhook request body + the `X-Hub-Signature-256` header value (INCLUDING the
  `sha256=` prefix) — true iff they match.

  Compared in constant time. The previous plain `=` returned as soon as two
  characters differed, and this endpoint answers whoever asks, as often as
  they ask — the shape of leak that lets a signature be recovered a byte at a
  time."
  [app-secret raw-body x-hub-signature-256]
  (b/constant-time-eq (str "sha256=" (hmac-sha256-hex app-secret raw-body))
                      (str x-hub-signature-256)))
