# kotoba-lang/quickjs

QuickJS/QuickJS-NG WASM binary loading contract: magic-byte validation,
SHA-256 integrity checking, and JVM/CLJS binary loading
(`quickjs.binary/load-wasm-file` on the JVM, `load-url` on CLJS).

Split out of `kotoba-lang/browser` (ADR-2607051140), where it lived as
`browser.compat.quickjs-binary`.

## Scope: why this repo is smaller than "all of browser's QuickJS code"

`kotoba-lang/browser` has four other QuickJS-related namespaces
(`browser.compat.quickjs`, `-binding`, `-execution`, `-wasm`) that were
**not** moved here. They stay in `browser` because they are genuinely
coupled to that browser's own domain model — `quickjs-execution` alone
requires `browser.audit`, `browser.dom-bridge`, `browser.net`,
`browser.origin`, `browser.profile`, and `browser.runtime`. They describe
how a QuickJS engine's capability requests get routed through *that
browser's* specific audit/origin/profile/session model, not a generic,
reusable "run QuickJS" contract. Moving them here would have required
either duplicating browser's domain model in this repo or making this repo
depend back on `browser` (backwards for a low-level engine-binding
library).

`quickjs.binary` is the one namespace with zero such coupling — pure
byte/hash/file-IO concerns — so it's the only piece that is actually a
standalone, reusable "quickjs" library today.

## Maturity

| | |
|---|---|
| Role | engine-adapter substrate |
| Tests | `kbb -M:test` |
| Actual JS execution | not here — see `kotoba-lang/browser`'s `browser.compat.quickjs-wasm` (CLJS + `quickjs-emscripten-core`/`@jitl/quickjs-singlefile-cjs-release-sync`, not buildable from that repo today; no shadow-cljs/npm toolchain checked in) |

## Test

```bash
kbb -M:test
```
