# ADR 0251: T8.3 / W4 sixth ops slice — secret kit record-kv request/reply EDN

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0250 HTTP record-kv recursive ADT; ADR 0232–0237 fixed-depth secret EDN

## Context

HTTP W4 recursive EDN reached record-typed `:edn/kv` entries (0250). Secret
kit still used fixed-depth string-concat codecs (0232–0237 / 0245 Component
twin) with residual **W4 recursive ADT open**. Host fetch remains intentionally
host-injected.

## Decision

1. Ship **secret-record-kv-edn** (wasm32, kotoba:typed):
   - Same sealed schemas as 0250: `:edn/kv` + `:edn/node` atom|entry|pair
   - `secret_request_rec_kv_edn` → `{:name "…"}`
   - `secret_reply_value_rec_kv_edn` → `{:tag :value :value "…"}`
   - `secret_reply_error_rec_kv_edn` → `{:tag :error :code "…" :message "…"}`
   - main → **-2406**
2. Closes secret kit **W4 recursive EDN** residual (codec identity).
3. Does **not** flip `:wasm-aot :implemented` — **host-fetch** remains open.
4. Dual quote/backslash reject; empty name / code fail closed; name length ≤128.

## Evidence

- Package sha `0dfcb60c…`; browser-host main → -2406
- ops kit registry + sha tests

## Related

- T8.3 residual W4; ADR 0250; secret 0232–0245; host-fetch authority
