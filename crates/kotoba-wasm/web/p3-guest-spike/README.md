# P3 spike — browser-native Pregel/UDF guest via jco (ADR-2606013600 D4)

Proves the P3 claim: **a WASM Component Model guest runs on the browser's native
WebAssembly engine via `jco`, calling back into JS-implemented host functions** —
no `wasmtime` in the browser. The same component runs under wasmtime natively
and under the browser engine here; one guest ABI, two runtimes.

`wasmtime` does not target wasm32, so "run wasmtime in the browser" is a
non-goal. Instead the guest `.wasm` (built once with `cargo component`) is
transpiled by `jco` into an ES module that the browser's own WebAssembly engine
executes; the host imports it needs are satisfied by JS shims wired to the
in-browser `KotobaNode`.

## What this spike contains

- `wit/world.wit` — a minimal `pregel` world: imports one host fn `host-get`,
  exports `run(input) -> string` (a single BSP superstep contract).
- `src/lib.rs` — the guest: `run()` calls `host-get` and returns a result.
- `host.js` — the host shim. Here it returns `kotoba-host[<key>]`; in production
  this is where the kotoba host WIT interfaces call back into `KotobaNode`.
- `runner.mjs` — a node harness that loads the transpiled module and calls `run`.

## Reproduce (verified)

```sh
# 1) build the Component (own workspace — uses wasm32-wasip2)
#    NOTE: ~/.config/wasm-pkg/config.toml may carry an old `default = "ghcr.io"`
#    schema that newer cargo-component rejects; move it aside for the build.
PATH="$HOME/.cargo/bin:$PATH" cargo component build --release --target wasm32-wasip2

# 2) transpile the Component to JS (browser/node WebAssembly engine + jco)
npm install @bytecodealliance/preview2-shim
npx @bytecodealliance/jco transpile \
  target/wasm32-wasip2/release/pregel_spike.wasm -o out --name pregel \
  --map 'host-get=./host.js'
cp host.js out/host.js

# 3) run the guest on the JS engine with the host import wired
node runner.mjs
```

Verified output:

```
guest run() returned: "pregel-superstep(input=vertex-42) host-said=kotoba-host[vertex-42]"
P3 jco SPIKE: PASS ✅ (Component Model guest ran on the JS WebAssembly engine + called back into the JS host)
```

## Productionizing into the kotoba browser node

The spike wires ONE host fn. For real `kotoba-guest` Pregel/UDF in the browser:

1. Build the existing `crates/kotoba-guest` (the `kotoba-node` world) with
   `cargo component build --target wasm32-wasip2` — the SAME component the native
   `kotoba-runtime::WasmExecutor` already runs. No fork.
2. `jco transpile` it; satisfy WASI-P2 with `@bytecodealliance/preview2-shim`.
3. Implement the kotoba host WIT interfaces in JS, wired to `KotobaNode`:
   - `kotoba:kais/kqe.{assert-quad,retract-quad,query,get-objects,get-head}`
     → the in-wasm arrangement (read) / local transact (write).
   - `kotoba:kais/kse.{publish,drain}` → a local journal (OPFS).
   - `kotoba:kais/auth.*` → the member DID / CACAO (read-only).
   - `kotoba:kais/llm.*` → **disabled** in the storage node (Murakumo-only,
     ADR-2605215000).
4. Rust side: add a `GuestRuntime` trait; the pure-Rust `WasmPregelRunner` (BSP
   orchestrator) stays unchanged and drives either `WasmtimeRuntime` (native) or
   `BrowserComponentRuntime` (this jco path) per target.

The `out/`, `target/`, and `node_modules/` build artifacts are gitignored; this
directory holds the source + the verified recipe only.
