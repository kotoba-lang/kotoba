# ADR 0266: T8.3 guest process W4 host_spawn — encode + typed-cap-call wire 20

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0252 process-record-kv; 0260–0265 HTTP/secret host surfaces; 0264 roundtrips

## Context

HTTP (0260/0262) and secret (0265) have guest host surfaces that build W4
request EDN and forward via `typed-cap-call` for host inject. Process already
has pure W4 codecs and `process-w4-roundtrip` (0264). Missing: guest export
for process/spawn wire id **20**.

## Decision

1. Ship **process-w4-host-edn** (wasm32, kotoba:typed, policy `[:cap/call 20]`):
   - Pure `process_req_rec_kv_edn` / `process_reply_ok_rec_kv_edn`
   - `host_spawn_edn` = encode then `(typed-cap-call 20 :string :string req)`
   - `main` pure → **-2508**
2. edn-codec: inject mode `:process-ok`; `process-w4-host-spawn-edn` with
   `:echo` / `:process-ok`; deny without allow.
3. Does **not** flip `:wasm-aot :implemented` — OS spawn remains host-injected.

## Evidence

- Package sha `530fa9c5…`; browser-host main → -2508; host_spawn inject tests

## Related

- T8.3 host authority residual; ADR 0260–0265; process kit id 20
