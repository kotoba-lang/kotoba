# storj

`storj.*` — a **Storj** client for the kotoba-lang stack: signed S3 operations
against Gateway-MT, presigned URLs, and public Linksharing URLs, as **portable
`.cljc` over injected crypto and transport**.

Companion to [`io-ipfs`](https://github.com/kotoba-lang/io-ipfs),
[`io-ipld`](https://github.com/kotoba-lang/io-ipld) and
[`tech-ipfs-specs-ipns`](https://github.com/kotoba-lang/tech-ipfs-specs-ipns):
those cover content addressing, this covers durable erasure-coded storage behind
an S3 surface.

| Namespace | What it owns |
|---|---|
| `storj.gateway` | Storj-specific config: endpoints, defaults, validation. |
| `storj.core` | Signed requests and object operations over injected `ICrypto` + `IHttp`. |
| `storj.linkshare` | Public Linksharing URL construction. |
| `storj.protocols` | The transport seam: `IHttp`. |

AWS SigV4 itself is [`kotoba-lang/sigv4`](https://github.com/kotoba-lang/sigv4)
— shared with the other seven places in this workspace that sign S3 requests.
`sigv4.crypto` supplies the default `ICrypto`.

## Usage

```clojure
(require '[storj.core :as storj]
         '[sigv4.crypto :as crypto])

(def client
  (storj/client {:bucket     "my-bucket"
                 :access-key "jw…"        ; Storj S3 access key
                 :secret-key "…"}         ; Storj S3 secret key
                {:crypto (crypto/crypto)
                 :http   my-http}))       ; your IHttp impl

(storj/put-object client {:key "docs/readme.txt"
                          :body "hello storj"
                          :content-type "text/plain"
                          :now (str (java.time.Instant/now))})

(storj/get-object client {:key "docs/readme.txt" :now now})   ; nil on 404
(storj/head-object client {:key "docs/readme.txt" :now now})
(storj/delete-object client {:key "docs/readme.txt" :now now})

(-> (storj/list-objects client {:prefix "docs/" :now now})
    :body
    storj/parse-list-result)
;; => {:keys ["docs/readme.txt"] :common-prefixes [] :truncated? false …}

(storj/presign client {:key "docs/readme.txt" :now now :expires-seconds 900})
;; => "https://gateway.storjshare.io/my-bucket/docs/readme.txt?X-Amz-…"
```

Public assets go through Linksharing instead — no signature, no credentials on
the wire:

```clojure
(require '[storj.linkshare :as ls])
(ls/raw-url {:access-key "jw…" :bucket "assets" :key "img/logo.png"})
;; => "https://link.storjshare.io/raw/jw…/assets/img/logo.png"
```

## Bytes by reference

`storj.core` is shaped for S3 — keys, ranges, content types, response maps,
404 as a status. A consumer that only wants bytes by reference has to
translate all of it, and every one of them translates it slightly
differently: some cannot tell *this object is gone* from *this request
failed*.

`storj.store` does that translation once and returns a plain map of four
functions:

```clojure
(store/store-fns client {:now #(iso-instant) :prefix "drive/acme/"})
;; {:get-object f :put-object f :delete-object f :exists? f}
```

Nothing in it names a consumer. `kotoba-lang/drive`'s `drive.object/store-of`
takes exactly this shape, and neither library depends on the other — whoever
builds the store depends on both, and that is the application.

Three things it settles at the edge rather than at every call site:

- **A 404 is `nil`, and an empty object is `[]`.** Pulling `:body` before that
  distinction makes them the same answer, and a consumer deciding whether its
  own records are wrong needs to tell them apart.
- **Bytes are a vector of unsigned ints, both ways.** The signer hashes a byte
  array; every byte handler in this workspace passes vectors. Connecting the
  two without converting throws out of the crypto layer, which is how this was
  found.
- **A clock is required rather than defaulted.** `sign` reads no clock on
  purpose — a signer that took the time from the machine could not be checked
  against AWS's fixed vectors — and defaulting to one here would undo that a
  layer up.

On a JVM these return values; in a browser they return promises, because
`then` is identity application on one and `.then` on the other. A consumer
whose own interface is synchronous can use them directly on a JVM and needs
its own boundary on JS. The nbb parity script covers the promise path, since
that is the half a green JVM suite says nothing about.

**No live request has been made against a gateway from this code.**

## Design

**The library performs zero network I/O and computes zero digests.** It builds
signed request maps and hands them to you. Both impure ingredients are
protocols — `IHttp` here, `ICrypto` in `sigv4.protocols` — so the same code runs
on a JVM, in a Cloudflare Worker, under nbb, or behind a WASM capability import,
matching the `kotoba.lang.ipfs` contract (ADR-2606302300 §Step-1: pure `.cljc`,
zero network I/O, zero vendor SDK).

**No clock, either.** Every signing entry point takes `:now` as an ISO-8601
string. That is what makes signatures reproducible, and it is why the reference
vectors below can be asserted at all.

**One code path for sync and async.** `javax.crypto` returns bytes;
`crypto.subtle` returns Promises of bytes. Rather than fork the signing logic,
`storj.core` composes everything through a single `then` — identity-application
on the JVM, `.then` on JS. The visible consequence: **on the JVM these functions
return values, on ClojureScript they return Promises of the same values.**

**Path-style addressing** (`/bucket/key`), which is what Storj's own
`--endpoint-url` examples exercise, and which avoids the DNS and TLS-SAN
requirements of virtual-hosted style.

### Why no AWS SDK

An S3 SDK would make this a JVM-only or Node-only library, which forfeits the
runtimes the kotoba-lang ladder actually targets (`kotoba wasm` > `clojurewasm`
> ClojureScript > nbb). SigV4 is string manipulation plus SHA-256 and
HMAC-SHA-256, and every target runtime already has both — and now it is one
shared library rather than a copy per consumer.

## Correctness

SigV4 fails silently: a wrong byte anywhere produces a valid-looking request and
an opaque `403 SignatureDoesNotMatch`. So the tests do not assert our own
output back to us.

- **AWS reference vectors** live with the signer, in `kotoba-lang/sigv4`: the
  canonical request, string-to-sign and **signature** AWS documents for its two
  worked S3 examples, asserted byte for byte on both runtimes.
- **Independent cross-check.** The request and presign signatures in
  `core_test` were produced by a separate implementation driven straight from
  the spec, not captured from this library — so they also pin the composition
  of this library over the signer.
- **Two-runtime parity.** `kbb -M:test` covers the JVM. WebCrypto is
  asynchronous and therefore takes a *different path through `then`*, so a green
  JVM suite says nothing about the code that ships to browsers and Workers.
  `scripts/verify-cljs.cljk` re-runs the load-bearing assertions on
  `crypto.subtle` and must produce byte-identical signatures. Both run in CI.

```bash
kbb -M:test                                          # JVM
kbb --backend sci --classpath "$(kbb -Spath)" scripts/verify-cljs.cljk   # ClojureScript / WebCrypto
kbb -M:lint
```

`sigv4` is a git dep, so nbb needs the resolved classpath.

## Scope

**In:** the S3 surface (`gateway.storjshare.io`) and Linksharing — the two
Storj edges reachable with HTTP and a signature.

**Out:** the native uplink protocol. Erasure coding, satellite metadata, and
segment distribution are a different and much larger contract than S3-over-HTTP,
and Storj exposes them through `storj.io/uplink` (Go) and its C bindings.
Reimplementing that here would mean either linking a native library — which
forfeits the portability that is this library's whole point — or reimplementing
the protocol, which is not a thing to do as a side effect of wanting object
storage. Gateway-MT is Storj's own answer for clients that want S3 semantics.

Also out: ACLs, bucket policies, lifecycle rules, and CORS configuration —
Storj's gateway does not implement them (see [S3
compatibility](https://storj.dev/dcs/api/s3/s3-compatibility)).

### Multipart upload

Not implemented. Gateway-MT supports it, and it is the right way to move objects
past a few hundred MB, but it is a stateful three-call protocol
(`CreateMultipartUpload` → `UploadPart`×N → `CompleteMultipartUpload`) whose
failure handling — aborting orphaned uploads — is the substantive part. Single
`put-object` covers the current callers; multipart should arrive with the first
caller that needs it, so it can be built against a real size profile rather than
a guess.

## Security notes

- `storj.gateway/validate` refuses to sign toward a host that is not a Storj
  gateway (`gateway.storjshare.io`, or a regional sibling), and refuses
  plaintext `http` — so a mis-set endpoint cannot quietly export credentials to
  someone else's server. Self-hosted Gateway-ST deployments opt out with
  `:allow-any-host? true`.
- `storj.linkshare` refuses an access key long enough to be a **serialized
  access grant**. A grant carries the project's encryption key; embedding one in
  a public URL hands every reader full control of the project. Derive a
  restricted key first: `uplink share --readonly --url --not-after …`.
- Failure messages carry the status and the operation, never the secret.

## License

Apache-2.0.
