# com-youtube

Portable (`.cljc`) YouTube Data API v3 upload client -- OAuth2 refresh-token
exchange, resumable `videos.insert`/`videos.update`, `captions.insert`,
`thumbnails.set`. One tested auth/HTTP boundary, injectable transport, for
any kotoba-lang/gftdcojp project that needs to publish video to YouTube
instead of re-deriving the resumable-upload/multipart-caption boilerplate
ad hoc.

## Why this exists

`kotoba-lang/youtube-upload` already extracted a real, working Python
client from `ai-gftd-project-yukkuri`'s `lg_yukkuri/graphs/upload_youtube.py`
-- and its own README explicitly recommends wrapping it (RPC/subprocess
bridge) rather than rewriting the HTTP logic in Clojure. This repo is that
rewrite anyway, by explicit request, so `yukkuri`'s new `.cljc` graph
namespaces (`upload_youtube.cljc`/`publish_youtube.cljc`, which only build
request-body *plans*, no execution) have a real, same-ecosystem library to
call instead of bridging into a separate Python process. It re-derives the
exact same request/response shapes as `client.py` (same header names,
status-code checks, multipart boundary format) rather than reinventing the
API from scratch.

## Design

```text
youtube.client      -- OAuth2 token exchange + HTTP (injectable :http-fn) + JSON helpers
youtube.videos      -- resumable videos.insert (init POST + PUT bytes), videos.update
youtube.captions    -- captions.insert (multipart/related SRT upload)
youtube.thumbnails  -- thumbnails.set (raw PNG POST)
```

Request/response shaping (metadata bodies, multipart body construction,
header maps) is pure `.cljc` and **runs on both Clojure and ClojureScript**
(JSON, form encoding, byte handling and the multipart body are all reader-
conditional). The transport is the one thing not shared: java.net.http is
the JVM default and cljs has no default on purpose (this library's contract
is a *synchronous* http-fn and JS has no synchronous fetch — cljs callers
inject their own; nbb operators drive `curl` through execFileSync) but every function takes an injectable `:http-fn`
(`{:url :method :headers :body} -> {:status :body :response-headers}`, the
same convention `kotoba-lang/com-cloudflare` uses) -- every namespace here
is tested with a stub, never only against a live account. `:body` may be a
String or a JVM byte array (video/PNG/SRT bytes); the default transport
dispatches on type.

**Credentials are never held or defaulted by this library.** Callers pass
`:client-id`/`:client-secret`/`:refresh-token`/an already-fetched
`access-token` explicitly -- mirrors
`ai-gftd-project-yukkuri/docs/youtube-upload-setup.md`'s policy that these
are operator-injected (Google Cloud OAuth client + refresh token the
channel owner mints once), never code-held or committed.

## Usage

```clojure
(require '[youtube.client :as client]
         '[youtube.videos :as videos]
         '[youtube.captions :as captions]
         '[youtube.thumbnails :as thumbnails])

(def access-token
  (client/refresh-access-token! {:client-id "..." :client-secret "..." :refresh-token "..."}))

(def video-id
  (videos/insert-video! access-token video-bytes
    (videos/video-metadata {:title "..." :description "..." :tags ["yukkuri" "cyber"]
                            :category-id "27" :default-language "ja" :privacy-status "unlisted"})))

(captions/insert-caption! access-token {:youtube-video-id video-id :lang "ja" :name "日本語"} srt-bytes)
(thumbnails/set-thumbnail! access-token video-id png-bytes)
```

## Testing without a live account

```clojure
(def calls (atom []))
(def stub-http-fn (fn [req] (swap! calls conj req) {:status 200 :body "{...}" :response-headers {}}))
(videos/insert-video! "tok" video-bytes metadata {:http-fn stub-http-fn})
```

Run tests:

```sh
kbb -M:test
```
