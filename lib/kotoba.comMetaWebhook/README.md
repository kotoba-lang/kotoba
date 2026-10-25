# com-meta-webhook

Shared webhook infrastructure for Meta Graph API messaging products
(WhatsApp Business Cloud API, Messenger Platform, Instagram Messaging — all
three use the identical `X-Hub-Signature-256` verification scheme and setup
handshake, so this library covers all of them rather than duplicating the
crypto/handshake code per-product).

## Modules

```
meta-webhook.signature          JVM-only: verify X-Hub-Signature-256 (HMAC-SHA256 hex, sync, javax.crypto)
meta-webhook.async-signature    cljs-only: same check, async (Web Crypto SubtleCrypto) -- Cloudflare Workers / browser
meta-webhook.handshake          pure .cljc: the GET hub.mode/hub.verify_token/hub.challenge setup handshake
meta-webhook.whatsapp-events    pure .cljc: WhatsApp Business Cloud API webhook JSON -> normalized text-message events
meta-webhook.messenger-events   pure .cljc: Messenger Platform webhook JSON -> normalized text-message events
meta-webhook.messenger-client   portable .cljc, DI'd I/O: Messenger Send API (send-message!)
meta-webhook.instagram-events   pure .cljc: Instagram Messaging webhook JSON -> normalized text-message events
meta-webhook.instagram-client   portable .cljc, DI'd I/O: Instagram Messaging Send API (send-message!)
```

WhatsApp's send-side is **not** duplicated here — `kotoba-lang/tayori`'s
`tayori.channel.whatsapp` already covers `POST /{phone-number-id}/messages`;
this library's WhatsApp coverage is receive-side (webhook verify + parse)
only. Messenger has no existing send client anywhere in kotoba-lang, so
`messenger-client` covers both directions for that product.

## Usage

```clojure
;; Verifying + parsing an inbound webhook (JVM)
(require '[meta-webhook.signature :as sig]
         '[meta-webhook.whatsapp-events :as wa-ev])   ; or messenger-events
(when (sig/valid-signature? app-secret raw-body (get headers "x-hub-signature-256"))
  (wa-ev/text-message-events decoded-body))

;; Verifying (Cloudflare Worker / browser, cljs)
(require '[meta-webhook.async-signature :as async-sig])
(-> (async-sig/valid-signature? app-secret raw-body x-hub-signature-256)
    (.then (fn [ok?] ...)))

;; The one-time webhook URL registration handshake
(require '[meta-webhook.handshake :as hs])
(hs/verify-handshake {:mode (get query "hub.mode")
                       :verify-token (get query "hub.verify_token")
                       :challenge (get query "hub.challenge")}
                      my-configured-verify-token)
;=> the challenge string to return as the response body, or nil (403)

;; Sending a Messenger reply
(require '[meta-webhook.messenger-client :as mc])
(mc/send-message! {:http-fn my-http-fn :json-write my-json-write :json-read my-json-read
                    :creds {:page-access-token "..."}}
                   {:recipient-id user-id :text "hello"})

;; Sending an Instagram DM reply
(require '[meta-webhook.instagram-client :as ic])
(ic/send-message! {:http-fn my-http-fn :json-write my-json-write :json-read my-json-read
                    :creds {:ig-user-id "..." :access-token "..."}}
                   {:recipient-id igsid :text "hello"})
```

`app-secret` (webhook verification) and `page-access-token`/WhatsApp's
`access-token`/Instagram's `ig-user-id`+`access-token` (send) are different
values from different pages of the Meta App dashboard — do not conflate them. Neither is acquired by this library;
callers resolve them from env/secrets.

## Testing

```bash
kbb -M:test   # signature/handshake/whatsapp-events/messenger-events/messenger-client/instagram-* (JVM)
kbb -M:lint
```

`async-signature.cljs` has no JVM-runnable test here (Web Crypto isn't
available under `kbb -M`); it's exercised by its consumer's own
integration test (a real Cloudflare Worker webhook route), same posture as
`line-messaging`'s async surface.
