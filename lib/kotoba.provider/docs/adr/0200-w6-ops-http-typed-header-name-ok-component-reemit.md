# ADR 0200: T8.3 pure Component re-emit of typed http_header_name_ok

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0187 typed header_name_ok; kotoba-component#93–#94
  (`:http-header-name-ok-with-main` + frontend loop-desugar admission);
  `kotoba compile --target component`

## Context

ADR 0187 shipped a **typed-host** wasm module (`kotoba:typed` import) for
RFC 7230 tchar header-name policy. ADR 0199 re-emitted url/request/response/
error packages as pure Components; header packages remained typed-only.

kotoba-component#93 adds Canonical lowering for `http_header_name_ok` (+ live
main → **-130**). #94 admits the real frontend loop desugar
`(__kotoba_loop_*)` so the provider source compiles without requiring `-3`
on the exported function body (charset stays in the unexported loop / WAT).

## Decision

Re-emit one pure Component and register a twin:

| source | module (typed) | Component (pure) | live `main()` |
|---|---|---|---|
| `http_header_name_ok.kotoba` | `:http-header-name-ok` | `:http-header-name-ok-component` | **-130** |

| artifact | role |
|---|---|
| `http-header-name-ok-v1.component.wasm` | `kotoba-compiler` `--target component` |
| `*.component.wasm.provenance.edn` | builder `:kotoba-compiler/v1`, target `:wasm-component-kotoba-v1` |
| registry `:http-header-name-ok-component` | `:artifact-kind :wasm-component`, `:component-lowering :kotoba-component/canonical`, **no** `:typed-host` |

### Honesty

- Does **not** flip `:wasm-aot` to `:implemented`
- Does **not** re-emit header value/pair (0188) or set packing walk (0189)
- Does **not** replace host `http-post` I/O or retire the typed-host module

### Rebuild recipe

```sh
# requires kotoba-component pin ≥ cfcc0a23 (loop-desugar admission)
kbb -Sdeps '{:deps {io.github.kotoba-lang/kotoba-component
  {:git/url "https://github.com/kotoba-lang/kotoba-component.git"
   :git/sha "cfcc0a23eba43dbc4cb83e593a3509237cdc1612"}}}' \
  -M -m kotoba.compiler.cli compile \
  resources/kotoba/lang/wasm-packages/src/http_header_name_ok.kotoba \
  --target component \
  --output resources/kotoba/lang/wasm-packages/http-header-name-ok-v1.component.wasm
```

## Non-claims

- Not header value/pair multi-export Component
- Not headers-set packing walk Component
- Not request/result packing walks Component
- Not nested EDN / full kit body / live network (T8.4)

## Evidence

- digest match Component vs registry sha256
- wasmtime: `main()` → **-130**; `Content-Type`→0; empty→-1; `Bad Name`→-3
- provenance `:builder :kotoba-compiler/v1`, format `:wasm-component`
- http kit notes list ADR 0200; `:wasm-aot` stays `:partial`

## Related

- Reliability WBS T8.3
- ADR 0187 (typed module); ADR 0199 (sibling re-emit pattern)
- kotoba-component#93–#94
- Frontier ADR-2607299400 residual “header typed package Component re-emit”
