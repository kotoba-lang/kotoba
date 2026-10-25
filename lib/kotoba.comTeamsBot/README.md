# com-teams-bot

Minimal [Bot Framework Connector API](https://learn.microsoft.com/en-us/azure/bot-service/rest-api/bot-framework-rest-connector-api-reference)
client for Microsoft Teams — OAuth2 client-credentials token acquisition +
send + inbound Activity parsing + JWT webhook verification. Portable
`.cljc` where possible, same DI conventions as
`kotoba-lang/com-line-messaging` / `kotoba-lang/com-viber-bot`.

## Modules

```
teams.jwt          pure .cljc: JWT structural parsing (base64url decode) + iss/aud/exp/nbf claims validation, no crypto
teams.jwt-verify    cljs-only: RS256 signature verification (Web Crypto) + Bot Framework JWKS fetch
teams.events        pure .cljc: one decoded Activity -> a normalized text-message event (or nil)
teams.client        portable .cljc, DI'd I/O: OAuth2 fetch-token! + send-message!
```

## Auth is structurally different from every other client in this workspace

There is **no static bot token**. `fetch-token!` exchanges your Azure AD
App Registration's `app-id`/`app-password` for a short-lived (~1 hour)
OAuth2 access token, which `send-message!` then uses as a Bearer token.
This library does **not** cache or auto-refresh the token — that's caller
state (like `channels.discord`'s `:after-id` cursor), not something a
stateless client library should own.

## Send has no fixed endpoint

Unlike every other channel, Teams' send endpoint is `{service-url}/v3/
conversations/{conversation-id}/activities` — both `service-url` and
`conversation-id` come from the *inbound* Activity you're replying to
(`teams.events`' `:service-url`/`:conversation-id`), not a fixed URL.

## Webhook verification: honestly unverified against live Microsoft infra

`teams.jwt-verify` implements RS256 JWT signature verification against a
fetched Bot Framework JWKS, per Microsoft's published auth docs — but
**this code has never been run against a real Bot Framework token
issuer** (no deployed bot exists yet to generate a real signed JWT). Every
other webhook signature scheme in this workspace (Meta, LINE, Viber) is
symmetric HMAC, exercised against self-generated known-answer test
vectors; RS256 verification against a third party's live public keys
can't be exercised the same way without an actual Azure Bot deployment.
Treat this module as code-reviewed-correct-per-spec, not
field-verified, until it's run against a real bot.

## Usage

```clojure
;; Getting a token and sending
(require '[teams.client :as t])
(def io {:http-fn my-http-fn :json-write my-json-write :json-read my-json-read
         :creds {:app-id "..." :app-password "..."}})
(def token (t/fetch-token! io))   ; {:access-token :expires-in} -- caller tracks expiry
(t/send-message! io {:service-url service-url :conversation-id conv-id
                      :access-token (:access-token token) :text "hello"})

;; Parsing an inbound Activity (already JSON-decoded)
(require '[teams.events :as ev])
(ev/text-message-event decoded-activity)

;; Verifying the inbound JWT (Cloudflare Worker / browser, cljs)
(require '[teams.jwt :as jwt]
         '[teams.jwt-verify :as jwt-verify])
(-> (jwt-verify/fetch-jwks! my-fetch-fn)
    (.then (fn [jwks] (jwt-verify/verify-signature! raw-jwt-token jwks)))
    (.then (fn [sig-ok?]
             (and sig-ok?
                  (jwt/valid-claims? claims {:expected-issuer "https://api.botframework.com"
                                              :expected-audience my-app-id
                                              :now-epoch-sec (/ (js/Date.now) 1000)})))))
```

## Testing

```bash
kbb -M:test   # jwt.cljc + events.cljc + client.cljc (JVM)
kbb -M:lint
```

`jwt_verify.cljs` has no JVM-runnable test here (Web Crypto isn't
available under `kbb -M`) and, per the caveat above, no live-network
test either — same posture as this workspace's other async-signature
surfaces, one level more honest about what "tested" means here.
