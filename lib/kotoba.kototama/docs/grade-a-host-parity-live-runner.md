# Grade A / T8.4 — live host runners (JVM + Node)

- Status: partial (JVM 56 + Node 38 inject/live; **live SCRAM/PG success via** `kbb -M:postgresql-interop`; **scram-sha256 host crypto live-proven**)
- Date: 2026-07-31
- WBS: T8.4

## Context

`kotoba.lang.host-parity/run-conformance` scores the L5 matrix as **pure
data**. T8.4 requires **live host runners** that link/call imports on real
runtimes (kototama tender, wasm-webcomponent).

## Decision

### JVM (`kototama.host-parity-live/run-jvm-live`)

WAT guests + Chicory tender for:

| case id | import(s) | proof |
|---|---|---|
| `:sha256-hex-all-available` | `:sha256-hex` | WAT + Chicory |
| `:clock-monotonic-all` | `:clock-monotonic` | WAT + Chicory |
| `:log-write-all-available` | `:log-write` | WAT + Chicory |
| `:log-read-all-available` | `:log-read` | WAT + Chicory |
| `:gen-keypair-all-available` | `:gen-keypair` | WAT + Chicory |
| `:sign-all-available` | `:gen-keypair` + `:sign` | WAT + Chicory |
| `:verify-all-available` | gen+sign+`:verify` | WAT + Chicory |
| `:cbor-encode-jvm-live` | `:cbor-encode` | pure allowlist host |
| `:json-encode-jvm-live` | `:json-encode` | pure allowlist host |
| `:random-bytes-all-available` | `:random-bytes` | WAT + Chicory (tender) |
| `:http-post-jvm-available` | `:http-post` | loopback fail-closed (link+SSRF) |
| `:llm-infer-jvm-available` | `:llm-infer` | injected infer-fn, no network |
| `:kagi-sign-jvm-available` | `:kagi-sign` | decision-aware inject (no Keychain) |
| `:scram-sha256-jvm-available` | `:scram-sha256` | host credentials inject; PBKDF2/HMAC → 64 (no PG) |
| `:scram-sha256-jvm-deny-available` | `:scram-sha256` | no allowlist/credentials → -1 |
| `:transport-connect-jvm-inject-available` | `:transport-connect` | inject transport-provider; empty allowlist → 0 |
| `:tls-open-jvm-inject-available` | `:tls-open` | inject; invalid handle → 0 |
| `:transport-close-jvm-inject-available` | `:transport-close` | inject; unknown handle → -1 |
| `:transport-write-jvm-inject-available` | `:transport-write` | inject; unknown handle → -1 |
| `:transport-read-jvm-inject-available` | `:transport-read` | inject; unknown handle → -1 |
| `:transport-rw-jvm-loopback-success` | `:transport-write` + `:transport-read` | loopback ServerSocket echo; write+read 2 bytes |
| `:tls-server-end-point-jvm-available` | `:tls-server-end-point` | inject; non-TLS handle → -1 |
| `:pg-pool-open-jvm-inject-available` | `:pg-pool-open` | fail-closed inject provider → -1 |
| `:pg-pool-acquire-jvm-inject-available` | `:pg-pool-acquire` | fail-closed inject; unknown pool → -1 |
| `:pg-pool-health-jvm-inject-available` | `:pg-pool-health` | fail-closed inject; unknown pool → -1 |
| `:pg-pool-close-jvm-inject-available` | `:pg-pool-close` | fail-closed inject; unknown pool → -1 |
| `:pg-pool-query-jvm-inject-available` | `:pg-pool-query` | fail-closed inject; no lease → -1 |
| `:pg-pool-release-jvm-inject-available` | `:pg-pool-release` | fail-closed inject; unknown lease → -1 |
| `:pg-pool-stats-jvm-inject-available` | `:pg-pool-stats` | fail-closed inject; unknown pool → -1 |
| `:pg-pool-drain-jvm-inject-available` | `:pg-pool-drain` | fail-closed inject; unknown pool → -1 |
| `:pg-cancel-register-jvm-inject-available` | `:pg-cancel-register` | inject; non-TLS handle → 0 |
| `:pg-cancel-jvm-inject-available` | `:pg-cancel` | inject; unknown handle → -1 |
| `:pg-open-jvm-inject-available` | `:pg-open` | wire fail-closed inject → handle 0 |
| `:pg-query-jvm-inject-available` | `:pg-query` | wire fail-closed inject → -1 |
| `:pg-simple-query-jvm-inject-available` | `:pg-simple-query` | wire fail-closed inject → -1 |
| `:pg-prepare-jvm-inject-available` | `:pg-prepare` | wire fail-closed inject → -1 |
| `:pg-session-reset-jvm-inject-available` | `:pg-session-reset` | wire fail-closed inject → -1 |
| `:pg-execute-params-jvm-inject-available` | `:pg-execute-params` | wire fail-closed → -1 |
| `:pg-close-statement-jvm-inject-available` | `:pg-close-statement` | wire fail-closed inject → -1 |
| `:http-fetch-jvm-available` | `:http-fetch` | loopback fail-closed (link+SSRF) |
| `:http-post-headers-jvm-available` | `:http-post-headers` | loopback fail-closed (link+SSRF) |
| `:json-extract-field-jvm-live` | `:json-extract-field` | pure host extract `{"x":"ok"}` → 2 |

### Node / browser (`web/verify-host-parity-live.mjs`)

Node WebAssembly + wasm-webcomponent `actor-host.js` for:

| case id | import(s) |
|---|---|
| crypto/clock/log (matrix-aligned) | |
| `:random-bytes-all-available` | `:random-bytes` (actor-host) |
| `:http-post-node-inject-available` | `:http-post` + inject + allowlist |
| `:llm-infer-node-available` | `:llm-infer` + inject |
| `:kagi-sign-node-inject-available` | `:kagi-sign` + kagiSigner/decisions inject |
| `:transport-connect-node-inject-available` | `:transport-connect` fail-closed (handle 0) |
| `:tls-open-node-inject-available` | `:tls-open` fail-closed (handle 0) |
| `:transport-close-node-inject-available` | `:transport-close` fail-closed (-1) |
| `:transport-write-node-inject-available` | `:transport-write` fail-closed (-1) |
| `:transport-read-node-inject-available` | `:transport-read` fail-closed (-1) |
| `:pg-pool-open-node-inject-available` | `:pg-pool-open` fail-closed (-1) |
| `:pg-pool-acquire-node-inject-available` | `:pg-pool-acquire` fail-closed (-1) |
| `:pg-pool-health-node-inject-available` | `:pg-pool-health` fail-closed (-1) |
| `:pg-pool-close-node-inject-available` | `:pg-pool-close` fail-closed (-1) |
| `:pg-open-node-inject-available` | `:pg-open` fail-closed (handle 0) |
| `:pg-query-node-inject-available` | `:pg-query` fail-closed (-1) |
| `:scram-sha256-node-deny-available` | `:scram-sha256` deny without credentials |
| `:scram-sha256-node-available` | `:scram-sha256` host crypto inject (64-byte proof) |
| `:http-fetch-node-inject-available` | `:http-fetch` + inject + allowlist |
| `:http-post-headers-node-inject-available` | `:http-post-headers` + inject |
| `:json-extract-field-node-live` | `:json-extract-field` pure host |
| `:cbor-encode-node-live` | `:cbor-encode` pure flat-pairs |
| `:json-encode-node-live` | `:json-encode` pure flat-pairs |

Loads sibling `../wasm-webcomponent` when present; else pinned CDN commit.
Emits `HOST_PARITY_LIVE_JSON:` for Clojure integration (`run-node-live`).

### Legacy

`web/verify-actor-host.mjs` — smaller smoke (sha256/clock/log + session revoke).

## Non-claims

- Transport/TLS + full pg-pool/wire/scram/deeper-wire Node inject fail-closed proven (wasm-webcomponent#17–#19). Node inject surface complete for actor:host pg family
- Live SCRAM-SHA-256-PLUS *session* success is proven by `kbb -M:postgresql-interop`
  (ephemeral PG + TLS + SCRAM guest providers); not embedded in the 56 JVM inject corpus
- `:scram-sha256` **host crypto** is live-proven in the JVM corpus (credentials inject;
  no live PG required) — complementary to interop session proof
- Not signed ops AOT Components (T8.3)
- Does not replace pure matrix `run-conformance`
- Not claim T8.4 complete
- JVM live corpus: 56 proofs; Node: 38 proofs (incl. transport inject fail-closed)
- Loopback success is plain TCP (not TLS mutual-auth / production network ABAC)
- Pool inject uses `fail-closed-inject-provider` (no live PostgreSQL)

## Evidence

- `test/kototama/host_parity_live_test.cljk` (56 JVM live proofs)
- `node web/verify-host-parity-live.mjs` (38 Node proofs)

## Related

- Reliability WBS T8.4
- ADR-w6-t84-host-parity-critical-fixtures
