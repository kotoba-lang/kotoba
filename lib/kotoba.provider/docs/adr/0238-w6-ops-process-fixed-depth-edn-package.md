# ADR 0238/0239: T8.3 process kit fixed-depth EDN request+reply package

- Status: Accepted
- Date: 2026-08-01
- Depends: process walk 0183; secret EDN package pattern 0236/0237

## Context

Process kit request/result were pure bounds/walk only (0172/0183) with OS spawn
host-injected. HTTP/secret gained fixed-depth request/reply EDN packages.
Process needs the same pure codec surface without embedding host spawn.

## Decision

1. Ship **process-edn-package** (wasm32, kotoba:typed):
   - Request: guest record argv EDN fold (begin/arg) + process_req_edn with
     max-stdout-bytes and timeout-ms bounds matching process-v1 limits
   - Reply: process_reply_ok_edn(exit, stdout, stderr) and
     process_reply_error_edn(code, message)
   - main → **-2309**
2. Dual quote/backslash scan on string leaves; argc ≤ 32; arg non-empty.
3. OS spawn remains host-injected — this package is pure EDN codec only.
4. Does not flip wasm-aot to implemented (W4 recursive nested EDN open).

## Evidence

- Package sha; KIR main → -2309
- ops kit registry + sha tests

## Related

- T8.3; process 0168/0172/0183; secret 0236/0237 pattern
