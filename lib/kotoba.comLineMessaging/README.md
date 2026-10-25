# com-line-messaging

Minimal [LINE Messaging API](https://developers.line.biz/en/reference/messaging-api/)
boundary: webhook signature verification, webhook event parsing, and
push/reply send. **Not** `kotoba-lang/com-line-api` (that repo is an
unrelated clean-room re-implementation of LINE's own backend infrastructure
— this one is a client for the real, hosted LINE Messaging API).

## Modules

```
line-messaging.signature        JVM-only: verify X-Line-Signature (HMAC-SHA256, sync, javax.crypto)
line-messaging.async-signature  cljs-only: same check, async (Web Crypto SubtleCrypto) -- Cloudflare Workers / browser
line-messaging.events           pure .cljc: raw webhook JSON -> normalized text-message events
line-messaging.client           portable .cljc, DI'd I/O: push! / reply!
```

## Usage

```clojure
;; Verifying an inbound webhook (JVM)
(require '[line-messaging.signature :as sig])
(sig/valid-signature? channel-secret raw-request-body (get headers "x-line-signature"))

;; Verifying an inbound webhook (Cloudflare Worker / browser, cljs)
(require '[line-messaging.async-signature :as async-sig])
(-> (async-sig/valid-signature? channel-secret raw-body x-line-signature)
    (.then (fn [ok?] ...)))

;; Parsing a verified webhook body
(require '[line-messaging.events :as ev])
(ev/text-message-events decoded-body) ;=> [{:type :line-text :user-id .. :reply-token .. :text .. :ts ..} ...]

;; Sending
(require '[line-messaging.client :as line])
(def io {:http-fn my-http-fn :json-write my-json-write :json-read my-json-read
         :creds {:channel-access-token "..."}})
(line/push! io {:to user-id :body "hello"})       ; no expiry, uses push quota
(line/reply! io {:reply-token rt :body "hello"})  ; free, expires ~1 min after the webhook
```

`channel-secret` (webhook verification) and `channel-access-token` (send) are
two different values from the same LINE Developers Console → Messaging API
channel page — do not conflate them. Neither is acquired by this library;
callers resolve them from env/secrets.

## Testing

```bash
kbb -M:test   # signature.cljc + events.cljc + client.cljc (JVM)
kbb -M:lint
```

`async-signature.cljs` has no JVM-runnable test here (Web Crypto isn't
available under `kbb -M`); it's exercised by its consumer's own
integration test (a real Cloudflare Worker webhook route).
