# atproto-client

`kotoba.lang.atproto-client` — AT Protocol client facade (XRPC + PDS session /
record helpers) as a **pure portable Clojure (`.cljc`) core over an injected
`IHttp` transport**.

The library performs **zero network I/O**: every XRPC call and DID-document
fetch goes through a host-supplied `kotoba.lang.atproto-client.atproto/IHttp`
(`-request`). The host backs it with `java.net` / `babashka.http-client` (JVM)
or `fetch` (CLJS/WASM). This is the kotoba-lang layer contract — pure `.cljc`,
zero network I/O, zero vendor SDK (ADR-2606302300 §Step-1). The original
`@atproto/api` vendor SDK has no place inside the library; callers inject an
`IHttp` that may itself wrap `@atproto/api` on the host side.

| Group | Functions |
|---|---|
| agent / xrpc | `create-agent`, `xrpc` (atproto) |
| session | `create-account`, `login`, `get-agent` (pds) |
| records | `create-record`, `get-record`, `list-records` (pds) |
| liveness / did | `health`, `resolve-pds` (did:web) (pds) |

The "agent" is an immutable map `{:service :http :headers :session?}`. JVM is
synchronous; CLJS returns `js/Promise` (mirroring the original async TS).

### `IHttp`: one `-request` method, not `kotoba-lang/ipfs`'s `-get`/`-post`/`-post-file`

`kotoba-lang/ipfs` (Kubo/IPFS HTTP API) shaped its `IHttp` as three methods
(`-get`/`-post`/`-post-file`) with no header parameter, because Kubo needs no
auth/custom headers and its POST bodies are either empty or a multipart file
upload. XRPC's needs are different: every call (GET *and* POST) carries
headers (Authorization bearer, Content-Type, per-call overrides), and no call
ever uploads multipart/binary content — only a JSON body on POST. So this
package's `IHttp` collapses to a **single** method instead of three:

```clojure
(defprotocol IHttp
  (-request [this req] "Perform the request; return {:status :body}."))
```

`req` is `{:method :get|:post :url String :headers {String String} :body
String|nil}`; the response is `{:status Int :body String}`. Bodies are
**Strings, not byte arrays** — another deliberate departure from `ipfs`'s
`bytes`-shaped `IHttp`: `ipfs`'s Kubo API moves opaque blob bytes (pinned
files, gateway fetches), so its seam has to be byte-exact; XRPC only ever
carries JSON text (request and response), so a String is both sufficient and
simpler — forcing a byte-array-in/byte-array-out shape here would only add
UTF-8 encode/decode busywork with no capability gained. The one-method
`-request` (vs. one method per verb) also reads a little more naturally once
headers have to flow through every call: it's a single request/response data
shape instead of two shapes with independent evolution.

Reference implementation (JVM): `kotoba.lang.atproto-client.http-jdk/jdk-http`
builds an `IHttp` from the JDK's built-in `java.net.http.HttpClient` (Java
11+) — **zero extra runtime deps**, so it ships directly in this repo's own
`src/` without pulling `babashka.http-client` back into the core library's
dependency footprint. `(jdk-http)` / `(jdk-http {:client my-client
:timeout-ms 5000})`. This repo's test suite additionally proves the design
against a *second*, independently-written `IHttp` backed by
`babashka.http-client` (a `:test`-alias-only dep — see
`test/kotoba/lang/atproto_client/pds_test.cljk`'s `babashka-http`), so both
the pure logic and two different real transports are exercised end-to-end
against the same mock PDS server. Neither is the *only* option: any host
already depending on a different JVM HTTP client, or (CLJS) browser `fetch`,
is free to `reify atproto/IHttp` directly.

**Scoped out of the pure core by this retrofit**: the pre-retrofit `xrpc`
accepted a per-call `:timeout`, forwarded straight to `babashka.http-client`.
A socket/read timeout is a transport-level concern with no meaningful,
uniform expression across `java.net.http` / `babashka.http-client` / browser
`fetch` (`AbortController`) / a test fake, so it doesn't belong on a protocol
whose only job is "move these bytes" — it moved to `IHttp` construction
instead (e.g. `jdk-http`'s `:timeout-ms`, applied to every request that
`IHttp` instance sends).

## Provenance

Relocated 2026-07-01 from `etzhayyim/root:20-actors/etzhayyim-sdk/src/{atproto,pds}.ts`
to `kotoba-lang/atproto-client`. Originally relocated as TypeScript (a physical
move), then ported to `.cljc`. The TypeScript has been **deleted** — the `.cljc`
core is the single canonical implementation.

## Develop

```bash
kbb -M:lint     # clj-kondo (errors fail)
kbb -M:test     # mock-PDS (JDK HttpServer), exercised via two injected IHttp
                    # impls: babashka.http-client (test-only dep) and this
                    # repo's own zero-dep reference adapter, http-jdk/jdk-http
```
