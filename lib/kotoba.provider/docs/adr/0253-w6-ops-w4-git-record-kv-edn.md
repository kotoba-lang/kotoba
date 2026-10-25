# ADR 0253: T8.3 / W4 git kit record-typed recursive EDN

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0252 process W4 pattern; ADR 0240/0241 fixed-depth git EDN

## Context

Process kit closed its W4 residual with record-typed recursive EDN (0252).
Git still used fixed-depth string-concat codecs (0240/0241) with residual
**W4 open**. OS git binary remains host-injected.

## Decision

1. Ship **git-record-kv-edn** (wasm32, kotoba:typed):
   - Same sealed `:edn/kv` + `:edn/node` atom|entry|pair as 0250–0252
   - `git_req_rec_kv_edn(args-edn, max-stdout, timeout-ms)` →
     `{:args […] :max-stdout-bytes N :timeout-ms N}`
   - `git_reply_ok_rec_kv_edn` / `git_reply_error_rec_kv_edn`
   - main → **-2503**
2. Args multi-step fold stays on fixed-depth 0240; this package takes
   prebuilt args-edn string (same split as process 0252).
3. Does **not** flip `:wasm-aot :implemented` — host git binary open.

## Evidence

- Package sha `9fded0b6…`; browser-host main → -2503
- ops kit registry + sha tests

## Related

- T8.3 residual W4; ADR 0252 process; git 0240/0241; host git authority
