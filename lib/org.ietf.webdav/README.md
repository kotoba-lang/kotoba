# org-ietf-webdav

[![CI](https://github.com/kotoba-lang/org-ietf-webdav/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-ietf-webdav/actions/workflows/ci.yml)

**WebDAV (IETF RFC 4918) surface projected onto
[kotobase](https://github.com/kotoba-lang/kotobase)** — the same
one-datom/document/block plane
[`kotobase-protocols`](https://github.com/kotoba-lang/kotobase-protocols)'s
`s3`/`ipfs`/`atproto`/`git` surfaces use, as its own repo per
`com-junkawasaki/root` ADR-2607172210 (protocol-layer extension;
addressing contract: the Kotoba Resource Protocol §16.1,
`90-docs/protocols/kotoba-resource-protocol.edn`).

The handler is a **pure cljc function** over the injected
`kotobase.store/IStore` — the same seam that lets an app run standalone on
`kotobase.local/LocalStore` or against `kotobase.net`. No I/O, no host XML
parser, no crypto dependencies live here; deploy shells (Cloudflare Worker,
browser worker, fleet peer) own transport and authentication.

| Namespace | Protocol subset (v0.1) | KRP identity |
|---|---|---|
| `kotobase.protocols.webdav` | `OPTIONS`/`GET`/`PUT`/`DELETE`/`HEAD`/`PROPFIND` (Depth 0/1)/`MKCOL` | §16.1 Name (+ `:webdav/collection?` flag) |

`src/kotobase/protocols/http.cljk` (ring-shaped request/response plumbing) is
vendored byte-for-byte from `kotoba-lang/kotobase-protocols` per
ADR-2607172210 — this repo has no runtime dependency on
`kotobase-protocols`, only on `kotobase` itself (the `IStore` seam). Update
it by re-vendoring from upstream, not by independent edits.

```clojure
(require '[kotobase.local :as local]
         '[kotobase.protocols.webdav :as webdav])

(def ctx {:store (local/local-store) :now "2026-07-17T00:00:00Z"})

(webdav/handle ctx {:method :mkcol :path "/share/assets"})
;; => {:status 201 ...}

(webdav/handle ctx {:method :put :path "/share/assets/rifle.glb"
                    :headers {"content-type" "model/gltf-binary"}
                    :body "..."})
;; => {:status 201 ...}

(webdav/handle ctx {:method :propfind :path "/share/assets"
                    :headers {"depth" "1"}})
;; => {:status 207 :body "<?xml ...><D:multistatus xmlns:D=\"DAV:\">...
```

## Storage mapping

One IStore collection per **share** (analogous to S3's bucket), keyed by
path, storing `{:bytes :content-type :webdav/collection? bool
:last-modified}`. `MKCOL` creates a doc with `:webdav/collection? true` and
empty bytes; a share's root is always an *implicit* collection (no MKCOL
needed, cannot be created or deleted). `PROPFIND` lists children by
path-prefix (the same pattern `kotobase.protocols.s3`'s `list-objects` uses)
and distinguishes files vs. collections via that flag. `MKCOL`/`PUT` only
require the *immediate* parent to already exist as a collection (filesystem
`mkdir`/`create` semantics — deeper ancestors are not re-checked). `DELETE`
on a collection recursively removes every descendant.

## Scope guards (read before extending)

- **Implemented (v0.1, per ADR-2607172210)**: `OPTIONS`, `GET`, `PUT`,
  `DELETE`, `HEAD`, `PROPFIND` (Depth 0 and Depth 1 only — Depth: infinity is
  rejected with 403), `MKCOL`. `PROPFIND` reports only `<D:href>`,
  `<D:getcontentlength>`, `<D:getcontenttype>`, and `<D:resourcetype>`
  (`<D:collection/>` when applicable) — no other DAV live property.
- **Explicitly out of scope for v0.1** (same discipline as
  `kotobase.protocols.s3`'s SigV4/multipart/versioning carve-out):
  - `LOCK` / `UNLOCK` — no lock tokens, no `If:` header enforcement; every
    write in this handler is unconditional.
  - `COPY` / `MOVE`.
  - `PROPPATCH` — no custom/dead property storage.
  - Binary bodies — string body only, same v0.1 constraint as
    `kotobase.protocols.http`; an explicit, deliberate follow-up.
  - Authentication (Basic/Digest/bearer) — the deploy shell owns auth,
    exactly as CACAO verification lives in the kotobase.net Worker, not in
    the engine.
- **Namespace stays `kotobase.protocols.webdav`** even though this library
  lives in its own repo (not inside `kotobase-protocols`) — kept consistent
  with the family for a possible future re-homing (ADR-2607172210 decided
  per-protocol repos for WebDAV/OCI/Nostr/SFTP, unlike the IPFS Pinning
  Service API which stayed inside `kotobase-protocols` as an incremental
  extension of already-shared block space).

## Develop / test

First-class runtime is **nbb/cljs** (repo-wide runtime priority: `kotoba
wasm` > `clojurewasm` > ClojureScript > nbb > (jvm/bb)):

```bash
git clone https://github.com/kotoba-lang/kotobase .deps/kotobase
kbb --backend sci --classpath "src:test:.deps/kotobase/src" bin/run_tests.cljk
```

The `:test` alias in `deps.edn` is the JVM **compat** suite only (via
`cognitect-labs/test-runner`), not the primary execution path.

## License

Apache-2.0
