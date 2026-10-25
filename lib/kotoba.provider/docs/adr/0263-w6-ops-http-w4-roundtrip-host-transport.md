# ADR 0263: T8.3 HTTP W4 round-trip — guest codecs + host transport

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0250 recursive-record-kv; 0256–0258 edn-codec; 0260–0262 guest host_post

## Context

ADR 0262 proved live `typedCapCall` inject for guest `host_post_edn`, but inject
modes were stubs (`:echo` / `:ok-200`). Production network authority already
lives in `http-transport/production-transport`. Forcing real HTTP through
Node-side inject duplicates host policy (allow-origins, redirects, SSRF) in a
second place.

The honest production composition is:

1. **Guest pure** W4 request EDN (codec AOT)
2. **Host** transport (network authority)
3. **Guest pure** W4 reply EDN (codec AOT)

Guest `host_post_edn` remains the capability-forward surface for hosts that
want encode+cap-call in one guest export; inject stubs stay for cap-path tests.

## Decision

1. Ship **`http-w4-roundtrip`** on `provider.edn-codec`:
   - Build headers list + request EDN via guest packages
   - Call host `transport` with structured map
   - Encode ok/err reply EDN via guest packages
   - Optional `on-call` with `:request-edn` / `:reply-edn` / latency
2. Ship **`http-w4-roundtrip-with-production`** — same with
   `production-transport` (allowed-origins required).
3. Does **not** flip `:wasm-aot :implemented` — network remains host-injected.

## Evidence

- Unit tests: test-double transport ok + error arms when browser-host available

## Related

- T8.3 host authority residual; ADR 0260–0262; http-transport production
