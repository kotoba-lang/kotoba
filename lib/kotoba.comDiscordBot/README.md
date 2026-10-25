# com-discord-bot

Minimal [Discord Bot API](https://discord.com/developers/docs/reference)
client — channel message list + send. Portable `.cljc`, I/O injected
(`:http-fn` / `:json-write` / `:json-read` / `:creds`), same DI shape as
`kotoba-lang/com-chatwork` / `kotoba-lang/com-x`.

**Not `kotoba-lang/com-discord`** — that repo is an unrelated clean-room
re-implementation of the Discord platform's own backend infrastructure
(same naming trap as `com-line-api` vs `com-line-messaging`). This one is a
client for the real, hosted Discord Bot API.

## Usage

```clojure
(require '[discord.client :as d])

(def io {:http-fn    my-http-fn
         :json-write my-json-write-fn
         :json-read  my-json-read-fn
         :creds      {:bot-token "..."}})

(d/list-messages io {:channel-id "123456789" :after "999" :limit 50})
(d/send-message! io {:channel-id "123456789" :text "hello"})
```

`:bot-token` is a bot application token from the Discord Developer Portal →
your application → Bot → Token. Creating the application, inviting the bot
to a server with the right OAuth2 scopes/permissions, and issuing the token
are all **out of scope** here (same non-goal `com-gmail`/`com-x` document
for their own tokens) — callers resolve a valid token from env/secrets.

## Scope: REST polling, not the Gateway

Discord bots more commonly use the persistent Gateway WebSocket for
real-time delivery. This library deliberately uses REST polling
(`GET .../messages`) instead, matching the poll-based `gw/Channel` shape
every other channel adapter in this workspace already uses
(`chatwork.client`/`x.client`), and avoiding the Gateway's own complexity
(persistent connection, heartbeats, sharding) for a personal-scale
single-channel watch. A consumer needing real-time delivery or
multi-channel/multi-guild scale should use the Gateway instead — not built
here.

## Testing

```bash
kbb -M:test
kbb -M:lint
```
