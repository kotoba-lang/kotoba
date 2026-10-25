# ADR 0208: T8.3 ops typed-string Component surface complete (secret + scoped-fs)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0205 (HTTP packing surface complete); ADR 0206 secret_name_ok
  Component; ADR 0207 fs_path_ok Component; kit-readiness inventory

## Context

ADR 0205 closed the **HTTP** packing-walk pure Component surface (0199–0204)
and parked nested EDN under W4. Secret and scoped-fs still had typed-string
single-call packages (`secret_name_ok` ADR 0178, `fs_path_ok` ADR 0180) that
either lacked Component twins or could miscompile under the wrong Canonical
shape (header tchar misfit — fixed in kotoba-component#100/#101).

## Decision

1. **Inventory honesty:** kit-readiness evidence now lists
   `secret-name-ok-v1.component.wasm` (ADR 0206) and
   `fs-path-ok-v1.component.wasm` (ADR 0207) alongside prior twins.
2. **Declare ops typed-string single-call Component surface complete** for
   http + secret + scoped-fs policy packages that have pure Canonical re-emits.
3. **Keep all ops kits `:wasm-aot :partial`** — nested kit `:request`/`:result`
   EDN codec and full multi-file kit project body remain **W4-gated**.

### Honesty

- Does **not** flip any kit `:wasm-aot` to `:implemented`
- Does **not** implement recursive EDN encode of header sets / result variants
- Does **not** claim multi-file kit project mode with capability grants

## Evidence

- Registry twins + wasmtime live mains: secret `-130`, fs-path `-15470`
- kit-readiness summary/evidence/notes updated this ADR
- Frontier Progress residual points at W4 nested EDN only (not missing packages)

## Related

- T8.3; ADR 0178, 0180, 0205–0207; frontier ADR-2607299400 Progress 31dh/31dj
- W4 recursive values; T8.4 host_parity_live optional expansion
