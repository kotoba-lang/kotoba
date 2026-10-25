# ADR 0255: T8.3 / W4 scoped-fs kit record-typed recursive EDN

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0250–0254 record-kv pattern; ADR 0243 fixed-depth scoped-fs EDN

## Context

Entropy W4 landed as 0254 (concurrent). Scoped-fs was the last ops kit still
marked **W4 open**. Host store remains host-injected. Path policy matches 0243.

## Decision

1. Ship **scoped-fs-record-kv-edn** (wasm32, kotoba:typed):
   - Same sealed `:edn/kv` + `:edn/node` as 0250+
   - read/write request + content/written/error reply arms
   - main → **-2505**
2. Closes last ops-kit pure **W4 recursive EDN** residual.
3. Does **not** flip `:wasm-aot :implemented` — host store open.

## Evidence

- Package sha `9121592e…`; browser-host main → -2505

## Related

- T8.3 residual W4; ADR 0243; host store authority
