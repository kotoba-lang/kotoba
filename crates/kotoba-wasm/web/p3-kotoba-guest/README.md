# P3 — the REAL kotoba-guest, browser-native via jco (ADR-2606013600 D4)

Beyond the toy spike (`../p3-guest-spike/`): this runs the **actual production
`crates/kotoba-guest`** — the `kotoba-node` world, the SAME WASM Component the
native `kotoba-runtime::WasmExecutor` (wasmtime) executes — on the JS
WebAssembly engine via `jco`, with its host interfaces wired to the in-wasm
`KotobaNode` read/write engine. One guest ABI, two runtimes.

## What the guest does (`kotoba-guest::run`)

`run(ctx_cbor) -> output_cbor`, one BSP superstep:
1. `auth.current-did()` → executing member DID
2. `kqe.assert-quad({graph, subject=did, predicate:"kotoba/task", object-cbor=args})`
3. `kse.publish("kotoba/<graph>/invoked", args)` → topic CID
4. returns CBOR `{status, quads_asserted, agent_did, topic_cid}`

## Host wiring (`hosts/`)

jco maps each imported interface to a JS module:

| WIT import | JS shim | backing |
|---|---|---|
| `kotoba:kais/kqe` | `hosts/kqe.js` | `assert-quad` → `KotobaNode.transact` (real read engine) |
| `kotoba:kais/kse` | `hosts/kse.js` | local journal stub (topic CID) |
| `kotoba:kais/auth` | `hosts/auth.js` | member DID (read-only) |
| `kotoba:kais/llm` | — | not imported by this guest (Murakumo-only, ADR-2605215000) |

`hosts/node.js` holds the shared `KotobaNode`; the kqe shim writes into it and the
harness reads it back to prove the guest's quad landed.

## Reproduce (verified in node — same engine model as the browser)

```sh
# 1) build the REAL guest (own workspace; move ~/.config/wasm-pkg/config.toml
#    aside if it carries the old `default = "ghcr.io"` schema)
cd ../../../../crates/kotoba-guest
PATH="$HOME/.cargo/bin:$PATH" cargo component build --release --target wasm32-wasip2

# 2) build the KotobaNode node bindings (read/write engine)
cd ../kotoba-wasm && wasm-pack build --target nodejs --out-dir pkg-node --release
cp pkg-node/* web/p3-kotoba-guest/pkg/

# 3) transpile the guest, mapping the kotoba host interfaces to the JS shims
cd web/p3-kotoba-guest
npm install cbor-x @bytecodealliance/preview2-shim
npx @bytecodealliance/jco transpile \
  ../../../../target/wasm32-wasip2/release/kotoba_guest.wasm -o out --name kguest \
  --map 'kotoba:kais/kqe=../hosts/kqe.js' \
  --map 'kotoba:kais/kse=../hosts/kse.js' \
  --map 'kotoba:kais/auth=../hosts/auth.js'

# 4) run the guest; verify it executed + wrote into KotobaNode
node run.mjs
```

Verified output:

```
real kotoba-guest run() → {"status":"ok","quads_asserted":1,
  "agent_did":"did:web:etzhayyim.com:actor:tsumugi","topic_cid":"bafy-kse-kotobayorosocial"}
KotobaNode got quad via guest kqe.assert-quad → {... "a":"kotoba/task","v_edn":"superstep-args" ...}
P3 REAL-GUEST VERIFY: PASS ✅
```

## Remaining for full browser Pregel

- A JS BSP driver (multi-superstep loop) — the pure-Rust `WasmPregelRunner`
  contract, in JS: feed `run()`'s `output_cbor` back as the next `ctx_cbor` while
  `status == "continue"`, accumulating quads.
- Run it under a real browser (this harness is node; the engine + jco glue are
  identical) and wire `kse`/`auth` to OPFS + the member identity rather than stubs.
- CBOR `object-cbor` decode: this shim treats the payload as text; full fidelity
  uses the CBOR QuadObject codec.

Build artifacts (`out/`, `pkg/`, `node_modules/`) are gitignored.
