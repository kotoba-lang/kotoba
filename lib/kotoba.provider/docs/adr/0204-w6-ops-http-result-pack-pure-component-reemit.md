# ADR 0204: T8.3 pure Component re-emit of typed result packing walk

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0192 typed-string result packing; kotoba-component#99
  (`:http-result-pack-package-with-main`); ADR 0203 request packing

## Context

ADR 0192 shipped a typed-host wasm module for host-sequenced HTTP result
packing (ok arm: status/headers/body; error arm: code/message/retryable) +
live `main`. Pure Component packaging needed nine-export Canonical multi-export
with nested main composition and helper-mediated error-code charset scan.

## Decision

| source | module (typed) | Component (pure) | live `main()` |
|---|---|---|---|
| `http_result_pack.kotoba` | `:http-result-pack` | `:http-result-pack-component` | **-12061** |

Policy (Canonical WAT):

- **ok path**: begin(0)=1 → status→2 → headers→3 → body→4 → end=0
- **err path**: begin(1)=11 → code→12 → message→13 → retryable→14 → end=0
- Codes: begin −1; status −2; headers −3; body −4; code −5/−6/−7; message −8;
  retryable −9; wrong-phase −10; incomplete −11

### Honesty

- Does **not** flip `:wasm-aot :implemented`
- Does **not** pack nested request/result EDN records as one value
- Does **not** replace host http-post I/O

## Evidence

- digest match; wasmtime `main()` → `-12061`
- begin 0/1/3 → 1/11/−1; empty code → −5
- ops-kit component twin registration

## Related

- T8.3; ADR 0190–0193, 0203; kotoba-component#99
