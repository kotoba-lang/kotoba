# ADR 0265: T8.3 guest secret W4 host_get — encode + typed-cap-call wire 21

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0251 secret-record-kv; 0260–0262 HTTP host surface/inject; 0264 roundtrips

## Context

HTTP gained a guest host surface (0260) + live inject (0262). Secret already
has pure W4 codecs and `secret-w4-roundtrip` (0264) on the host JVM path.
Missing: guest export that builds W4 request EDN and forwards via
`typed-cap-call` for host inject — wire id **21** (provider kit `secret/get`).

Compiler catalog does not yet list `:secret/get` as a named capability;
numeric wire id 21 is used (same as provider kit id). Catalog registration
is a follow-up in kotoba-lang authority.

## Decision

1. Ship **secret-w4-host-edn** (wasm32, kotoba:typed, policy `[:cap/call 21]`):
   - Pure `secret_request_rec_kv_edn` / `secret_reply_value_rec_kv_edn`
   - `host_get_edn` = encode then `(typed-cap-call 21 :string :string req)`
   - `main` pure → **-2507**
2. edn-codec: generalize inject primary-cap-id; `secret-w4-host-get-edn`
   with `:echo` / `:secret-value` inject modes; deny without allow.
3. Does **not** flip `:wasm-aot :implemented`.

## Evidence

- Package sha `075a3d1f…`; browser-host main → -2507; host_get with inject
- Registry + edn-codec optional host tests

## Related

- T8.3 host authority residual; ADR 0260–0264; provider secret kit id 21
