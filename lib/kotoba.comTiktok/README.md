# com-tiktok

TikTok **Content Posting API** client — portable `.cljc`, I/O injected
(`:http-fn` / `:json-write` / `:json-read` / `:creds`). No dependencies.

## Two source modes, and why both are here

- **`PULL_FROM_URL`** — hand TikTok a URL and let it fetch. One call, but the
  URL's domain must be verified in the developer console first.
- **`FILE_UPLOAD`** — get an upload URL and push bytes. Works without domain
  verification, but it is a three-step flow.

Neither is a superset of the other, so a client implementing only one would be
unusable for half its callers.

## Init does not mean posted

Both modes return a `publish_id` immediately and finish **asynchronously**. A
caller that treats a successful init as a successful post will report publishes
that never appeared.

```clojure
(require '[tiktok.client :as tt])

(let [pid (tt/init-pull-from-url! io {:title "朝の商店街 #machiaruki"
                                      :video-url "https://aozora.app/media/ep-001.mp4"
                                      :privacy-level "SELF_ONLY"})]
  (tt/await-publish io pid {:sleep-fn my-sleep}))
```

Two traps this client handles for you: TikTok answers **200 with an error body**
for application-level failures, so HTTP status alone is not a success test; and
`Content-Range` is mandatory on chunk uploads even when there is only one chunk.
`post-info` rejects an unknown `privacy_level` locally rather than letting it
come back as an opaque API error, and defaults to `SELF_ONLY`.

## Test

```bash
kbb --backend sci run_tests.cljk     # primary
kbb -M:test        # JVM, secondary
```

7 tests / 12 assertions, green on both.
