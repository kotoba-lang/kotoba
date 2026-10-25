# ADR 0254: T8.3 / W4 entropy kit — record-typed recursive EDN request+reply

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0250–0253 record-kv recursive EDN; ADR 0244 fixed-depth entropy EDN

## Context

Git kit closed W4 recursive EDN identity (0253). Entropy kit still used
fixed-depth string-concat codecs (0244) with residual “W4 open”. CSPRNG
remains host-injected; recursive request/reply identity advances without
host draw.

## Decision

1. Ship **entropy-record-kv-edn** (wasm32, kotoba:typed):
   - Same sealed schemas as 0250–0253
   - `entropy_req_rec_kv_edn` → `{:n N}` with N ∈ [1, 64]
   - `entropy_reply_hex_rec_kv_edn` → `{:tag :hex :hex "…"}` (hex validate)
   - `entropy_reply_error_rec_kv_edn` → `{:tag :error :code "…" :message "…"}`
   - main → **-2504**
2. Closes entropy kit **W4 recursive EDN** residual (codec identity).
3. Does **not** flip `:wasm-aot :implemented` — **CSPRNG host-injected**.

## Evidence

- Package sha `712d5cc0…`; browser-host main → -2504
- ops kit registry + sha tests

## Related

- T8.3 residual W4; ADR 0250–0253; entropy 0244 / 0167 / 0172
