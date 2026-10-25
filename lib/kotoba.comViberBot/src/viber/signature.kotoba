(ns viber.signature
  "JVM-only (see `viber.async-signature` for the Cloudflare Workers/browser
  counterpart — same sync-vs-async platform split `meta-webhook.signature`/
  `async-signature` and `line-messaging.signature`/`async-signature`
  document).

  Verifies the `X-Viber-Content-Signature` header Viber sends on every
  webhook POST: hex(HMAC-SHA256(bot-auth-token, raw-body)). **The HMAC key
  is the bot's own auth token** — unlike every Meta product (WhatsApp/
  Messenger/Instagram), which use a SEPARATE app secret distinct from the
  send-side access token, Viber has no separate webhook-signing secret; the
  same token that authenticates `send_message!`/`set-webhook!` calls also
  signs inbound webhooks. Do not go looking for a `VIBER_APP_SECRET` — it
  doesn't exist, `:creds {:bot-token}` is the only credential this whole
  library needs. The raw body bytes (pre-JSON-parse) are required for
  verification, same as every other webhook signature in this workspace."
  (:require [kotoba.bytes :as b]
            [kotoba.bytes.sha256 :as sha]))

(defn hmac-sha256-hex
  "hex(HMAC-SHA256(bot-token, raw-body)) — the exact value Viber puts in
  `X-Viber-Content-Signature` (no `sha256=` prefix, unlike Meta's scheme).
  `raw-body` is the request body as a UTF-8 String."
  [bot-token raw-body]
  (sha/hmac-sha256-hex (str bot-token) (str raw-body)))

(defn valid-signature?
  "`bot-token` (the same token used for `send_message!` / `set-webhook!` — see
  the ns docstring, this is NOT a separate app secret) + the raw webhook
  request body + the `X-Viber-Content-Signature` header value — true iff they
  match.

  Compared in constant time. The previous plain `=` returned as soon as two
  characters differed, and this endpoint answers whoever asks, as often as
  they ask — the shape of leak that lets a signature be recovered a byte at a
  time."
  [bot-token raw-body x-viber-content-signature]
  (b/constant-time-eq (hmac-sha256-hex bot-token raw-body)
                      (str x-viber-content-signature)))
