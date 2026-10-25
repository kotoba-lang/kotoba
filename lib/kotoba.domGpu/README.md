# kotoba-lang/dom-gpu

[![CI](https://github.com/kotoba-lang/dom-gpu/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/dom-gpu/actions/workflows/ci.yml)

## Node types

The `kotoba:dom` document holds three node types, and the split between the
last two matters to every consumer:

| type | `tree` (layout view) | `comment-tree` (DOM view) | `text-content` |
|---|---|---|---|
| `:element` | map with `:tag`/`:attrs`/`:children` | same | children joined |
| `:text` | bare string | bare string | its text |
| `:comment` | **omitted** | `{:node/type :comment :text ...}` | `""` |

A comment has no box, no text and no effect on layout, so admitting a third
shape into `tree` would push comment-awareness into every layout path in
`cssom.layout` for no benefit. It is still a real node with a real id — a
later mutation can reference it — so the node map and the retained host both
keep it, and `comment-tree` is the view for consumers looking at the DOM
rather than laying it out (a parser conformance harness comparing against a
real browser's node list, a devtools inspector, a serializer).

Comments were added on 2026-08-04. Before that there was **no comment node
type anywhere in this stack**, which is why `htmldom` dropped every
`<!-- ... -->`: it had nowhere to put one. Dropping a comment does not only
lose the comment — it merges the text on either side into a single node
where a browser keeps two.

Renamed from `kotoba-lang/wasm-ui` (see
`90-docs/adr/2607051200-kotoba-lang-ui-family-rename.md` in
`com-junkawasaki/root`) to avoid collision with the unrelated `kotoba-ui`/
`appkit`/`uikit` app design-system family and to name what this repo actually
is: the `kotoba:dom` retained-tree lowered to GPU draw ops. Internal build
target names (`wasm-ui`/`wasm-webgpu` npm scripts, `kotoba-wasm-ui.html`) are
unchanged by this rename.

This project hosts the kotoba DOM-compatible WASM UI substrate and the browser
reference renderers:

- `wasm-ui`: WebGL retained-tree renderer with text canvas overlay
- `wasm-webgpu`: WebGPU retained-tree renderer with text canvas overlay

The substrate keeps Reagent/re-frame-shaped CLJS code portable by providing
small compatibility namespaces in `src/reagent/core.cljk` and
`src/re_frame/core.cljk`. UI is lowered into a kotoba virtual document, encoded
as the `kotoba:dom` host ABI, retained by renderer hosts, then projected to draw
ops for WebGL/WebGPU.

```sh
npm install
npm run check:wasm-ui

npm run compile:wasm-ui
npm run compile:wasm-webgpu
python3 -m http.server 8701 -d public
# http://localhost:8701/kotoba-wasm-ui.html
# http://localhost:8701/kotoba-wasm-webgpu.html
```

Browser debug hooks:

```js
kotoba.wasm.demo.debug_snapshot()
kotoba.wasm.demo_webgpu.debug_snapshot()
```

Coverage entry points:

```sh
kbb -M:test -n kotoba.wasm.compat-api-test
kbb -M:test -n kotoba.wasm.dom-compat-test
kbb -M:test -n kotoba.wasm.abi-runtime-test
kbb -M:test -n kotoba.wasm.debug-test
kbb -M:test -n kotoba.wasm.retained-host-test
kbb -M:test -n kotoba.wasm.wit-contract-test
kbb -M:test -n kotoba.wasm.golden-test
kbb -M:test
```
