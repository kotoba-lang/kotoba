# ADR 0257: T8.3 edn-codec audit-hook integration

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0256 host pure-EDN codec wire; ADR 0250–0255 W4 packages

## Context

ADR 0256 shipped `provider.edn-codec` as a callable pure-EDN wire, but hosts
still had to hand-roll transport composition to attach request/reply EDN to
audit events. Secret fetch has no built-in `:on-call`; HTTP has `:on-call` but
default production-transport events omit pure W4 EDN fields.

## Decision

1. Extend **`provider.edn-codec`** with:
   - `wrap-secret-fetch` — wrap secret `:fetch` so each call audits
     `request-edn` / `reply-edn` via W4 secret package (no extra secret I/O
     beyond the underlying fetch).
   - `wrap-http-post-transport` — wrap HTTP post transport fn to audit
     pure W4 `request-edn` (plus status/latency) without performing network
     itself.
   - HTTP helpers: `http-headers-list-edn`, `http-request-edn`,
     `http-result-ok-edn`, `http-result-err-edn`.
2. Wrappers swallow codec/on-call failures; fetch/transport semantics unchanged.
3. Does **not** flip `:wasm-aot :implemented` — host authority remains open.

## Evidence

- Unit tests: wrap-secret-fetch audits request+reply EDN; wrap-http dry-run
  attaches request-edn when browser-host available

## Related

- T8.3 host authority residual; ADR 0256; secret-transport; http-transport
