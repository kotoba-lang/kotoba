# com-viber-bot

Minimal [Viber REST Bot API](https://developers.viber.com/docs/api/rest-bot-api/)
client — webhook signature verify + event parse + send + webhook
(de)registration. Portable `.cljc`, I/O injected, same DI conventions as
`kotoba-lang/com-line-messaging`.

## Modules

```
viber.signature         JVM-only: verify X-Viber-Content-Signature (HMAC-SHA256 hex, sync, javax.crypto)
viber.async-signature   cljs-only: same check, async (Web Crypto SubtleCrypto) -- Cloudflare Workers / browser
viber.events            pure .cljc: one decoded webhook body -> a normalized text-message event (or nil)
viber.client            portable .cljc, DI'd I/O: send-message! + set-webhook!
```

## The auth model is simpler than every Meta product — one token, not two

Viber has **no separate app secret**. The same `bot-token` (Admin Panel →
your bot → API Info) that authenticates `send-message!`/`set-webhook!`
calls is also the HMAC key `viber.signature` verifies inbound webhooks
with. Don't go looking for a second secret.

## Webhook registration runs in the OPPOSITE direction from Meta/LINE

WhatsApp/Messenger/Instagram register your webhook URL by calling *your*
endpoint with a GET verification challenge; Viber does the opposite —
*your* backend calls Viber's `set_webhook` API with your URL. `set-webhook!`
is a one-time (or whenever the URL changes) setup call, not something a
Worker route handles inbound.

## Usage

```clojure
;; Verifying + parsing an inbound webhook (JVM)
(require '[viber.signature :as sig]
         '[viber.events :as ev])
(when (sig/valid-signature? bot-token raw-body (get headers "x-viber-content-signature"))
  (ev/text-message-event decoded-body))   ; one event per webhook POST, not a batch

;; Verifying (Cloudflare Worker / browser, cljs)
(require '[viber.async-signature :as async-sig])
(-> (async-sig/valid-signature? bot-token raw-body x-viber-content-signature)
    (.then (fn [ok?] ...)))

;; Sending, and registering the webhook once
(require '[viber.client :as v])
(def io {:http-fn my-http-fn :json-write my-json-write :json-read my-json-read
         :creds {:bot-token "..."}})
(v/send-message! io {:receiver user-id :text "hello"})
(v/set-webhook! io {:url "https://your-worker.example.com/webhook/viber"})
```

## Testing

```bash
kbb -M:test   # signature.cljc + events.cljc + client.cljc (JVM)
kbb -M:lint
```

`async-signature.cljs` has no JVM-runnable test here (Web Crypto isn't
available under `kbb -M`); same posture as `line-messaging`'s and
`meta-webhook`'s async surfaces.
