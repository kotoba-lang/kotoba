# com-vimeo-upload

Vimeo video upload (**tus** resumable) — portable `.cljc`, I/O injected
(`:http-fn` / `:json-write` / `:json-read` / `:creds`). No dependencies.

## Why not `kotoba-lang/com-vimeo`

That repository is a **clean-room, API-compatible actor** — it *answers* Vimeo's
shape, it does not call Vimeo. Putting a real outbound client inside it would
mean one repository both serving and consuming the same API. Hence the role
suffix, per the workspace's naming rule for when the short name is taken.

## tus, in three moves

```
POST /me/videos {upload:{approach:"tus", size:N}}   -> upload_link
PATCH <upload_link>  (Upload-Offset, offset+octet-stream)  -> new offset
HEAD  <upload_link>  -> current offset, to resume after a failure
```

The resumability is the point: a 2 GB upload that dies at 80% resumes from
`upload-offset` instead of starting over.

```clojure
(require '[vimeo-upload.client :as vm])

(vm/upload-file! io {:name "朝の商店街" :description "..." :size 8000000}
                 video-bytes {:chunk-size 52428800})
```

`upload-file!` loops on the **server's** reported offset rather than a local
counter — that is what makes a resumed upload correct instead of merely
restarted — and throws if an offset fails to advance, because looping forever on
a stuck server is worse than failing.

Two details worth knowing: Vimeo versions its API through `Accept`
(`application/vnd.vimeo.*+json;version=3.4`), not the URL; and `size` is not
negotiable — tus allocates against it, so a mismatch fails at the *end* of the
upload rather than the start.

## Test

```bash
kbb --backend sci run_tests.cljk     # primary
kbb -M:test        # JVM, secondary
```

6 tests / 15 assertions, green on both.
