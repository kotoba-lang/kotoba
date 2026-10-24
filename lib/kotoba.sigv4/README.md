# sigv4

`sigv4.*` — AWS Signature Version 4, **signing and verification**, as portable
`.cljc` with injected crypto. The shared implementation for every S3-compatible
surface in this workspace.

| Namespace | What it owns |
|---|---|
| `sigv4.core` | The pure half — encoding, canonicalization, credential scope, string-to-sign, presign params. No crypto, no clock, no I/O. |
| `sigv4.request` | The composed signer: config in, `{:url :headers}` out. Presigned URLs too. |
| `sigv4.verify` | The server side — parse `Authorization`, recompute the expected signature, compare in constant time. |
| `sigv4.crypto` | Optional default `ICrypto` (`javax.crypto` / WebCrypto). |
| `sigv4.protocols` | The one host seam: `ICrypto`. |
| `kotoba/pct_encode.kotoba` | The percent-encoder, again — in Kotoba, compiled to Wasm, held byte-equal to `sigv4.core`. |

## Why this exists

SigV4 was implemented **six times** across this workspace. Every one of them
now depends on this library instead:

| Implementation | Was |
|---|---|
| `gftdcojp/net-kotobase` `kotobase.sigv4` | the original; the other five descend from it |
| `gftdcojp/net-kotobase-ipfs` `kotobase-ipfs.sigv4` | a verbatim copy, so documented in its own docstring |
| `kotoba-lang/kotobase-peer` `object-store.s3-sigv4` | an edited copy |
| `kotoba-lang/kotobase-protocols-worker` `sigv4` | the verification side |
| `kotoba-lang/shoko` `archiveport` | a JVM port, written because the original was cljs-only |
| `kotoba-lang/io-storj` | written fresh, two days before this library |

Each was a locally correct decision. `net-kotobase-ipfs` copied rather than
depended precisely to stay single-purpose and low-privilege; `shoko` ported to
the JVM because a ClojureScript signer cannot be `require`d from one. The cost
only shows up in aggregate: **they had already diverged, and each in a way its
own repo could never notice.**

- `kotobase-protocols-worker` percent-encoded with `charCodeAt`, emitting UTF-16
  code units — so any non-ASCII key or query value signed differently from AWS
  and from every S3 SDK. It is the *verifying* side, so it would have rejected
  correctly-signed requests.
- `kotobase-peer` split keys without a trailing-empty limit, so a key ending in
  `/` signed as a different key than it addressed.
- Four of the six used `encodeURIComponent` with a manual `!'()*` fixup; only
  `shoko` encoded from UTF-8 bytes, which is the correct rule.

Four of the six had **no test of their signing at all**. `kotobase-peer` had
2278 lines of object-store tests without one assertion about an `Authorization`
header; `net-kotobase`, which held the implementation the others copied, had 25
proxy tests and none that looked at a signature. A signer nobody exercises
drifts, and the only symptom is an opaque `403 SignatureDoesNotMatch` at some
later date.

Two things previously reported as duplicates are not, and are recorded here so
the count stops being repeated:

- `kotobase-peer-atomic` and `kotobase-peer-main-test` are **git worktrees of
  `kotobase-peer`**, not separate repositories. The "three byte-identical
  copies" were one file seen through three checkouts.
- `kotobase-protocols` `protocols.s3` only *mentions* SigV4, as explicitly out
  of scope. It never implemented it.

## Usage

```clojure
(require '[sigv4.crypto :as crypto]
         '[sigv4.request :as req])

(def c (crypto/crypto))

;; sign a request — endpoint-agnostic: B2, R2, Storj and S3 all speak this
(req/signed c {:endpoint "https://gateway.storjshare.io"
               :bucket "my-bucket" :region "us-east-1"
               :access-key "…" :secret-key "…"
               :method :put :key "docs/a.txt" :body "hello"
               :headers {"content-type" "text/plain"}
               :now (str (java.time.Instant/now))})
;; => {:method "PUT" :url "https://…/my-bucket/docs/a.txt" :headers {…} :body "hello"}

(req/presigned c (assoc config :key "docs/a.txt" :expires-seconds 900))
;; => "https://…?X-Amz-Algorithm=…&X-Amz-Signature=…"

;; a presigned PUT that binds its size, and the headers the client must send
(req/presigned-request c (assoc config :method :put :key "docs/a.txt"
                                :headers {"content-length" "12345"}))
;; => {:url "https://…&X-Amz-SignedHeaders=content-length%3Bhost&X-Amz-Signature=…"
;;     :method :put :headers {"content-length" "12345"}
;;     :signed-headers "content-length;host" :expires-seconds 3600}

;; verify
(require '[sigv4.verify :as verify])
(let [parsed (verify/parse-authorization (get-in req [:headers "authorization"]))
      expected (verify/expected-signature c {:secret-key secret
                                             :parsed parsed
                                             :amz-date amz-date
                                             :payload-hash body-hash
                                             :request req})]
  (verify/constant-time-eq? (:signature parsed) expected))
```

## A presigned URL is a capability, and `:headers` gives it a shape

`presigned` signs only `host`, which is what makes the URL usable from a
browser — and also what makes a presigned PUT a blank cheque: whoever holds it
may store any number of bytes under a key whose content they never had to
know. `presigned-request` signs whatever you put in `:headers` as well, and
returns them so the client can send them back.

Listing a header in the request while signing only `host` binds nothing. The
constraint has to be in the signature: a holder who sends a different
`content-length` computes a different signature and the store rejects the
upload. `test/sigv4/request_test.cljk` pins both signatures — the bound one and
the one a 99999-byte body would need — from an independent implementation.

Signing an S3 object store end to end — client, endpoint validation, presigned
URLs — is [`kotoba-lang/io-storj`](https://github.com/kotoba-lang/io-storj),
which builds on this.

## Design

**No clock, no crypto, no I/O in `sigv4.core`.** Every signing entry point takes
the timestamp as an ISO-8601 string, and SHA-256/HMAC arrive through `ICrypto`.
That is what makes the reference vectors reproducible, and it keeps the
namespace identical on every runtime in the kotoba-lang ladder.

**`signing-key-chain` returns the HMAC inputs, not a key.** The host folds its
own HMAC over them, so this library derives signing keys without ever touching
a cipher.

**One code path for sync and async.** `javax.crypto` returns bytes;
`crypto.subtle` returns Promises of bytes. Consumers compose through a `then`
that is plain application on the JVM and `.then` on JS. On the JVM these
functions return values; on ClojureScript, Promises of the same values.

**No transport protocol.** A signer produces a signed request; putting it on the
wire belongs to whoever owns the connection — and every consumer already has one.

### Why no AWS SDK

An S3 SDK would make this JVM-only or Node-only, which forfeits the runtimes
that consume it: Cloudflare Workers, browser peers, nbb scripts, the JVM. SigV4
is string manipulation plus SHA-256 and HMAC-SHA-256, and every target runtime
already has both.

## Correctness

SigV4 fails silently: a wrong byte anywhere produces a valid-looking request and
an opaque `403 SignatureDoesNotMatch`. So the tests do not assert our own output
back to us.

- **AWS reference vectors.** The canonical request, string-to-sign and
  **signature** AWS documents for its two worked S3 examples — header auth
  (`f0e8bdb8…`) and query-string auth (`aeeed9bb…`).
- **Signing closed against verification.** `verify_test` signs AWS's example and
  then verifies it, and `request_test` round-trips the composed signer through
  the verifier on ASCII, non-ASCII, reserved-character and extra-header keys.
  A drift between the two halves fails there rather than in production as an
  unexplained 403 — which is precisely what nine independent copies could not
  guarantee about each other.
- **Two-runtime parity.** `kbb --backend sci run-tests.cljk` re-runs the load-bearing
  assertions on WebCrypto, where the async path through `then` is genuinely
  different code. Most consumers of this library run in Workers, and this
  library both signs their outbound S3 requests and verifies the inbound ones
  they accept. Measured 2026-08-17: corrupting the ClojureScript HMAC key by
  one character fails 7 assertions here and **none** of the 93 on the JVM.
- **Kotoba/Wasm parity.** `kbb --backend sci kotoba-tests.cljk` requires the Kotoba
  implementation and the Clojure one to agree byte for byte across 147 inputs.

All four run in CI.

```bash
kbb -M:test                 # JVM
kbb --backend sci run-tests.cljk              # ClojureScript / WebCrypto
kbb --backend sci kotoba-tests.cljk           # Kotoba/Wasm vs Clojure (builds the module itself)
kbb -M:lint
```

## The Kotoba implementation

`kotoba/pct_encode.kotoba` is a second, independent implementation of
`sigv4.core/uri-encode`, written in Kotoba and compiled by the released native
CLI to a ~500-byte Wasm module.

Percent-encoding is the right slice to own in Kotoba: it is the single most
failure-prone step in SigV4 (S3 does not exempt the characters
`encodeURIComponent` exempts, and demands uppercase hex), and it is pure
byte-to-byte work — no maps, no sorting, no host capability. It runs on `alloc`,
`mem-byte-at` and `byte-store!` over the module's linear memory, with
self-recursion in place of a loop form.

```bash
kbb --backend sci kotoba-tests.cljk   # emits the module, then compares 147 inputs
```

The suite invokes the CLI itself rather than assuming a built module, and
**fails when the CLI is absent** — a parity check that was skipped must not
report what a satisfied one reports. That is not hypothetical: the module had
been failing to build since the language grew its T1 memory-safety gate
(`raw-memory-denied` on `mem-byte-at` / `byte-store!`), and nothing said so
because nothing ran it.

**What is not in Kotoba, and why.** The rest of SigV4 — sorting headers,
canonical query assembly, string-to-sign — needs maps, string collections and a
sort. Those are not in the Wasm subset today, so the composition layer stays
`.cljc`. Two further limits are worth recording because they shaped this module:

- The Wasm emitter rejects `:require` across modules (`internal-error` on
  v0.6.29), so the classifier is inlined rather than split into its own module.
- The `web`/ESM target, which *does* support multi-module, has no admitted
  lowering for `alloc` / `mem-byte-at` / `byte-store!` (`operation has no
  admitted lowering`), so this cannot be an ESM pilot the way `io-ipfs`'s is.

This is a real slice, not a relabelling: it is compiled from `.kotoba` by the
checksum-verified released CLI and held to byte-equality with the Clojure
implementation. It is not yet load-bearing — `sigv4.core/uri-encode` is what
consumers call. Promoting it is a decision for when the composition layer can
follow it.

## License

Apache-2.0.
