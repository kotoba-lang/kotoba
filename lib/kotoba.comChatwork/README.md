# com-chatwork

Minimal [Chatwork API v2](https://developer.chatwork.com/reference) client —
room message list + send, the two operations a channel ingress/egress adapter
needs. Portable `.cljc`, I/O injected (`:http-fn` / `:json-write` /
`:json-read` / `:creds`), same DI shape as `kotoba-lang/tayori`'s
`tayori.channel.slack`.

## Usage

```clojure
(require '[chatwork.client :as cw])

(def io {:http-fn    my-http-fn        ; (fn [{:keys [url method headers body]}]) -> {:status :body}
         :json-write my-json-write-fn
         :json-read  my-json-read-fn
         :creds      {:api-token "..."}})

(cw/list-messages io {:room-id 123456789 :force? true})
(cw/send-message! io {:room-id 123456789 :body "hello"})
(cw/me io)
```

`:api-token` is a Chatwork personal/room API token (Chatwork has no bot/OAuth
app concept for simple room read/post — see My Profile → API Token in the
Chatwork web UI). Not committed here; consumers resolve it from env/secrets
(see `kotoba-lang/tayori`'s `:creds` convention).

## Scope

Message list + send only — extend `src/chatwork/client.cljc` if a consumer
needs more of the API surface (tasks, files, members, ...).

## Testing

```bash
kbb -M:test
kbb -M:lint
```
