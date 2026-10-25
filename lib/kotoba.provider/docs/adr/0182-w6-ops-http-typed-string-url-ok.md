# ADR 0182: T8.3 typed-string single-call http_url_ok (kotoba:typed host)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0171 pure http bounds; ADR 0178/0180 typed-string pattern

## Context

Http pure bounds (0171) check numeric limits only. Kit semantics require
`:schemes #{:https}` and `:url-bytes 4096`. Typed-string single-call packaging
for secret (0178) and scoped-fs (0180) is the established path for string
policy without pure Component embedding.

## Decision

| piece | role |
|---|---|
| `src/http_url_ok.kotoba` | single-call URL policy + `main` live vector |
| `http-url-ok-v1.wasm` | kotoba-compiler wasm32 + provenance |

`http_url_ok(url)` → `-1` empty, `-2` >4096, `-3` not `https://` prefix, `0` ok.

`main` live vector → `-130` (ok / empty / http / ok2).

Registry `:http-url-ok`, `:typed-host :kotoba.typed`, no Component.

### Honesty

- Host http-post I/O and SSRF allowlist remain authority
- Does not encode header/body structure (request EDN codec still open)
- `:wasm-aot` stays `:partial`

## Non-claims

- Not full request/result EDN codec AOT
- Not pure Component / signed-wasm flip
- Not live network success (T8.4)

## Evidence

- browser-host `main` → `-130n`
- digest match; exports `http_url_ok` + `main`

## Related

- T8.3; ADR 0162, 0165, 0171, 0178, 0180
