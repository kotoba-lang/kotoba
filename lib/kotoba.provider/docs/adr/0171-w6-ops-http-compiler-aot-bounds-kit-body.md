# ADR 0171: T8.3 first compiler-AOT ops kit body slice (http-post bounds)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0162/0165 http real-bytes + Component; kotoba-compiler wasm32-kotoba-v1

## Context

Ops kits (http/secret/process/scoped-fs/git/entropy) shipped thin
`:wasm-component` packages that flip readiness `:signed-wasm :ready`
(ADR 0165–0170), but every kit kept `:wasm-aot :partial` because the
**kit body** (product logic derived from kit EDN `:limits` / `:request` /
`:result`) was either:

1. a host-import forwarder (http-post), or
2. hand-written pure policy WAT (secret name, process bounds, …)

T8.3 residual after Components is **compiler-AOT kit body** — product policy
emitted by `kotoba-compiler`, not hand-authored WAT.

## Decision

### First slice: pure http-post `:limits` checker

`http-v1.edn` declares:

```
:limits {:url-bytes 4096 :headers 32 :body-bytes 65536 :timeout-ms [1 30000]}
```

Ship a **compiler-emitted** pure function:

```
http_post_bounds_ok(url-len, headers-n, body-len, timeout-ms) → i64
```

Error codes: `-1` url, `-2` headers, `-3` body, `-4` timeout; `0` ok.

| artifact | role |
|---|---|
| `src/http_post_bounds.kotoba` | source of truth (entryless `(:export [http_post_bounds_ok])`) |
| `http-post-bounds-v1.wasm` | `kotoba-compiler` `--target wasm32` output + provenance |
| `http-post-bounds-v1.component.wasm` | `wasm-tools component new` embed of core |

Registry names `:http-post-bounds` / `:http-post-bounds-component` with
`:class :ops-network`, `:builder :kotoba-compiler/v1`, non-fixture.

### Honesty

- **Does not** flip `:wasm-aot` to `:implemented` — full request/result EDN
  codec AOT (record/variant headers/body strings) remains open
- **Does not** replace host `http-post` I/O or ADR 0165 thin forwarder
- Provenance custom sections prove `kotoba-compiler/1` + `wasm32-kotoba-v1`
- Hand-written WAT path is intentionally **not** used for this export

### Rebuild recipe (optional)

```sh
kbb -Sdeps '{:deps {io.github.kotoba-lang/compiler
  {:git/url "https://github.com/kotoba-lang/compiler.git"
   :git/sha "<compiler pin>"}}}' \
  -M -m kotoba.compiler.cli compile \
  resources/kotoba/lang/wasm-packages/src/http_post_bounds.kotoba \
  --target wasm32 \
  --output resources/kotoba/lang/wasm-packages/http-post-bounds-v1.wasm
wasm-tools component new \
  resources/kotoba/lang/wasm-packages/http-post-bounds-v1.wasm \
  -o resources/kotoba/lang/wasm-packages/http-post-bounds-v1.component.wasm
# refresh sha256 in wasm-packages-v1.edn
```

## Non-claims

- Not multi-file kit project mode with `:capabilities #{:http/post}`
- Not secret/process/… compiler re-emit of existing hand WAT
- Not live network success proof (T8.4 qualification)

## Evidence

- digest match module + Component
- Node/WebAssembly: ok path → 0; each limit violation → matching error code
- provenance `:builder :kotoba-compiler/v1`
- http kit notes + readiness evidence list ADR 0171

## Related

- Reliability WBS T8.3
- ADR 0162–0170
- Frontier ADR-2607299400 Progress residual “compiler-AOT kit body”
