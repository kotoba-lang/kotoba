# ADR 0240/0241: T8.3 git kit fixed-depth EDN request+reply package

- Status: Accepted
- Date: 2026-08-01
- Depends: git walk 0184; process EDN package pattern 0238/0239

## Context

Git kit request/result mirrored process (args vector + max-stdout + timeout;
ok exit/stdout/stderr or error). Process gained fixed-depth EDN package
(0238/0239). Git needs the same pure codec surface; OS git run stays host-injected.

## Decision

1. Ship **git-edn-package** (wasm32, kotoba:typed):
   - Request: host-sequenced args EDN fold (begin/arg, argc ≤ 64 per git-v1
     :limits) + git_req_edn with max-stdout-bytes and timeout-ms bounds
   - Reply: git_reply_ok_edn / git_reply_error_edn
   - main → **-2311**
2. Dual quote/backslash scan; arg non-empty; limits match git-v1.
3. OS git binary remains host-injected — pure EDN codec only.
4. Does not flip wasm-aot to implemented (W4 recursive nested EDN open).

## Evidence

- Package sha; KIR main → -2311
- ops kit registry + sha tests

## Related

- T8.3; git 0170/0172/0184; process 0238/0239 pattern
