# P3 — JS BSP multi-superstep driver (ADR-2606013600 D4)

Completes the browser Pregel loop: `pregel-driver.js` is the **browser-side
equivalent of `kotoba-vm::WasmPregelRunner`** — pure JS, runtime-agnostic. It
re-feeds a guest's `run()` output as the next input while `status == "continue"`,
driving a Component Model guest (transpiled by jco, running on the JS WebAssembly
engine) through multiple supersteps.

```js
// pregel-driver.js
export function pregelRun(guestRun, initialState, { maxSupersteps = 64 } = {}) {
  let ctx = encode(initialState), steps = 0, final = null; const trace = [];
  while (steps < maxSupersteps) {
    const out = decode(guestRun(ctx)); steps++; final = out; trace.push(out.status);
    if (out.status === 'continue') { ctx = encode({ n: out.n, acc: out.acc }); continue; }
    break;
  }
  return { supersteps: steps, final, trace };
}
```

`bsp-counter` is a tiny guest that returns `continue` for N supersteps (calling
`host-log` each step) then `ok` — exercising the multi-superstep loop. The same
driver runs the real `kotoba-guest` (which returns `ok` → 1 superstep).

## Reproduce (verified)

```sh
# build the guest (own workspace; move ~/.config/wasm-pkg/config.toml aside if it
# carries the old `default = "ghcr.io"` schema)
PATH="$HOME/.cargo/bin:$PATH" cargo component build --release --target wasm32-wasip2
npm install cbor-x @bytecodealliance/preview2-shim
npx @bytecodealliance/jco transpile \
  target/wasm32-wasip2/release/bsp_counter.wasm -o out --name bsp --map 'host-log=../host.js'
node run.mjs
```

Verified output:

```
supersteps: 4 | trace: continue,continue,continue,ok
final: {"status":"ok","n":0,"acc":"..."}
host-log calls per superstep: 4 → ["superstep n=3 acc=", ... , "superstep n=0 acc=..."]
P3 BSP MULTI-SUPERSTEP DRIVER: PASS ✅
```

This closes the P3 browser-native Pregel/UDF path end to end: a guest component
(the same ABI wasmtime runs natively) executes on the browser's WebAssembly
engine via jco, with host imports wired to `KotobaNode` (`../p3-kotoba-guest/`)
and a JS BSP driver orchestrating supersteps. Build artifacts gitignored.

## Real-browser verification (Chromium)

The same driver + jco guest run in an actual browser (not just node):

```sh
npm install cbor-x @bytecodealliance/preview2-shim esbuild
npx @bytecodealliance/jco transpile target/wasm32-wasip2/release/bsp_counter.wasm \
  -o out --name bsp --map 'host-log=../host.js'
# bundle for the browser (node:* externalised — the guest never invokes stdio)
npx esbuild browser-entry.mjs --bundle --format=esm --outdir=www \
  --platform=browser --external:'node:*'
cp out/bsp.core.wasm www/          # new URL('./bsp.core.wasm', import.meta.url)
# serve www/ and load index.html → globalThis.__bspResult
```

Verified in headless Chromium (Playwright):

```
__bspResult: {"supersteps":4,"trace":["continue","continue","continue","ok"],
              "final":{"status":"ok","n":0,"acc":"..."}}   (no console errors)
P3 BSP DRIVER — REAL BROWSER VERIFY: PASS ✅
```

The jco-transpiled Component guest instantiates on the browser's own WebAssembly
engine and the JS BSP driver loops it through supersteps — browser-native
Pregel/UDF, end to end. `browser-entry.mjs` is the bundle entry; `www/` is
build output (gitignored).
