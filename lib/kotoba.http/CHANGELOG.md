# Changelog

All notable changes to kotoba-lang/http are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/). Semver per the
kotoba-lang stdlib compatibility policy (kotoba-lang/kotoba-lang/docs/lang/stdlib-versioning.md).

## [Unreleased]

### Added
- `kotoba.lang.http.wire` — an HTTP/1.1 client (RFC 9112) over an **injected
  byte transport**, so the same code runs on a plaintext socket, a TLS 1.3
  record layer or a kotoba-WASM host capability. `http` gains no dependency on
  any of them. Request serialisation (§3), a resumable response parser
  (§4–§6) framed by `Content-Length`, `chunked` or connection close,
  `exchange`, and `transport-http` — an `IHttp` so existing callers get a real
  client by handing over a transport instead of a mock.
- Every fallible entry point returns `[:ok v]` / `[:error reason detail]`;
  nothing throws.
- Named refusals for the framing ambiguities that are smuggling primitives:
  `Content-Length` with `Transfer-Encoding`, disagreeing `Content-Length`s,
  non-hex chunk sizes, truncated chunks, a missing last chunk, a bare LF
  terminator, whitespace before a colon, obs-fold, and every caller-supplied
  ceiling.
- `scripts/live_fetch.cljk` + the `:live` alias: a live composition with
  `kotoba-lang/org-ietf-tls` (script-scope only) against `kotobase.net:443`,
  using its shipped `tls.provider.jvm` directly with no adaptation (measured at
  org-ietf-tls `b91d4a1`), plus a wrong-pin negative control.

### Fixed
- The suite now runs on nbb as well as the JVM, which caught a real
  ClojureScript defect before it shipped: `(int \!)` is 0 there, so a token
  character set built with `(map int "...")` would have been `#{0}` and every
  valid header name invalid on that runtime. The JVM suite was green
  throughout and structurally could not have shown this — run both runtimes.

### Notes
- The live negative control asserts the *reason* a wrong SPKI pin is refused,
  not merely that something was refused. Its first version passed spuriously
  while the handshake was dying earlier for an unrelated cause: "it was
  refused" was true and meaningless because the pin was never reached. A check
  that has never refused for the reason it claims to test has not
  discriminated. It also pins the literal reason, which is how the upstream
  rename `:spki-pin-mismatch` (org-ietf-tls `b37f912`) →
  `:peer-not-pinned` (`b91d4a1`) surfaced instead of passing silently.

## [0.1.0] - 2026-07-01

Initial public release. kotoba.lang.http — request/response + parse-url + IHttp protocol (host-injected).

### Added

- Initial library surface, tests, and CI.
