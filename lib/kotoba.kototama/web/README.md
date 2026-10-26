# kototama browser WASM AOT demo

Proof that a `.kotoba`-emitted WASM binary can run **directly in a
browser's own WebAssembly engine** (already-AOT-compiled machine code, no
interpreter step), wrapped as a WebComponent — via
[`kotoba-lang/wasm-webcomponent`](https://github.com/kotoba-lang/wasm-webcomponent),
not hosted on the JVM, and not this repo's own copy of that hosting code
anymore (see "History" below).

## Files

- `demo.wasm` — byte-for-byte output of `kotoba wasm emit src/demo.kotoba`
  in `kotoba-lang/kotoba` (73 bytes, zero imports, exports `main() : i32`
  which computes `40 + 2`).
- `demo-kgraph.wasm` — byte-for-byte output of
  `kotoba wasm emit src/demo_kgraph.kotoba --policy src/demo_kgraph_policy.edn`
  (219 bytes; declares the `kgraph_assert`/`kgraph_query` imports).
- `actor-host-demo.wasm` — hand-assembled (`wasm-tools`) module importing
  `clock_monotonic`/`log_write`/`sha256_hex` (module `"kotoba"`) -- exercises
  `kototama.contract`'s `actor:host` ABI (partial), same fixture as
  `kotoba-lang/wasm-webcomponent`'s `examples/actor-host/`.
- `index.html` — **generated**, not hand-written (see `generate.cljs`
  below). Imports `KotobaWasmElement` + `kgraph.js` + `actor-host.js` from
  `kotoba-lang/wasm-webcomponent` (pinned commit, via jsdelivr's GitHub
  proxy) and defines three custom elements. No hosting logic lives in
  this repo.
- `generate.cljs` — an `nbb` (ClojureScript-on-Node) script that builds
  `index.html` from Hiccup EDN via
  [`kotoba-lang/html`](https://github.com/kotoba-lang/html)
  (`html.core/render`) and
  [`kotoba-lang/css`](https://github.com/kotoba-lang/css)
  (`css.core/style-node`), matching the org's `.cljc` runtime priority
  (kototama > cljs > nbb > jvm) applied to *authoring* this page. The
  `<script type="module">` WebComponent-wiring block is genuine
  executable JS, passed through verbatim via `[:hiccup/raw ...]`
  (html.core's own escape hatch for trusted markup). Regenerate after
  editing:
  ```bash
  cd web
  kbb --backend sci --classpath "../../html/src:../../css/src" generate.cljs
  ```
  (adjust the `--classpath` entries to wherever your west checkout has
  `kotoba-lang/html` and `kotoba-lang/css`). The output is still a plain
  static file — no build step for a browser visiting the page, only for
  regenerating it.
- `verify.mjs` / `verify-kgraph.mjs` / `verify-actor-host.mjs` —
  dependency-free Node smoke tests for the three `.wasm` files above.
  Node has no flag-free way to `import()` an `https:` URL, so the latter
  two fetch the pinned source and hand it to a `data:` URL instead
  (standard ESM, works on any Node ≥ 18).

## Run it

```bash
cd web && python3 -m http.server 8123
# open http://localhost:8123/ in a browser
```

## Scope (honest R2 advanced-partial)

Maturity ladder: top-level [`docs/maturity.md`](../docs/maturity.md).
Parity matrix: `kototama.browser` / `kbb -M:cli parity`.

### actor:host (wasm-webcomponent `actor-host.js`)

| Import | Browser tab | Notes |
|---|---|---|
| gen-keypair / sign / verify | **yes** | sync via vendored `@noble/curves` |
| sha256-hex / clock-monotonic | **yes** | |
| log-read / log-write | **yes** | injectable store |
| llm-infer | **no** in tab | Node can inject `opts.llmInfer` |
| http-post | **yes** in tab | Worker-hosted guest + `createSabHttpPostBridge` (SharedArrayBuffer+Atomics.wait); needs COOP/COEP; `opts.httpPost` inject also available on Node |

**9/9** imports are browser-linkable (`http-post` and `llm-infer` both real
via a Worker-hosted SAB+Atomics bridge in `wasm-webcomponent`; `llm-infer`
additionally needs a caller-supplied proxy URL — see `../docs/maturity.md`).
`http-post` became real in a browser tab via `wasm-webcomponent` PR #8
(2026-07-16) — see `90-docs/adr/0007-http-post-paths-and-fleet-persist-execute.md`'s
second addendum for the two real bugs that had to be fixed to get there.
Without a cross-origin-isolated page or an inject backend, `http_post` is
**absent** from the import object (clear link error — not a silent fake
success).

### Host-free guests (R2)

| File | Expected `main` |
|---|---|
| `demo.wasm` | 42 |
| `host-free-fact.wasm` | 120 |
| `host-free-peak-cells.wasm` | 240 |

```bash
node web/verify-host-free.mjs
```

### Other surfaces

- **`kgraph.js`**: kgraph assert/query only; **no** HostCaps re-enforcement at
  load (emit-time policy only). `actor-host.js` **does** re-verify grants.
- Wider kotoba imports (`kse`/`auth`/`evm`/…) — not ported here.
- This is not a multi-tenant sandboxed fleet host (that's R3 skeleton+persist on
  JVM: `fleet.core` + disk/B2 store + `fleet.exec` tender bridge in
  `kotoba-lang/fleet`).

## History

This directory used to carry its own `kototama-wasm-run.js` /
`kototama-wasm-kgraph-demo.js` / `kgraph.js` (the original PoC, see git
history / ADR-2607061630). That code has been extracted into
`kotoba-lang/wasm-webcomponent` so other repos can reuse it instead of
copying it; this directory is now a **consumer** of that library, not the
canonical source for the hosting code.
# Kotoba Script host

`kotoba-script-host.mjs` verifies the compiler manifest and emitted source
digest before importing restricted ESM. `kotoba-script-worker-host.mjs` runs
the verified module in a terminating Worker boundary with bounded values,
arguments, source size, startup time, and execution time. Capability-provider
functions are never cloned from the page realm into the Worker.
