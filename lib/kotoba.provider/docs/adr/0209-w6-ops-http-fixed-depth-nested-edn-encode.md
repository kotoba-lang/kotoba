# ADR 0209: T8.3 fixed-depth nested EDN encode (header + request0)

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0205 packing surface complete / nested EDN residual; ADR 0208
  typed-string Component surface complete

## Context

ADR 0205 parked **nested EDN codec** of kit `:request`/`:result` under W4
recursive values. Packing walks (0192–0193 / 0203–0204) validate fields
without producing a nested EDN value. Product hosts still need a pure
string encode path for fixed-depth request surfaces that does **not** wait
on general recursive schema identity in Component v1.

## Decision

Ship a **fixed-depth** nested EDN encode package (compiler-AOT wasm32,
no `kotoba:typed`):

| Export | Meaning |
|--------|---------|
| `edn_quoted` | quote a string atom; reject `"` / `\` (no escape table) |
| `http_header_edn` | `{:name "…" :value "…"}` |
| `http_request_edn0` | `{:url "…" :headers [] :body "…" :timeout-ms N}` (0 headers) |
| `main` | length fingerprint **27005800** |

| artifact | sha256 (prefix) |
|----------|-----------------|
| `http-request-edn-v1.wasm` | `a7cfc22c…` |

Registry `:http-request-edn`. kit-readiness + http-v1 notes updated.

### Honesty

- Does **not** flip `:wasm-aot` to `:implemented`
- Does **not** encode multi-header sets, result variants, or recursive ADTs
- Does **not** Component re-emit (wasm32 module only)
- Does **not** claim W4 recursive value identity — fixed depth only

### Rebuild

```sh
kbb -Sdeps '{:deps {io.github.kotoba-lang/compiler
  {:git/url "https://github.com/kotoba-lang/compiler.git"
   :git/sha "98b56bdb6886236281b634cc3409088ed2fe72a4"}
  io.github.kotoba-lang/abi
  {:git/url "https://github.com/kotoba-lang/abi.git"
   :git/sha "34415ce9bf2b8d37d5bc8259ba7e00f5d091eb44"}}}' \
  -M -e '(require (quote [kotoba.compiler.core :as c])) … write :bytes …'
```

## Evidence

- KIR execute: header `{:name "X-Ok" :value "yes"}`, reject `a"b` → empty,
  request0 `{:url "https://x" :headers [] :body "{}" :timeout-ms 1000}`
- `main` → **27005800**; package registry sha matches artifact
- Tests: `http-request-edn-package-registered`

## Related

- T8.3; ADR 0205 residual; frontier ADR-2607299400
- Follow-up: multi-header set encode; result variant EDN; Component twin;
  W4 recursive value identity when admissible
