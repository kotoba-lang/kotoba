# com-instagram

Instagram **Content Publishing API** client — portable `.cljc`, I/O injected
(`:http-fn` / `:json-write` / `:json-read` / `:creds`), the same DI shape as
`kotoba-lang/com-x` and `kotoba-lang/com-youtube`. No dependencies.

## Why this exists

`kotoba-lang/com-meta-webhook` covers Instagram **DMs** (`send-message!`).
Nothing in the workspace could publish a post. This is that gap.

## The thing that surprises people

There is **no byte-upload path**. `POST /{ig-user-id}/media` takes a `video_url`
or `image_url` and Instagram *fetches the asset itself* — so the media must
already be publicly reachable before a post can be created at all. Publishing is
therefore always at least two calls and a wait:

```
create container ──▶ poll until FINISHED ──▶ publish
```

The wait is real: Instagram transcodes video asynchronously, and publishing a
container that is still `IN_PROGRESS` fails.

```clojure
(require '[instagram.client :as ig])

(ig/publish-video! io {:kind :reels
                       :video-url "https://aozora.app/media/ep-001.mp4"
                       :caption "朝の商店街 #machiaruki"}
                   {:sleep-fn my-sleep})   ; no ambient timer in the library
```

`await-container` throws on `ERROR`/`EXPIRED` and on running out of polls —
giving up quietly there looks exactly like a publish that never happened.

## Test

```bash
kbb --backend sci run_tests.cljk     # primary
kbb -M:test        # JVM, secondary
```

6 tests / 16 assertions, green on both.
