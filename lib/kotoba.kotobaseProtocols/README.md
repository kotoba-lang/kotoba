# kotobase-protocols

[![CI](https://github.com/kotoba-lang/kotobase-protocols/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/kotobase-protocols/actions/workflows/ci.yml)

**Storage / protocol surfaces projected onto [kotobase](https://github.com/kotoba-lang/kotobase)**
— one datom/document/block plane, five wire protocols
(ADR-2607171700 + ADR-2607172210 in `com-junkawasaki/root`; addressing
contract: the Kotoba Resource Protocol,
`90-docs/protocols/kotoba-resource-protocol.edn`).

Every surface is a **pure cljc handler** over the injected
`kotobase.store/IStore` — the same seam that lets an app run standalone on
`kotobase.local/LocalStore` or against `kotobase.net`. No I/O, no host JSON,
no crypto dependencies live here; deploy shells (Cloudflare Worker, browser
worker, fleet peer) own transport and authentication, exactly as
`kotobase-cljc-worker` / `kotobase-browser-worker` rebind the kotobase engine.

| Surface | Namespace | Protocol subset (v0.1) | KRP identity |
|---|---|---|---|
| `s3.<apex>` | `kotobase.protocols.s3` | PUT/GET/HEAD/DELETE object, ListObjectsV2 | §3.4 Location |
| `ipfs.<apex>` | `kotobase.protocols.ipfs` | GET/HEAD `/ipfs/{cid}` (read-only gateway) | §3.3 Content |
| `pinning.<apex>` | `kotobase.protocols.ipfs-pinning` | [IPFS Pinning Service API](https://ipfs.github.io/pinning-services-api-spec/): `POST/GET /pins`, `GET/DELETE /pins/{requestid}` | §3.3 Content |
| `atproto.<apex>` | `kotobase.protocols.atproto` | XRPC `com.atproto.repo.{get,put,delete,list}Record*`, `sync.getBlob` | §3.2 Record |
| `git.<apex>` | `kotobase.protocols.git` | dumb-HTTP fetch plus signed `git-remote-kotobase` push | §3.1/§3.4 |

`kotobase.protocols.router` dispatches by subdomain (`s3.kotobase.net`, …)
with a single-origin path-prefix fallback (`/s3/*`, `/xrpc/*`, `/ipfs/*`,
`/pins*`, `/git/*`), apex injectable for self-hosted peers.

### IPFS Pinning Service API (`pinning.<apex>` / `ipfs-pinning.cljc`)

Extends the same shared block space `ipfs.cljc` already serves read-only
(ADR-2607172210 — this stays inside `kotobase-protocols` rather than
becoming a 4th IPFS-adjacent repo, since three homes for this exact block
space already exist: this repo's `ipfs.cljc` gateway, the general
`kotoba-lang/ipfs` implementation library, and the public product surface
`gftdcojp/net-kotobase-ipfs`). Mounted on its own `pinning` subdomain rather
than folded into `ipfs`'s — see the routing note at the top of `router.cljc`
for why: `ipfs.cljc` is documented READ-ONLY BY DESIGN, and a write-capable
API deserves its own host/auth boundary rather than blurring that
invariant.

**Honest limitation, read before using**: v0.1 has **no background pinning
daemon**. `POST /pins` decides the outcome synchronously, at request time,
by checking whether the block is already present locally
(`blocks/get-block`):

- block present  → `status: "pinned"` immediately.
- block missing  → `status: "failed"` immediately, with an `info.reason`
  explaining why — **not** `"queued"`. The `origins` field is accepted and
  stored (API-shape compatible) but never dialed; there is no peer fetch,
  no retry, no background worker that could ever complete a queued
  request. If you need a pin to succeed, `blocks/put-block!` the CID first
  (inside an authenticated deploy shell, same as `ipfs.cljc`'s own write
  path), then `POST /pins`.

`DELETE /pins/{requestid}` removes the pin *request* only — the underlying
block is untouched, since multiple pin requests may reference the same
block (same content-addressed dedup principle as `blocks.cljc`).

Every recognized protocol subdomain also answers `GET /health` with a
no-store EDN status document. This is the deploy-shell readiness boundary;
it proves routing and handler availability, not backing-store durability.

```clojure
(require '[kotobase.local :as local]
         '[kotobase.protocols.router :as router])

(def ctx {:store (local/local-store) :apex "kotobase.net"})

(router/handle ctx {:method :put :host "s3.kotobase.net"
                    :path "/media/hello.txt" :body "hello"})
;; => {:status 200 :headers {"etag" "\"…\""} :body nil}

(router/handle ctx {:method :get :host "s3.kotobase.net"
                    :path "/media/hello.txt"})
;; => {:status 200 … :body "hello"}
```

## The block plane: bytes do not belong on the datom plane (ADR-2608039970)

`ctx` may carry a **block port**, and when it does, block bytes go there
instead of into the `IStore` document collection:

```clojure
(def ctx {:store  store            ; documents, metadata, audit — unchanged
          :blocks {:get  (fn [cid] block-or-nil)
                   :put! (fn [cid block] _)
                   :list (fn [] [cid ...])}
          :cid-of (fn [block] "bafkrei…")})   ; optional verification
```

**Why.** A block stored as a document is a document *value*, and in
`kotobase-protocols-worker` a document value is encoded as a datom
(`"doc/val" (pr-str v)`) on the prolly-tree chain — so a 5 MB object body
becomes datoms. The measured cost of that route is the **4 MiB ceiling on
`PUT /ipfs/:cid`** (superproject ADR-2607175000, ADR-2608012600 D4).

**Without `:blocks`, behaviour is exactly what it was** — the document
collection. That is deliberate: `kotobase-protocols-worker` is live, and a
port it has not adopted yet must not change what it does. `(blocks/put-block!
store cid block)` with a bare `IStore` still works and is still tested.

This port is deliberately **not** `kotobase.storage/IBlockStore`: these
handlers are synchronous by contract and that protocol is batch and
Promise-returning on cljs — the same wall the worker's `kotobase-store`
namespace documents when it explains why it hydrates *before* the router
runs. A shell needing async reads prefetches, as it already does for
documents.

### `:cid-of` — verification is the plane's job

When present, every read and every write checks the block against the CID it
is keyed by, and a mismatch **throws** `:kotobase.protocols/cid-mismatch`.
This closes the v0.1 "trusts the caller-supplied CID" gap.

- It takes the **whole block**, not `:bytes` — only the shell knows what the
  CID was computed over (`POST /ipfs` hashes the *raw* body and stores
  `:encoding "base64"`). The shell owns the encoding convention; the library
  owns the invariant.
- A mismatch **throws** rather than reading as absent, for the reason
  `kotobase.storage.verify` gives: omitting a tampered block turns a corrupt
  store into a *shorter answer* — bytes quietly gone, looking exactly like a
  cache miss. A miss is still `nil`; absence and corruption are different
  answers.
- **Without `:cid-of` nothing is verified.** That is what this library did
  unconditionally before, and it is now a question a deployment can be asked.

## Scope guards (read before extending)

- **`ipfs.kotobase.net` (the public route) is owned by
  `gftdcojp/net-kotobase-ipfs`** (ADR-2607072000). This repo's gateway is the
  portable/self-hosted equivalent; it is non-authoritative for that hostname.
- **The atproto surface is the tenant data-plane, not a social PDS.** The
  aozora.app consolidation (ADR-2607062200) is untouched: no `app.bsky.*`,
  no firehose, no handle resolution.
- **git-journal primacy stands** (ADR-2607072300): an actor repo's git
  history remains the primary source of its public data; this repo makes
  kotobase *servable over git's protocol*, it does not invert that ADR.
- **ETags/fingerprints are not CIDs** (KRP §3.3). Real content addressing
  (blake3/CIDv1 via kotoba multiformats) is a declared follow-up; blocks are
  stored under caller-computed CIDs.

## Develop / test

First-class runtime is **nbb/cljs** (repo-wide runtime priority):

```bash
git clone https://github.com/kotoba-lang/kotobase .deps/kotobase
kbb --backend sci --classpath "src:test:.deps/kotobase/src" bin/run_tests.cljk
```

The `:test` alias in `deps.edn` is the JVM **compat** suite only.

## Cloudflare deploy shell

`worker/git-worker.mjs` is the host-only transport/persistence adapter for
`git.kotobase.net`. D1 performs compare-and-set ref transactions and R2 stores
verified Git loose objects by content identity. Before D1 adopts a ref, the
helper commits its signed-ref datoms to the actor's CACAO-authorized Kotobase
graph and the Worker independently reads them back with the same short-lived
capability. D1 is the compare-and-set serving mirror, not the only authority.
`bin/git-remote-kotobase.mjs`
provides the Git remote-helper protocol, so ordinary `git push` uploads the
reachable object graph and advances a ref. Every write has a replay-protected
Ed25519 request signature; every ref update additionally carries the exact
RID/ref/commit/timestamp signed-ref tuple defined by `nekko.sigref`. Request
signatures bind the sigref, graph CID, Kotobase commit CID and a CACAO digest;
the capability itself is never persisted in audit records. Server-side
ancestry traversal enforces bonsai fast-forward policy across multi-commit
pushes. Force and delete updates are rejected by both the helper and authority.

Set `KOTOBASE_GIT_PRIVATE_KEY` to an Ed25519 PKCS8 PEM (literal newlines or
escaped `\\n`) or base64 DER and make this package's `bin/` available on PATH:

```bash
git remote add origin kotobase::https://git.kotobase.net/org/repo
git push origin main:refs/heads/main
```

Deployments must use the superproject resource guard.

## License

Apache-2.0
