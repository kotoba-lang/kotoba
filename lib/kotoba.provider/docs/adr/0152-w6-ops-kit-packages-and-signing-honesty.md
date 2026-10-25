# ADR 0152: W6 ops kit packages + signed-package honesty

- Status: Accepted
- Date: 2026-07-28

## Context

W6 landed dual-runtime reference implementations for process (20), scoped-fs
(19), secret (21), git (22), and entropy (23). Product handoff still listed
"network / secret capability packages" as **contract-only** and asked for
**production signed providers** (content-addressed Wasm).

HTTP already shipped as `http-v1.edn` with `:qualification` including
`:wasm-aot :pending`. Ops kits lacked matching kit EDN packages, so inventory
could not distinguish "code exists" from "packaged kit surface".

## Decision

1. Ship capability-kit EDN packages under
   `resources/kotoba/lang/capability-kits/` for:
   - `secret-v1` (id 21)
   - `process-v1` (id 20)
   - `scoped-fs-v1` (id 19)
   - `git-v1` (id 22)
   - `entropy-v1` (id 23)
2. Register them in `provider-conformance-v1.edn`.
3. Qualification honesty:
   - `:reference :implemented` + dual-runtime host transports **landed**
   - `:wasm-aot` / `:native-aot` / `:jit` / `:signed-content-addressed-package`
     remain **`:pending`** — do **not** claim production signed Wasm providers yet.

## Non-claims

- No content-addressed signed Component artifact for secret/http hosts
- No kbb grant-lowering for these ops kits
- SSH remains host-forever (no kit)

## Evidence

- Kit EDN files + conformance registration
- Existing dual-runtime tests (provider#24–#33)
- Inventory/handoff update

## Related

- ADR 0143–0151 ops kit contracts/transports
- com-cloudflare/murakumo product-shell dual-source (orthogonal guest pure path)
