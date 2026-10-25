# com-linkedin

LinkedIn **Posts API** client — portable `.cljc`, I/O injected
(`:http-fn` / `:json-write` / `:json-read` / `:creds`). No dependencies.

Posts, image upload, and chunked video upload with finalization.

## Three headers that are not optional

LinkedIn's REST surface is versioned **per request**, not per URL:

```
LinkedIn-Version: 202506
X-Restli-Protocol-Version: 2.0.0
Authorization: Bearer ...
```

Omitting either of the first two gets a 426 or a 400 that reads like an auth
problem. `:linkedin-version` is therefore a **required credential**, not a
default this library picks — a client that chooses the version for you breaks on
LinkedIn's schedule rather than yours.

## The post id is in a header

`POST /rest/posts` returns 201 with an **empty body**; the URN is in the
`x-restli-id` response header. Reading the body gets you nothing and looks like a
silent failure. Header lookup here is case-insensitive, because HTTP clients
disagree on case and a miss reads as "the post failed".

```clojure
(require '[linkedin.client :as li])

(li/create-post! io {:author "urn:li:person:abc"
                     :commentary "朝の商店街\n\nhttps://aozora.app/videos/ep-001"})
;; => "urn:li:share:7000"
```

Media is two-phase: `initialize-image-upload!` / `initialize-video-upload!` hand
back a **pre-signed** URL. `upload-bytes!` deliberately sends no `Authorization`
header to it — some CDNs reject the request if you do. Video finalization needs
each chunk's ETag echoed back **in order**.

## Test

```bash
kbb --backend sci run_tests.cljk     # primary
kbb -M:test        # JVM, secondary
```

8 tests / 15 assertions, green on both.
