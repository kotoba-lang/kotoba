# ADR 0260: T8.3 guest W4 host_post surface — encode + typed-cap-call

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0250 recursive-record-kv; host pure codec 0256–0259

## Context

Host pure-EDN codec wire (0256–0259) invokes W4 packages from the JVM via
browser-host. Residual host-I/O honesty still lacked a **guest-side** surface
that (1) builds W4 request EDN and (2) forwards via `typed-cap-call :http/post`
for host injection — the path between pure encode and live network authority.

## Decision

1. Ship **http-w4-host-edn** (wasm32, kotoba:typed, policy `[:cap/call 4]`):
   - Schemas: same W4 `:edn/kv` + `:edn/node` as ADR 0250
   - `request_rec_kv_edn` / `result_ok_rec_kv_edn` pure encode
   - `host_post_edn` = encode then `(typed-cap-call :http/post :string :string req)`
   - `main` pure encode proof → **-2506** (no live network in main)
2. Host must inject capability id 4 for `host_post_edn`; deny-by-default.
3. Does **not** flip `:wasm-aot :implemented` — live HTTP authority remains
   host-injected; this package only wires guest encode + capability forward.

## Evidence

- Package sha `4f22e626…`; browser-host main → -2506
- Registry + sha tests; policy edn co-located

## Related

- T8.3 host authority residual; ADR 0250; 0256–0259; typed-cap-call http/post
