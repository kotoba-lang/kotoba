# kotoba-lang/http

[![CI](https://github.com/kotoba-lang/http/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/http/actions/workflows/ci.yml)

**Layer 3 (I/O) of the kotoba foundational stdlib** — a request/response data
model plus a pure `parse-url`, with an `IHttp` **protocol** the host injects.
No HTTP client is baked in, so the same code runs on kotoba-WASM where the
transport must be a granted host capability. Zero third-party runtime deps;
every namespace is `.cljc` (JVM / SCI / ClojureScript / GraalVM / kotoba-WASM).
See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Why a protocol

A capability-confined cell cannot open a socket on its own. `http` splits: the
**data model** (`request`, `response`, header helpers, `parse-url`) is pure and
portable; the **transport** (`send`) lives behind `IHttp`, host-injected — same
seam as `kotobase.store/IStore` and `fs/IFilesystem`. A `mock-http` is provided
for tests.

## Current surface

`kotoba.lang.http`:

- `request` / `response` — data constructors
- `header` (case-insensitive get) / `set-header`
- `parse-url` — `{scheme host port path query}` from a URL string
- `IHttp` protocol: `send` (host-injected transport)
- `mock-http` — routing fn → response, for tests

`kotoba.lang.http.wire` (see [The wire layer](#the-wire-layer)):

- `serialize-request` / `parse-response` — RFC 9112 §3 and §4–§6
- `recv-init` / `recv-feed` / `recv-eof` — a resumable parser that does not
  care where the read boundaries fell
- `exchange` — one request/response over an injected byte transport
- `transport-http` — an `IHttp` over that transport

## The wire layer

`kotoba.lang.http.wire` is an HTTP/1.1 client (RFC 9112) over an **injected
byte transport**. It knows nothing about TLS, sockets or DNS: it is handed two
functions and speaks HTTP through them, so the same code runs on a plaintext
socket, on a TLS 1.3 record layer, or on a kotoba-WASM host capability, and
`http` acquires a dependency on none of them.

```clojure
(require '[kotoba.lang.http :as http]
         '[kotoba.lang.http.wire :as w])

;; a transport is two functions
{:write (fn [octets] [:ok (count octets)])          ; | [:error reason detail]
 :read  (fn []       [:ok octets])}                 ; | [:eof] | [:error reason detail]

(w/exchange transport (http/request :get "https://a.b/x"))
;=> [:ok {:http/status 200 :http/headers {...} :http/body [...]}]
;=> [:error :conflicting-content-length {:values ["5" "6"]}]

;; or as the IHttp the rest of this library already speaks
(http/send (w/transport-http transport) (http/request :get "https://a.b/x"))
```

Bytes are a vector of ints in `0..255` ("octets"), so nothing depends on a host
byte-array type; `->octets`, `utf8-encode` / `utf8-decode`, `latin1-encode` /
`latin1-decode` and `octets->hex` convert.

### Errors are values

Every fallible entry point returns `[:ok value]` or `[:error reason detail]`,
where `reason` is a keyword naming exactly one refusal and `detail` is a map.
Nothing here throws. `.kotoba` has no `try`/`catch`, so a thrown parse error
could never become a decision core; a returned one can. `IHttp/send` must
return a response map, so on failure it returns one with `:http/status 0` and
`:http/error` — never an exception.

### It refuses rather than normalises

An ambiguous frame is a request-smuggling primitive, not a formatting quirk.
Each refusal has its own reason, because a parser that refuses everything with
`:bad-response` tells a caller nothing:

| reason | what it refuses |
|---|---|
| `:content-length-with-transfer-encoding` | both framings in one message (RFC 9112 §6.1) |
| `:conflicting-content-length` | two `Content-Length` values that disagree |
| `:malformed-content-length` | a length that is not digits |
| `:invalid-chunk-size` | a chunk size that is not hex, or is padded with space |
| `:chunk-size-too-large` / `:too-many-chunks` | chunk framing over the ceiling |
| `:truncated-chunk-data` | a chunk that ran past what arrived |
| `:missing-last-chunk` | no final `0\r\n\r\n` |
| `:missing-chunk-crlf` | a chunk not followed by CRLF |
| `:header-missing-colon` | a field line with no colon |
| `:whitespace-before-colon` | space before the colon (RFC 9112 §5.1) |
| `:bare-lf-line-terminator` | a bare LF used as a line terminator |
| `:obs-fold` | an obsolete line fold |
| `:body-too-large` / `:line-too-long` / `:too-many-headers` | over a caller-supplied ceiling |
| `:unsupported-http-version` | anything that is not HTTP/1.0 or HTTP/1.1 |
| `:header-name-contains-control` / `:header-value-contains-control` | CR, LF or NUL in a request header — refused at construction, so it never reaches the wire |
| `:truncated-response-head` / `:truncated-body` / `:empty-response` | the peer closed mid-message |

Identical duplicate `Content-Length` values are **accepted** and collapse to one
(RFC 9112 §6.3 permits it, and refusing a server that merely repeats itself
would break real traffic). Only disagreement is a desync.

Every ceiling is caller-supplied via `:limits` — the caller decides how much
memory a stranger may spend. `w/default-limits` is a starting point, not a
policy.

### What a caller must not assume

- **No HTTP/2, no HTTP/3.** `HTTP/2` in a status line is refused, not
  downgraded. There is no ALPN here — that belongs to the transport.
- **No redirect following.** A 302 is returned as a 302.
- **No connection management**: no pooling, no keep-alive reuse, no pipelining.
  `exchange` is one request over one transport.
- **No cookies, no auth, no proxies, no `CONNECT`**, no `Expect: 100-continue`
  (interim responses are discarded, not answered).
- **No content decoding.** `Content-Encoding: gzip` is handed back as bytes;
  `Transfer-Encoding: gzip` is refused outright.
- **No timeouts and no retries.** Both belong to the transport, which is the
  only thing that can block.
- **The body is octets, not a string.** Decode it yourself — `latin1-decode` is
  lossless, `utf8-decode` is strict and returns a result.
- **Field values are decoded latin-1**, one octet per code unit, so nothing the
  sender sent is lost.

### Live proof

`scripts/live_fetch.cljk` composes `kotoba-lang/org-ietf-tls` as the transport
with this client and fetches from `kotobase.net:443` under an SPKI pin:

```sh
kbb -M:live scripts/live_fetch.cljk
```

org-ietf-tls is a **script-scope** dependency (the `:live` alias) and appears
nowhere in `:deps`. The entire coupling is `tls-transport`, twenty lines that
turn `tls.client/write!` and `read!` into a `{:write :read}` pair. It uses
org-ietf-tls's shipped `tls.provider.jvm` directly, with no adaptation
(measured at org-ietf-tls `b91d4a1`).

The script ends with a **negative control**: the same fetch under a deliberately
wrong SPKI pin, which must be refused. Two lessons are baked into it, both
learned the hard way here and both worth carrying to other suites:

- **Assert the reason, not the outcome.** The first version of that control
  passed while the handshake was dying at ServerHello for an entirely unrelated
  reason. "It was refused" was true, and meaningless, because the pin was never
  reached. A check that has never refused *for the reason it claims to test* has
  not discriminated, and a green run of it means nothing.
- **Pin the literal reason.** It was `:spki-pin-mismatch` at org-ietf-tls
  `b37f912` and is `:peer-not-pinned` at `b91d4a1`. Asserting the literal is
  what made that upstream rename visible instead of silent.

## Kotoba source authority

`src/kotoba/lang/exact_router.kotoba` owns a zero-capability exact-route table:
case-normalized method plus literal path maps to a handler keyword. It compiles
to restricted browser JS and typed browser Wasm, and is bounded to 31 routes.
Transport remains host-provided; dynamic paths and middleware will use a later
bounded route-plan ABI. The measured boundary is recorded in
`migration/exact-router-v1.edn`.

## Install

```clojure
io.github.kotoba-lang/http {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.http :as http])

(http/parse-url "https://a.b:8443/x?y=1")  ;=> {:scheme "https" :host "a.b" :port 8443 :path "/x" :query "y=1"}
(let [c (http/mock-http (fn [req] (http/response 200 {} "ok")))]
  (-> (http/send c (http/request :get "https://a.b/x")) :http/status)) ;=> 200
```

## Verify

```sh
kbb -M:test                                      # JVM
kbb --backend sci --classpath src:test:../text/src:../json/src run-tests.cljk              # the same .cljc suite, second runtime
kbb -M:lint
kbb -M:live scripts/live_fetch.cljk               # live, over TLS 1.3
```

The suite prints `EXECUTED <n> FLOOR <n>` and fails below the floor; the live
script prints `LIVE-CHECKS <n>` and exits 2 rather than reporting a pass when
nothing ran. A suite that measured nothing must not look like one that measured
and found no problem.

**Run both runtimes.** The nbb entry is not a formality. It caught a defect the
JVM suite structurally could not see: `(int \!)` is `0` in ClojureScript, so a
token character set built with `(map int "!#$%&'*+-.^_`|~")` was `#{0}` there —
every valid header name was invalid on that runtime, and the JVM run was green
throughout.
