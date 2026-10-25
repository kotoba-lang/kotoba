# kotoba-lang/css

Static CSS-in-Clojure with shadow-css-compatible class semantics and portable EDN sheets.

This is compatible with the small `kami.css` style DSL: maps render to
declarations, `:rules` render to selectors, `:keyframes` render to keyframes,
numbers become `px` except for unitless properties and zero, vectors become
space-joined CSS values, and keywords become bare CSS identifiers.

`kotoba.css.shadow/css` returns a source-position-derived class string. `css.build`
indexes those static forms, validates and deterministically emits targeted CSS with
optional minification. No browser runtime CSS generator is shipped.


## Maturity

| | |
|---|---|
| Role | ui-substrate |
| Tests | `kbb -M:test` |
| Operator console (UI/UX) | — |
| Export (CSV/JSON) | — |
| Shared CSS design system | yes (css.core/operator-theme) |
| Static source indexing | yes (`css.build/index-shadow-source`) |
| Targeted utility output | yes (`css.utility`) |
| JVM Clojure contract | CI tested |
| Node ClojureScript contract | CI tested with nbb |

## Compatibility boundary

- Static EDN sheets, declaration maps, keyframes, media rules and inline styles are stable.
- `kotoba.css.shadow/css` forms are build-time indexed; CSS generation is never shipped to the browser.
- Utility classes are a strict finite catalog. Unsupported utilities fail the strict build.
- Values and selectors that could terminate a declaration or rule are rejected.
- Dynamic styling uses conditional classes, inline style or CSS custom properties, not runtime rule generation.

## Kotoba port (`kotoba/`)

`.kotoba` ports of the string-producing halves of this library live under
`kotoba/`, alongside — never instead of — the `.cljc` under `src/`
(ADR-2607270100 §10). Each is gated by a byte-equality parity test that
compiles the port and runs it through the KIR interpreter in the test JVM.
`kotoba-lang/compiler` is a **test-only** dependency; consumers keep requiring
`css.core` / `css.utility`.

| module | ports | stays in `.cljc`, and why |
|---|---|---|
| `kotoba/css_core.kotoba` | `css.core` declaration/rule text | — |
| `kotoba/css_document.kotoba` | the same rules as a logical `:document` value | — |
| `kotoba/css_utility.kotoba` | `css.utility` `escape-class`, the variant split, the media-query and spacing-scale lookups, and the regex-driven utility families | `static-utilities` (90 entries; a Kotoba typed map holds 31, and its values are heterogeneous), `opacity-N` (a double the host prints; there is `string-from-i64` but no f64 printer), and `rules` / `media-rules` / `unsupported`, which build maps keyed by selector |

Both excluded boundaries are asserted by the parity test rather than left as
prose: every corpus token is checked to be absent from `static-utilities`, and
`opacity-N` has a fixture showing the port reports it as unsupported instead of
approximating it.

## Test

```bash
kbb -M:test
kbb -M:lint
kbb --backend sci test/run_nbb_contract_tests.cljk
```
