# ADR 0259: T8.3 production/test factories with pure EDN audit

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0256–0258 edn-codec wire + wraps

## Context

Audit wraps existed (0257–0258) but hosts still hand-composed
`production-transport` / `map-fetch` / `os-spawn` / `os-run` / `os-store`
with wrappers. Also `wrap-scoped-fs-transact` mis-read content body as
`:content` while store replies use `:value`.

## Decision

1. Ship explicit factories on **`provider.edn-codec`**:
   - `production-http-transport` — production HTTP + W4 EDN audit
   - `secret-map-fetch-with-edn-audit` / `secret-env-fetch-with-edn-audit`
   - `process-echo-with-edn-audit` / `process-os-spawn-with-edn-audit`
   - `git-echo-with-edn-audit` / `git-os-run-with-edn-audit`
   - `scoped-fs-os-store-with-edn-audit`
2. Base transport internal `:on-call` is silenced for HTTP production factory;
   host supplies one `:on-call` for EDN-enriched events.
3. Fix scoped-fs content reply field to accept `:value` (store contract).
4. Does **not** flip `:wasm-aot :implemented`.

## Evidence

- Unit tests: secret-map + process-echo + git-echo factories audit EDN when
  browser-host available

## Related

- T8.3 host authority residual; ADR 0256–0258
