# com-mattermost

Minimal [Mattermost REST API v4](https://api.mattermost.com/) client —
channel message list + send. Portable `.cljc`, I/O injected (`:http-fn` /
`:json-write` / `:json-read` / `:creds`), same DI shape as
`kotoba-lang/com-chatwork` / `kotoba-lang/com-discord-bot`.

## Usage

```clojure
(require '[mattermost.client :as mm])

(def io {:http-fn    my-http-fn
         :json-write my-json-write-fn
         :json-read  my-json-read-fn
         :creds      {:base-url "https://mattermost.example.com" :bot-token "..."}})

(mm/list-messages io {:channel-id "..." :since 1721000000000})
(mm/send-message! io {:channel-id "..." :text "hello"})
```

Unlike every other client in this workspace, Mattermost is self-hosted —
there is no single fixed API host, so `:creds` also carries `:base-url`
(your deployment's own server URL).

`:bot-token` is a Personal Access Token or bot account token (System
Console → Integrations → Bot Accounts, or Account Settings → Security →
Personal Access Tokens). Acquiring it is **out of scope** here — callers
resolve a valid token from env/secrets.

## A note on `list-messages`' response shape

Mattermost's `/posts` response is `{:order [id ...] :posts {id {...}}}`
(posts keyed by id, `:order` gives the newest-first sequence) — this
library flattens that into a plain vector. Dynamic map keys like post ids
land as either strings or keywords depending entirely on the caller's
`:json-read` (`:key-fn keyword` vs `:key-fn identity`); `list-messages`
tries the keyword form first (this workspace's own convention) and falls
back to the raw string, so it works either way.

## Testing

```bash
kbb -M:test
kbb -M:lint
```
