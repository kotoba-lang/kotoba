# com-matrix

Minimal [Matrix Client-Server API](https://spec.matrix.org/latest/client-server-api/)
client — room sync (poll-based) + send. Portable `.cljc`, I/O injected
(`:http-fn` / `:json-write` / `:json-read` / `:creds`), same DI shape as
`kotoba-lang/com-chatwork` / `kotoba-lang/com-mattermost`.

## Usage

```clojure
(require '[matrix.client :as m])

(def io {:http-fn    my-http-fn
         :json-write my-json-write-fn
         :json-read  my-json-read-fn
         :creds      {:base-url "https://matrix.example.com" :access-token "..."}})

(def r1 (m/sync! io {}))                          ; first call: omit :since
(m/sync! io {:since (:next-batch r1)})             ; subsequent calls: pass the cursor back
(m/send-message! io {:room-id "!room:example.com" :text "hello"})
```

Like Mattermost, Matrix is self-hosted/federated — there is no single fixed
API host, so `:creds` also carries `:base-url` (your homeserver URL, e.g.
`https://matrix.org` or a self-hosted Synapse/Dendrite/Conduit deployment).

`:access-token` comes from a Matrix login (interactive password login, or
an admin-issued token). Acquiring it is **out of scope** here — callers
resolve a valid token from env/secrets.

## Poll-based, not Matrix's native long-polling

Matrix's own `/sync` endpoint is designed for long-polling (the request
blocks server-side until something new arrives or a timeout elapses).
`sync!` always passes `timeout=0` instead — a non-blocking call that
returns immediately with whatever's new — because every other channel
adapter in this workspace polls at its own interval on a synchronous
`:http-fn` contract that isn't shaped for a held-open long-poll connection.
A consumer needing genuine real-time push should use Matrix's long-polling
directly — not built here (YAGNI, matches `com-discord-bot`'s
REST-not-Gateway scope cut for the same reason).

## Testing

```bash
kbb -M:test
kbb -M:lint
```
