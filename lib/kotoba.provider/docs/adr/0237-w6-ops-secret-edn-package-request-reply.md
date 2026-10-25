# ADR 0237: T8.3 multi-export secret kit EDN (request + reply)

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0232 reply; ADR 0236 request

## Context

Request and reply fixed-depth EDN were separate packages. Hosts need one
shared pure multi-export surface for secret kit EDN encode.

## Decision

1. Ship **secret-edn-package** (wasm32): exports
   `secret_request_edn`, `secret_reply_value_edn`, `secret_reply_error_edn`.
2. `main` → **-2307**. Package sha `14c3a61d…`.

Honesty: fixed-depth only; not W4 recursive ADT; not host-fetch AOT.
Does not flip secret wasm-aot to implemented.

## Evidence

- KIR main → -2307
- ops kit registry + sha tests

## Related

- T8.3; ADR 0232, 0236; W4 residual remains
