# ADR 0234: T8.3 full request EDN from kit-shaped set-record

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0231 request set-record; ADR 0233 headers fold; compiler 0194

## Context

ADR 0231 held kit-shaped request guest records with headers-n-only EDN.
ADR 0233 folded headers to full EDN vector. Hosts still needed one pure package
that emits the full fixed-depth request map from the guest record.

## Decision

1. Ship **http-request-edn-set-record** (wasm32, kotoba:typed): same begin/add
   surface as 0231; **http_req_edn** emits
   `{:url "…" :headers [{…} …] :body "…" :timeout-ms N}` using typed-set-nth
   headers fold.
2. main → **-9002** (two headers, EDN contains url/headers/timeout keys, dup name → -9).
3. Fixed-depth request map only — not W4 recursive nested EDN ADT.
4. Does not flip `:wasm-aot :implemented`.

## Evidence

- Package sha; KIR main → -9002
- ops kit registry + sha tests

## Related

- T8.3; ADR 0231–0233; W4 residual remains for recursive ADT / wasm-aot
