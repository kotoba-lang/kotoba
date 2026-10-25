# com-google-chat

Portable `.cljc` Google Chat client: **send-only**, via an Incoming
Webhook URL. No polling/reading counterpart -- see `src/google_chat/client.cljk`
for why (Google Chat's inbound path needs a Workspace Marketplace app
registration + Google-issued JWT verification, and its full REST send API
needs service-account JWT *signing*; both are disproportionate for a
notification channel).

## Setup

1. In Google Chat, open (or create) a space -> space settings -> **Apps &
   integrations** -> **Add webhook**. Copy the generated URL (it already
   carries `key`/`token` query params -- no separate auth header needed).
2. Configure that URL as `:webhook-url` when calling `send-message!`.

## Usage

```clojure
(require '[google-chat.client :as client])

(client/send-message!
 {:http-fn    my-http-fn      ; (fn [{:keys [url method headers body]}]) -> {:status :body}
  :json-write my-json-write   ; edn -> json string
  :json-read  my-json-read    ; json string -> edn
  :webhook-url "https://chat.googleapis.com/v1/spaces/AAAA/messages?key=...&token=..."}
 "hello from manimani")
```

## Testing

```bash
kbb -M:test
kbb -M:lint
```

## Connector

`google-chat.connector` is `google-chat.client` given a descriptor — one tool,
`google_chat_post_message`, write-only. The scope decision above still holds:
there is no read counterpart, and `connector.model/read-only` on this
descriptor leaves nothing, which is the honest answer for a webhook.

**The webhook URL is the credential.** It arrives from Google already carrying
`key` and `token`, and there is no header to authenticate with. Modelling that
as a bearer token would be wrong twice: an Authorization header Google ignores,
and the URL — the actual secret — sitting in a descriptor a connector catalog
can print. The connector plane grew a `:url-credential` profile for this:
`request` returns `:connector.http/url-from-credential`, and `connector.invoke`
fills the URL in from the host's token store. There is a test asserting the
descriptor contains no `chat.googleapis.com` string at all.

Threading asks for `messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD`
explicitly: without it Google Chat treats `threadKey` as a hint and silently
starts a new thread when it does not recognise the key.

```sh
kbb --backend sci --classpath "src:test:../connector/src" run-connector-tests.cljk   # 8 tests, 19 assertions
kbb --backend sci --classpath "src:../connector/src" emit-connector-edn.cljk
```
