# ADR 0252: T8.3 / W4 process kit — record-typed recursive EDN request+reply

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0250/0251 record-kv recursive EDN; ADR 0238/0239 fixed-depth process EDN

## Context

Secret kit closed W4 recursive EDN identity (0251). Process kit still used
fixed-depth string-concat codecs (0238/0239) with residual “W4/wasm-aot open”.
Multi-step argv fold stays on the fixed-depth package; recursive identity
can take a prebuilt `argv-edn` string.

## Decision

1. Ship **process-record-kv-edn** (wasm32, kotoba:typed):
   - Same sealed schemas as 0250/0251
   - `process_req_rec_kv_edn` →
     `{:argv […] :max-stdout-bytes N :timeout-ms N}`
     (bounds: max-stdout ∈ (0,65536], timeout ∈ (0,600000])
   - `process_reply_ok_rec_kv_edn` →
     `{:tag :ok :exit N :stdout "…" :stderr "…"}`
   - `process_reply_error_rec_kv_edn` →
     `{:tag :error :code "…" :message "…"}`
   - main → **-2502**
2. Closes process kit **W4 recursive EDN** residual (codec identity).
3. Does **not** flip `:wasm-aot :implemented` — **OS spawn host-injected**.

## Evidence

- Package sha `a4d3cd96…`; browser-host main → -2502
- ops kit registry + sha tests

## Related

- T8.3 residual W4; ADR 0250–0251; process 0238/0239 / 0183
