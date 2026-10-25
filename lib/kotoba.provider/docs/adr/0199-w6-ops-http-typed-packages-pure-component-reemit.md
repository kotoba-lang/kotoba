# ADR 0199: T8.3 pure Component re-emit of typed HTTP policy packages

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0182/0186/0190/0191 typed-string packages; kotoba-component#86–#92 multi-export + helper admission; `kotoba compile --target component`

## Context

ADR 0182–0191 shipped **typed-host** wasm modules (`kotoba:typed` import) for
HTTPS URL, post-request, response surface, and error/result-arm policies.
Those modules prove policy on the typed ABI but are **not pure Components** —
Component Model hosts cannot instantiate them without a typed host.

kotoba-component multi-export Canonical lowering (`:https-url-ok-with-main`,
`:http-post-request-ok-with-main`, `:http-response-package-with-main`,
`:http-error-package-with-main`, plus helper-mediated `code-ok` admission in
#92) now lets the **same `.kotoba` sources** compile via
`kotoba compile --target component` into pure Components with Canonical
string ABI and **no** `kotoba:typed` import.

## Decision

Re-emit four pure Components from the existing sources and register twins:

| source | module (typed) | Component (pure) | live `main()` |
|---|---|---|---|
| `http_url_ok.kotoba` | `:http-url-ok` | `:http-url-ok-component` | **-130** |
| `http_post_request_ok.kotoba` | `:http-post-request-ok` | `:http-post-request-ok-component` | **-13406** |
| `http_response_ok.kotoba` | `:http-response-ok` | `:http-response-ok-component` | **-1012** |
| `http_error_result_ok.kotoba` | `:http-error-result-ok` | `:http-error-result-ok-component` | **-13501** |

| artifact | role |
|---|---|
| `*.component.wasm` | `kotoba-compiler` `--target component` (Canonical via kotoba-component) |
| `*.component.wasm.provenance.edn` | builder `:kotoba-compiler/v1`, target `:wasm-component-kotoba-v1` |
| registry `:*-component` | `:artifact-kind :wasm-component`, `:component-lowering :kotoba-component/canonical`, **no** `:typed-host` |

### Honesty

- **Does not** flip `:wasm-aot` to `:implemented` — nested request/result EDN
  codec + full kit body AOT remain open
- **Does not** replace host `http-post` I/O or retire typed-host modules
  (typed modules stay for browser-host / typed ABI consumers)
- Charset / length / scheme checks for error/url/request are owned by the
  Canonical lowering (WAT), matching the typed module live vectors
- Header name/value/set packing and pure memory-scan packages are **out of
  scope** for this ADR (separate residual)

### Rebuild recipe

```sh
# requires kotoba-component pin ≥ f857f8e3 (helper-mediated error package)
kbb -Sdeps '{:deps {io.github.kotoba-lang/kotoba-component
  {:git/url "https://github.com/kotoba-lang/kotoba-component.git"
   :git/sha "f857f8e3a5a1ffb117a200d6a3c3c1c3e69edcc9"}}}' \
  -M -m kotoba.compiler.cli compile \
  resources/kotoba/lang/wasm-packages/src/http_error_result_ok.kotoba \
  --target component \
  --output resources/kotoba/lang/wasm-packages/http-error-result-ok-v1.component.wasm
# similarly for http_url_ok / http_post_request_ok / http_response_ok
# refresh sha256 in wasm-packages-v1.edn
```

## Non-claims

- Not full request/result EDN nested record packing as one Component export
- Not header set uniqueness / W4 recursive values
- Not live network success (T8.4)
- Not secret/process/git typed-string Component re-emit (separate tracks)

## Evidence

- digest match for each Component vs registry sha256
- wasmtime: `main()` live vectors (-130 / -13406 / -1012 / -13501)
- provenance `:builder :kotoba-compiler/v1`, format `:wasm-component`
- http kit notes list ADR 0199; `:wasm-aot` stays `:partial`

## Related

- Reliability WBS T8.3
- ADR 0182, 0186, 0190, 0191 (typed modules)
- kotoba-component#86–#92
- Frontier ADR-2607299400 Progress residual “provider registry Component re-emit”
