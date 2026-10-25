# com-feishu

Portable `.cljc` Feishu/Lark Open Platform client: webhook signature/token
verification (`feishu.signature` JVM, `feishu.async-signature`
Workers/browser), event parsing (`feishu.events`), tenant token + send
(`feishu.client`).

**Never exercised against live Feishu infrastructure** (no deployed
Feishu app exists yet) -- same disclosed-gap posture as this workspace's
`com-teams-bot` (`teams.jwt-verify`). `feishu.signature/token-valid?` is a
plain string compare with no crypto involved, so it's the more
trustworthy verification path if you don't need an Encrypt Key configured.

## Setup

1. Feishu Open Platform Console -> create/open your app -> **Credentials
   & Basic Info** for `app-id`/`app-secret`.
2. **Event Subscription** -> configure your webhook URL, subscribe to
   `im.message.receive_v1`, note the **Verification Token** (and Encrypt
   Key, if you enable payload encryption -- decrypting an encrypted
   payload is out of scope here, see `feishu.signature` docstring).

## Usage

```clojure
(require '[feishu.client :as client]
         '[feishu.events :as events]
         '[feishu.signature :as sig])

;; ingress: verify + parse an inbound webhook POST
(sig/token-valid? configured-token (events/header-token decoded-body))
(events/text-message-event json-read decoded-body)

;; egress: fetch a tenant token, then send
(def io {:http-fn my-http-fn :json-write my-json-write :json-read my-json-read
         :creds {:app-id "..." :app-secret "..."}})
(def token (client/fetch-tenant-access-token! io))
(client/send-message! io {:receive-id "ou_..." :text "hi"
                           :tenant-access-token (:tenant-access-token token)})
```

## Testing

```bash
kbb -M:test
kbb -M:lint
```
