# com-x

Minimal [X (Twitter) API v2](https://developer.x.com/en/docs/x-api) client —
mentions search, DM read/write, tweet reply. Portable `.cljc`, I/O injected
(`:http-fn` / `:json-write` / `:json-read` / `:creds`), same DI shape as
`kotoba-lang/com-chatwork` / `tayori.channel.slack`.

## Usage

```clojure
(require '[x.client :as x])

(def io {:http-fn    my-http-fn
         :json-write my-json-write-fn
         :json-read  my-json-read-fn
         :creds      {:bearer-token "..."}})

(x/search-recent-mentions io {:handle "your_handle"}) ; App-only token OK
(x/list-dm-events io)                                 ; needs User-context token (dm.read)
(x/reply-tweet! io {:tweet-id "123" :text "thanks!"})
(x/send-dm! io {:participant-id "456" :text "hey"})
```

## Auth — two different token shapes, this library doesn't distinguish them

- **App-only** (OAuth 2.0 Client Credentials): works for `search-recent-mentions`
  (public data).
- **User-context** (OAuth 2.0 Authorization Code + PKCE, scopes `dm.read` /
  `dm.write` / `tweet.write`): required for `list-dm-events`, `send-dm!`,
  `reply-tweet!` — a DM is private to the authenticated user, no App-only
  token can read or send it.

Acquiring either token — the developer app registration, the PKCE
authorize/callback/refresh flow — is **out of scope** for this library (same
non-goal `com-gmail` documents for its own Bearer token). Callers resolve a
valid token from env/secrets and pass it in `:creds`.

## Cost

Meaningful read access (mentions search beyond a trivial sandbox quota, any
DM access at all) requires a **paid X API tier** (Basic, $200/mo or higher as
of this writing) — this library doesn't change that economics, it only
avoids re-deriving the HTTP calls once a tier is purchased.

## Testing

```bash
kbb -M:test
kbb -M:lint
```
