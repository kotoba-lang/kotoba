# ADR 0203: T8.3 pure Component re-emit of request packing walk

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0193 typed request packing; kotoba-component#98
  (`:http-request-pack-package-with-main` + nested live-main);
  `kotoba compile --target component`

## Context

ADR 0193 shipped a **typed-host** host-sequenced request packing walk
(`begin` / `url` / `headers` / `body` / `end`). Header packages and
headers-set packing (ADR 0199–0202) already re-emit as pure Components.
The request walk needs six exports and nested live-main chains that
compose the state machine, including a Canonical `https://` URL scan.

kotoba-component#98 admits the package and Canonical WAT phase machine.

## Decision

| source | module (typed) | Component (pure) | live `main()` |
|---|---|---|---|
| `http_request_pack.kotoba` | `:http-request-pack` | `:http-request-pack-component` | **-13467** |

### Honesty

- Does **not** flip `:wasm-aot` to `:implemented`
- Does **not** re-emit result packing walk (0192)
- Does **not** pack nested EDN records

### Rebuild recipe

```sh
# requires kotoba-component pin ≥ 5ce90f13
kbb -Sdeps '{:deps {io.github.kotoba-lang/kotoba-component
  {:git/url "https://github.com/kotoba-lang/kotoba-component.git"
   :git/sha "5ce90f130c6f38e8c699d64685bebd36fef2c1f7"}}}' \
  -M -m kotoba.compiler.cli compile \
  resources/kotoba/lang/wasm-packages/src/http_request_pack.kotoba \
  --target component \
  --output resources/kotoba/lang/wasm-packages/http-request-pack-v1.component.wasm
```

## Evidence

- digest match; wasmtime `main()` → **-13467**; begin()→0; url(0,"http://x")→-3
- provenance `:builder :kotoba-compiler/v1`, target `:wasm-component-kotoba-v1`
- `:wasm-aot` stays `:partial`

## Related

- T8.3; ADR 0193, 0199–0202; kotoba-component#98
- Frontier residual “request/result packing walks Component re-emit”
