# kotoba-lang/wasm-webcomponent

Kototama's **browser host** — a small, dependency-free library for hosting a
`kotoba wasm emit` binary as a browser WebComponent, running it via the
browser's own native `WebAssembly` engine. Already-AOT-compiled machine code,
no interpreter, no JVM, no `com.dylibso.chicory`, no wasmtime.

The product is [`kototama`](https://github.com/kotoba-lang/kototama) (言霊).
This library stays extracted so any repo can adopt the same pattern instead
of depending on kototama core (ADR-2607061630 / ADR-2608139980).
kototama's own `web/` imports from here rather than duplicating the code.

Guest binaries are produced by [`amu`](https://github.com/kotoba-lang/amu)
(編む), not by this host.

## Shared client runtime candidate

`src/kotoba-client-runtime.js` is the canonical browser implementation of
`kotoba.app.client-runtime.v1`. It has no imports or build step. It validates
bounded endpoints, obtains fresh trusted consent, and verifies pinned artifact
bytes and signed descriptors. See [the integration contract](docs/client-runtime.md),
[browser evidence](docs/evidence/client-runtime-browser-20261023.json) and
[source recovery provenance](docs/client-runtime-recovery.md). Browser fixture
qualification does not qualify a product, deployment or Amu compiler build.

## CDCI status

The former GitHub Actions workflow used Node 22, npm and NBB/KBB-based
harnesses. It has been retired under the Amu selfhost / Kotoba-only CDCI
direction. No replacement success status or native qualification is claimed.
Existing host fixtures and the verification commands described below remain
porting inventory; their historical results do not qualify native CDCI.
The replacement controller and gates must run through canonical Kotoba and
Amu selfhost, with loaderless native artifacts and recorded provenance.

## Usage

Zero-import module:

```js
import { KotobaWasmElement } from './src/kotoba-wasm-element.js';
KotobaWasmElement.define('my-wasm-run');
```

```html
<my-wasm-run src="./my-module.wasm"></my-wasm-run>
<script type="module" src="./register-my-wasm-run.js"></script>
```

Module with host imports (e.g. `kgraph.js`'s `kgraph-*` ABI port):

```js
import { KotobaWasmElement } from './src/kotoba-wasm-element.js';
import { kgraphHostImports } from './src/kgraph.js';

KotobaWasmElement.define('my-kgraph-demo', {
  createImports(memoryBox) {
    const store = [];
    return { kotoba: kgraphHostImports(store, memoryBox) };
  },
  render(pre, { result, memoryBox }) {
    pre.textContent = `result: ${result}`;
  },
});
```

See `src/kotoba-wasm-element.js`'s header comment for the full `define()`
option surface (`exportName`, `createImports`, `render`).

Module using a runtime `(has-capability? :some/cap)` check (`has_capability`,
a single import distinct from `kgraph-*`'s effectful host calls):

```js
import { KotobaWasmElement } from './src/kotoba-wasm-element.js';
import { hasCapabilityHostImport } from './src/has-capability.js';

KotobaWasmElement.define('my-cap-demo', {
  createImports() {
    return { kotoba: hasCapabilityHostImport(['notify/show']) };
  },
});
```

Module using the `actor:host` ABI (`src/actor-host.js`'s peer,
browser/Node-native implementation of `kototama.contract`'s HostCaps/
RuntimeLimits — `tender` is a host-language-independent role, not a JVM
concept; this is an independent, non-JVM implementation of that role
alongside `kotoba-lang/kototama`'s JVM/Chicory `kototama.tender`, not a
port derived from it. Its authority table and host functions cover all
14 contract imports; network imports require an inject or SAB bridge —
see "Scope" below):

```js
import { KotobaWasmElement } from './src/kotoba-wasm-element.js';
import { actorHostImports, hostCaps, inMemoryStore } from './src/actor-host.js';

KotobaWasmElement.define('my-actor-host-demo', {
  createImports(memoryBox) {
    const store = inMemoryStore();
    const caps = hostCaps({ grants: ['clock-monotonic', 'sha256-hex'] });
    return { kotoba: actorHostImports(['clock-monotonic', 'sha256-hex'], caps, memoryBox, { store }) };
  },
});
```

Amu `compile --target wasm` guests import `kotoba:cap`/`call`, not
`actor:host`. That host is ClojureScript (`src-cljs/kotoba/kotoba_cap.cljk`
→ `src/kotoba-cap.js`), not more hand-written JS. Always link that module
(JVM tender does the same):

```js
import { KotobaWasmElement } from './src/kotoba-wasm-element.js';
import { actorHostImports, hostCaps } from './src/actor-host.js';
import { kotobaCapImports } from './src/kotoba-cap.js';

KotobaWasmElement.define('my-amu-clock', {
  createImports(memoryBox) {
    const caps = hostCaps({ grants: ['clock-monotonic'] });
    return {
      kotoba: actorHostImports(['clock-monotonic'], caps, memoryBox),
      'kotoba:cap': kotobaCapImports(caps),
    };
  },
});
```

## Files

- `src/kotoba-wasm-element.js` — `KotobaWasmElement`, the reusable custom
  element base / factory. Fetches `src`, runs
  `WebAssembly.instantiateStreaming`, calls the named export (default
  `main`), renders the result into shadow DOM, and dispatches
  `kotoba-wasm:done`/`kotoba-wasm:error` events.
- `src/kgraph.js` — optional: a browser-side port of `kotoba-lang/kotoba`'s
  `src/kotoba/kgraph.clj` (pure in-memory EAVT datom store) plus a minimal
  EDN reader/writer for the `kgraph-*` host-import wire ABI's two shapes.
  Only pull this in if your module actually calls `kgraph-assert!`/
  `kgraph-query`/etc.
- `examples/hello/` — zero-import module (`kotoba wasm emit src/demo.kotoba`,
  102 bytes, `main()` returns 42).
- `examples/kgraph/` — a module using the `kgraph-*` host imports
  (`kotoba wasm emit src/demo_kgraph.kotoba --policy src/demo_kgraph_policy.edn`,
  248 bytes).
- `examples/gcd/` — a brand-new `.kotoba` program (`gcd.kotoba`, included)
  demonstrating real runtime recursion (the Euclidean algorithm), not a
  hardcoded constant or a compile-time-folded computation. Compiled with
  `kotoba wasm emit gcd.kotoba --package-lock <empty-deps-lock>` (145 bytes;
  see kotoba-lang/kotoba#284 for why an empty-deps lock is needed for a
  zero-dependency build). Byte counts above (and every other example's,
  as of kotoba-lang/kotoba's embedded-fuel change) include the
  module-private fuel global + per-function charge prologue every
  `kotoba wasm emit` output now carries — see `wasm-binary`'s doc comment
  in that repo's `runtime.clj` for why.
- `src/has-capability.js` — optional: a browser-side port of
  `kotoba-lang/kotoba`'s `has_capability` host import
  (`kotoba.wasm-exec/has-capability-fn`), for modules with a runtime
  `(has-capability? :some/cap)` check (as opposed to the static
  compile-time gate `kotoba wasm emit --policy` already applies). The
  id-to-capability-name table is copied from the canonical
  `kotoba-lang/kotoba-core-contracts` `capability_contract.edn` (this
  library has no Clojure runtime to read that EDN file from directly).
- `examples/cap/` — `demo_cap.kotoba` (a runtime `has-capability?` check)
  instantiated twice with the same bytes: once granting `notify/show`
  (`main()` → 7) and once denying everything (`main()` → 0) — proves the
  check is real per-instantiation policy, not a stub that always answers
  one way.
- `src-cljs/kotoba/kami_ecs.cljk` / `src/kami-ecs.js` — the browser/Node
  host for `kotoba-lang/kotoba`'s `kotoba.kami-host` (the deterministic
  game-engine ECS behind the `kami-*` host imports, kotoba-core-contracts
  `"kami/engine"` id 233, single `(module "kotoba")` ABI — NOT
  `kami-engine-host.js`'s 4-namespace `kami:engine/*` shape). **Authored
  in ClojureScript** (like `kami-engine-host.js`, unlike this repo's
  hand-JS modules — it replaced an earlier hand-JS port): the portable
  `.cljc` ECS itself is `src-cljs/vendor/kotoba/kami_host.cljk`, VENDORED
  file-for-file from `kotoba-lang/kotoba` (the `src/vendor` ed25519
  convention; provenance sha in its header) so ONE source serves kotoba's
  JVM compat suite, its nbb parity script, and this ESM — no drift.
  Host-owned entity table, fixed-step Euler integration (1/60s), tick
  counter, input axes, and a seeded 32-bit-pair xorshift64, bit-identical
  on every runtime — the same compiled game plays the same run here that
  kotoba's `kami_game_test.clj` pins on Chicory. Exports
  `createKamiEcs(seed)` and `kamiHostImports(ecs, memoryBox)`; regenerate
  with `npm run release:kami-ecs` (the compiled output is checked in).
- `examples/kami-survivors/` — `kami-survivors.wasm` (compiled by the real
  `kotoba wasm emit` from `kotoba-lang/kotoba`'s
  `src/kami_survivors.kotoba` — **the first game authored directly in a
  `.kotoba` file**) driven at a fixed step per `requestAnimationFrame`
  frame, rendered on a canvas, with arrow keys/WASD wired to the
  host-owned `MoveX`/`MoveY` axes. `test/verify-kami-survivors.mjs` is the
  parity proof: the same 300-tick run asserts the exact entity counts
  (`12` at tick 240, `8` after the tick-270 nova burst, `10` at 300,
  seed 7) kotoba's own JVM/Chicory test pins.
- `src-cljs/kotoba/kotoba_cap.cljk` / `src/kotoba-cap.js` — the browser/Node
  host for amu wasm32-kotoba-v1 `kotoba:cap`/`call` (typed-cap-call i64).
  **Authored in ClojureScript** and compiled once via `shadow-cljs.edn`'s
  `:kotoba-cap` build (`:target :esm`) to `src/kotoba-cap.js` — same
  pattern as `kami-engine-host` / `gpu-clear-host`. This is the host, not
  a `.kotoba` guest; new Node proof is nbb (`npm run test:kotoba-cap`),
  not `.mjs`. Capability 7 is clock/now under the `:clock-monotonic`
  grant; any other id fail-closes with the same
  `kototama.tender: host import denied` message as the JVM tender.
  `actor-host.js` does not re-export this module, so the cljs runtime is
  not on the actor:host path. Regenerate with `npm run release:kotoba-cap`
  (the compiled output is checked in). Proof against **amu-woven** bytes
  (not only hand-written WAT) is `examples/kotoba-cap/amu-compiled-clock-now.wasm`
  + `npm run test:kotoba-cap`.
- `examples/kotoba-cap/` — amu `compile-source :wasm32-kotoba-v1` guest
  (`clock/now` → `kotoba:cap`/`call` id 7) hosted by `kotoba-cap.js`.
  Same fixture kototama binds on the JVM (`amu-compiled-clock-now.wasm`).
- `src/actor-host.js` — a peer, browser/Node-native implementation of the
  `tender` role `kototama.contract` defines (the same role
  `kotoba-lang/kototama`'s JVM/Chicory `kototama.tender` implements —
  `tender` names a host-language-independent role, not a JVM-specific
  concept; see ADR-2607183010). Unconditionally sync: clock / sha256 /
  gen-keypair / sign / verify / log-* / codecs. Conditional:
  **`llm-infer`**, **`http-fetch`**, **`http-post-headers`**, and
  **`http-post`** (inject, or the shared `opts.httpPostBridge` SAB+COOP
  transport from `http-post-bridge.js`). JSPI is
  detected (`httpPostCapabilities`) but not the default wire. All 14 JVM
  contract imports now share the same browser session authority,
  one-shot/revoke/drop lifecycle, memory gate and quotas. Network effects
  deliberately have no ambient synchronous default — see "Scope" below.
  See `test/verify-http-post.mjs`
  + `examples/http-post-echo.wasm`.

- `src/component-linker.js` / `src/http-sab-bridge.js` / `src/node-*-provider.js` — the bounded component provider runtime: `createComponentLinks` binds kotoba components to exact-endpoint providers; the SAB HTTP bridge (`attachSabHttpGetBridge`/`attachSabHttpPostBridge`) gives browser components synchronous fetch over SharedArrayBuffer (COOP/COEP required, default-denied, request-count bounded, manual redirects, HTTPS host/port/path allowlist); the Node providers (`createNodeCredentialProvider`, `createNodePostgresqlPoolProvider`, `createNodeTransportBroker`) are fail-closed by default with lease-based connection handles and explicit per-method overrides. Proof: `test/verify-node-*.mjs`, `test/verify-actor-host.mjs`, `test/browser/verify-http-get-sab.mjs`.
- `src/vendor/` — the actual, unmodified `@noble/curves`/`@noble/hashes`
  source files `actor-host.js`'s ed25519 imports need, copied file-for-file
  (not hand-transcribed) with only bare-specifier import paths patched to
  relative — see `src/vendor/README.md` for the exact file list, versions,
  and why vendored rather than CDN-imported (Node's default ESM loader
  refuses `https:` specifiers, which would break `node test/verify-*.mjs`).
- `examples/actor-host/` — hand-assembled (`wasm-tools`) modules wired to
  `actor-host.js`: `actor-host-demo.wasm` (`clock_monotonic`/`log_write`/`sha256_hex`)
  and `crypto-demo.wasm` (`gen_keypair`/`sign`/`verify` — same fixture
  shape `kototama.tender`'s (JVM) `tender_test.clj` compiles via
  `wasm-tools`).
- `src-cljs/kotoba/kami_engine_host.cljk` / `src/kami-engine-host.js` — a
  port of `kotoba-lang/kami-script-runtime-rs` (the Rust/wasmtime WASM host
  for `kotoba-lang/engine`-compiled `.clj` game scripts), **authored in
  ClojureScript and compiled once via `shadow-cljs.edn`'s `:kami-engine-host`
  build (`:target :esm`) to `src/kami-engine-host.js`** — see
  ADR-2607078000 for why this module (unlike this repo's other, hand-JS
  modules below) takes a build step: one compiled ES module runs
  identically in a browser `<script type="module">` and in Node, instead
  of separate per-platform hand-ports. Run `npm install && npm run
  compile:kami-engine-host` to regenerate `src/kami-engine-host.js` from
  the `.cljs` source (the compiled output is checked in, so consumers don't
  need shadow-cljs unless they're changing the source). Wires all 14
  `kami:engine/*` host-imports (`bind_scene`/`bind_input`/`bind_random`/
  `bind_time`, across 4 WASM import modules: `kami:engine/scene@1.0.0`,
  `/input`, `/random`, `/time`) and drives the guest's `init`/`<name>-tick`
  lifecycle against a minimal in-memory ECS store — same semantics as the
  Rust `KamiHost`, ported 1:1 (entity spawn/despawn/position/velocity, tag
  queries, nearest/move-toward, xorshift64 random, fixed-step Euler
  integration, export-section `-tick`-suffix ordering). Exports
  `createKamiEngineHost(seed)` (a factory returning a plain JS object with
  `imports`/`setAxis`/`attach`/`callInit`/`tick`/`entityCount`/
  `taggedCount`/`debugDump` methods — not a JS `class`) and
  `orderedTickExports(wasmBytes)`. Unlike this library's other modules
  (single `(module "kotoba")` ABI), this one targets `kami-script-runtime-
  rs`'s existing 4-namespace import shape directly, since the goal is
  running the exact same compiled `game.wasm` a Rust host runs, not a new
  ABI.
- `examples/kami-engine-host/` — `isekai-network-01-netsurvivors.wasm`
  (the same fixture `kami-script-runtime-rs/tests/fixtures/` ships) driven
  for 300 ticks via `requestAnimationFrame` (real-browser confirmation
  outstanding — see ADR-2607078000's Consequences).
- `src-cljs/kotoba/gpu_clear_host.cljk` / `src/gpu-clear-host.js` — ADR-
  2607078000 Track B **Phase 0**: the browser host for the `gpu-clear`
  capability, the first proof that a compiled `.kotoba` guest can drive a
  real WebGPU canvas clear through a genuinely synchronous Wasm
  host-import (no JSPI / `Atomics.wait` bridge needed — `requestAdapter`/
  `requestDevice` are the only async WebGPU calls, and they run once,
  host-side, before the guest ever executes). Wire format:
  `gpu_clear(rgba8: i32) -> i32`, a packed `0xRRGGBBAA` color. Exports
  `setupGpuClearHost(canvas)` (async, one-time device/context setup) and
  `unpackRgba8` (the pure signed-i32→`[r,g,b,a]` bit-unpacking logic,
  public specifically so it's unit-testable without a GPU — see
  `test/verify-gpu-clear-host.mjs`). Regenerate via `npm run
  compile:gpu-clear-host` / `release:gpu-clear-host`.
- `examples/gpu-clear/` — `demo_gpu_clear.kotoba`/`.wasm` (a `.kotoba`
  guest that calls `gpu_clear` with a packed color) + `index.html`,
  browser-verified against `setupGpuClearHost` end to end.
- `src-cljs/kotoba/solar_render_host.cljk` / `src/solar-render-host.js` —
  ADR-2607078000 Track B **Phase 1**: the browser host for
  `gpu-set-position`/`gpu-draw-frame`, rendering `kami-solar-helix-scene`'s
  9 bodies (Sun + 8 planets) as spheres. The guest (compiled from
  `demo_solar_helix.kotoba`) computes each body's position every frame via
  real `cos`/`sin` host-imports and calls `gpu-set-position(body-id, x, y,
  z)` once per body, then `gpu-draw-frame()` once — all matrix/camera/
  pipeline/mesh mechanics stay host-side, since `.kotoba` has no vector/
  matrix type. One dedicated uniform buffer + bind group per body (9
  total, not one shared buffer) — `queue.writeBuffer` runs immediately but
  `pass.drawIndexed` only records until `queue.submit()`, so a single
  shared buffer written 9× before any draw executes would leave every draw
  referencing only the last write. Exports `setupSolarRenderHost(canvas)`
  plus its pure mat4/vec3/mesh helpers (`mat4Multiply`/`mat4Perspective`/
  `mat4LookAt`/`mat4TranslationScale`/`vec3Normalize`/`vec3Sub`/
  `vec3Cross`/`vec3Dot`/`buildSphereMesh`), public specifically so they're
  unit-testable without a GPU — see `test/verify-solar-render-host.mjs`.
  Regenerate via `npm run compile:solar-render-host` /
  `release:solar-render-host`.
- `examples/solar-helix/` — `demo_solar_helix.kotoba`/`.wasm` (the 9-body
  orbital-math guest, using `.kotoba`'s real `f32` support — `kotoba-lang/
  kotoba`'s compiler gained native f32 params/locals/results/comparisons
  for this) + `index.html`. `main` is called again every
  `requestAnimationFrame` tick (real animation, not a single static
  frame); each call reads a host-owned, wrapped simulated day count
  (`now-days`) and a host-owned heliocentric/galactic view toggle
  (`galactic-frame?`, wired to a page checkbox) instead of a fixed t.
  Galactic view ports `kami-solar-helix-scene`'s
  `galactic-frame-position-au` 1:1 (orbital-plane tilt + the Sun's own
  forward drift). Verified rendering correctly in both view modes three
  independent ways: interactive real-browser screenshots (page load and
  immediately after toggling), a headless real-GPU CI check
  (`test/render/verify-render-solar-helix.mjs`, exact landmark positions
  and colors for both a heliocentric and a galactic-frame frame), and a
  GPU-free numerical sweep of the guest's own math across the entire
  `now-days` range (`test/verify-solar-helix-guest.mjs`). Sustained
  multi-second *live* animation showed intermittent blank-canvas behavior
  in one sandboxed browser-automation session that root-caused to that
  session's own repeated WebGPU device/canvas creation, not the guest or
  host code — see the "Run an example" section below for the full
  account of that investigation.
- `test/verify-*.mjs` — dependency-free Node smoke tests (same
  `WebAssembly` engine — V8 — a Chromium browser uses) for each example.
  They check the AOT-execution / host-import claims only; they do not
  exercise `KotobaWasmElement`'s DOM/customElements path (no DOM in plain
  Node) — that needs a real browser, see `examples/*/index.html`.

  `verify-kami-engine-host.mjs` specifically is the parity proof for
  retiring `kami-script-runtime-rs`'s Rust runtime role: it drives the same
  fixture for the same 300 ticks and asserts the exact same entity counts
  (`entities=16 shiro-pico=1 ghost=14 beat-spark=1`) that crate's own README
  documents from a real `cargo run`/wasmtime execution.
  `verify-gpu-clear-host.mjs`/`verify-solar-render-host.mjs` exercise the
  pure, GPU-free logic behind Phase 0/Phase 1 (bit-unpacking, mat4/vec3
  math, sphere-mesh generation) directly. The actual WebGPU draw path (pipeline
  creation, bind groups, `queue.submit` timing, the real rendered pixels) is
  no longer a human-only check — see `test/render/` and "Automated render
  verification" below.
  `verify-solar-helix-guest.mjs` separately sweeps `demo_solar_helix.wasm`'s
  own computed positions (no GPU, no browser) across the full `now-days`
  wrap range in both view modes (finite, bounded, correctly-signed) — the
  guest-math half of the animation-toggle investigation in "Run an
  example" below, made a permanent regression check.
- `test/render/verify-render-gpu-clear.mjs` / `test/render/verify-render-solar-helix.mjs`
  — real-pixel CI verification of `examples/gpu-clear`/`examples/solar-helix`'s
  actual WebGPU draw path via a real headless browser (not a human with
  claude-in-chrome). See "Automated render verification" below for what was
  investigated, what these assert, and what's still out of scope.
- `test/render/lib/webgpu-harness.mjs` / `test/render/lib/png-decode.mjs` —
  shared, dependency-free (beyond the `playwright` devDependency itself)
  helpers the two tests above use: a plain-Node static file server, a
  Playwright launch helper that resolves the full (non-headless-shell)
  Chromium binary, and a from-scratch PNG decoder (Node's built-in `zlib`
  only) to read back actual pixel bytes from a canvas screenshot.

Node hosts may opt into the bounded raw transport ABI through
`createNodeTransportBroker` in `src/node-transport-broker.js` and inject it as
`actorHostImports(..., {transport: broker})`. The broker owns sockets and
affine handles in a worker, bridges synchronous Wasm imports with
SharedArrayBuffer/Atomics, requires exact endpoint and resolved-address
allowlists, enforces finite connection/read/write/time quotas, and always
verifies TLS certificates and the exact SNI name. Its default policy permits
zero connections; browser hosts do not expose raw transport.

`instantiateKotobaComponent` compiles/instantiates a low-level provider, while
`instantiateLinkedKotobaComponent` links a consumer to that provider across
independent linear memories. The linker copies only manifest-declared buffers
through a 64 KiB scratch page, rejects overflow/reentrancy/missing exports, and
meters `http-get` attempts. `test/verify-node-http-component.mjs` compiles the
repository's real `providers/http_transport.kotoba` and
`providers/http_consumer.kotoba`, then verifies the complete consumer →
provider → worker/SAB → TLS server path.

The same linker exposes the five bounded generic DB bindings from
`DB_LINKS`. `test/verify-node-db-component.mjs` compiles the real framed DB
provider and consumer and exchanges a length-prefixed frame over verified TLS.
PostgreSQL protocol, SCRAM credential custody, pooling, and cancellation remain
separate opt-in layers; generic DB linkage does not imply those authorities.

Node also provides the purpose-bound native TCB extensions required by
`pg_scram.kotoba`: `createNodeCredentialProvider` resolves only allowlisted
credential references and returns SCRAM client-proof plus server-signature,
never the password; the transport broker turns BackendKeyData into a bounded
one-shot cancellation handle that can send only PostgreSQL's fixed 16-byte
CancelRequest to the TLS session's pinned peer. Tests execute the RFC vector
through the compiled `.kotoba` provider and verify cancel wire bytes and
double-use denial.

The first PostgreSQL session bindings are also live on Node. `PG_SESSION_LINKS`
bridges `pg-open`, `pg-query`, and `db-close`; its E2E test compiles the real
provider and consumer, validates the plaintext PostgreSQL SSLRequest, upgrades
the same affine connection to verified TLS, validates StartupMessage framing,
and performs a SimpleQuery through ReadyForQuery.

Multi-provider consumers are supported by `instantiateLinkedKotobaComponents`.
The transaction E2E links `db_transport.kotoba` and `pg_scram.kotoba` into the
separate `pg_transaction_consumer.kotoba`, completes SCRAM-SHA-256 without
exporting its password, and verifies PostgreSQL transaction metadata across
`BEGIN` (`T`) → division error (`E`, SQLSTATE `22012`) → `ROLLBACK` (`I`).

Named prepared statements are linked through `PG_PREPARED_LINKS`. The compiled
prepared consumer is checked at the wire boundary: Parse contains the fixed
`$1/$2` query, potentially hostile text remains only in Bind parameter bytes,
an expected `22P02` does not poison the session, a later execution succeeds,
and CloseStatement receives CloseComplete.

Typed prepared statements use `PG_TYPED_PREPARED_LINKS`. Their compiled
consumer proves that Parse carries exactly three `int4` OIDs, Bind preserves
text/text/binary format codes, SQL NULL stays the `-1` length sentinel, binary
`int4` 22 remains four big-endian bytes, and hostile text remains a parameter.

Named cursors use `PG_PORTAL_LINKS` inside an explicit transaction. The
compiled portal consumer proves Parse/Bind name separation, Execute row bounds,
`PortalSuspended` followed by a resumed Execute and `CommandComplete`, and
independent ClosePortal/CloseStatement completion over verified TLS + SCRAM.

`PG_BATCH_LINKS` keeps each prepared statement name and parameter block in
separate bounded buffers while emitting multiple Bind/Execute pairs under one
Sync. The compiled batch consumer verifies two successful items, a middle
`22012` error with ReadyForQuery recovery, a later successful reuse, and close.

`PG_SESSION_RESET_LINKS` performs `ROLLBACK` followed by `DISCARD ALL`. Its
compiled consumer verifies transaction cleanup, application-name reset,
temporary-table removal, prepared-statement deallocation (`26000`), and reuse
of the same verified TLS + SCRAM connection.

`PG_COPY_LINKS` supports COPY IN and COPY OUT without exposing the socket. The
compiled consumer proves CopyInResponse → bounded CopyData → CopyDone and a
three-row CopyOutResponse/Data/Done stream, then validates the resulting table
through the same verified TLS + SCRAM session.

`createNodePostgresqlPoolProvider` is the bounded native runtime boundary for
opaque pool membership and affine lease tokens; PostgreSQL protocol, session
reset, TLS and credentials remain in the compiled Kotoba providers below it.
The compiled multi-pool consumer verifies two real TLS/SCRAM connections,
saturation, monotonic non-revivable leases, release-time reset, fixed stats,
idle-only health probes, busy close, forced drain accounting, and final close.

The remaining PostgreSQL compatibility imports are also explicit component
links: the legacy one-shot query performs SSLRequest before verified TLS and
exact-reads AuthOK/Ready; caller-nonce SCRAM retains host-custodied credentials;
and cancellable SCRAM copies out only an opaque one-shot authority whose
compiled consumer emits the fixed pinned-peer CancelRequest.

Node `kagi-sign` is available only through a decision-aware trusted adapter.
The generic host never accepts raw key bytes or a bare signing callback; it
threads the exact decision set and opaque key reference into `authorizedSign`,
returns only bounded signature bytes, defaults to zero calls, and enforces a
finite per-session quota.

## Run an example

```bash
cd examples/hello && python3 -m http.server 8123
# open http://localhost:8123/ in a browser
```

Every `test/verify-*.mjs` in this repo confirms the underlying `WebAssembly`
execution and host-import logic against Node's own engine (the same V8 a
Chromium browser uses) — but none of them drive an actual DOM/
`customElements` render in a real browser tab. That gap is a real,
outstanding limitation of this test suite, not just an unverified claim:
an agent working in a sandboxed automation environment tried to close it
and hit tooling dead ends worth recording so the next attempt doesn't
repeat them:
- A local `python3 -m http.server` in a sandboxed shell was unreachable
  from the browser-automation tool's actual Chrome process (separate
  network namespaces) — `file://` and `data:` URLs were also blocked
  outright by that tool.
- jsdelivr's GitHub proxy (`cdn.jsdelivr.net/gh/...`) serves `.js` files
  with the correct `application/javascript` type (fine for `import()`),
  but serves `.html` as `text/plain; charset=utf-8` with `nosniff` — a
  browser will not render it, only display it as text.
- `htmlpreview.github.io` does serve proxied GitHub HTML as real
  `text/html` and a page's own `<title>`/DOM genuinely renders through
  it — but its own `htmlpreview.js` reinjects `<script>` tags in a way
  that drops `type="module"`, so a page using `<script type="module">`
  (this library's own convention) fails there with `Cannot use import
  statement outside a module`. A page using dynamic `import()` from a
  classic `<script>` avoids that specific error, but produced an
  unexplained rendering artifact worth a fresh investigation rather than
  more workarounds layered on unrelated third-party proxies.
- None of the above says anything about a real, un-sandboxed browser
  (a developer's own Chrome hitting a real `python3 -m http.server`)  —
  only that this particular sandboxed session's tooling chain couldn't
  reach one. Do this from an environment where the browser and the
  static server actually share a network first.

### `examples/solar-helix/`'s sustained-animation verification gap

Same spirit as the gap above, recorded for the same reason (so the next
attempt doesn't repeat the investigation from scratch): a real-browser
GitHub Pages check confirmed `examples/solar-helix/` renders correctly —
9/9 bodies, correct colors/positions — both at page load (heliocentric)
and immediately after toggling the galactic-frame checkbox. But letting
the page's own `requestAnimationFrame` loop run for several sustained
seconds sometimes produced a solid-black canvas afterward, in both view
modes, with `main()` still returning `0` (success) and the frame counter
still advancing — i.e. the guest was still running successfully, but
nothing visible was being drawn.

Investigation before concluding this isn't a code defect:
- `test/verify-solar-helix-guest.mjs` sweeps the guest's own computed
  positions across the *entire* `now-days` wrap range in both view
  modes via Node's native `WebAssembly` (no GPU) — every value is
  finite, bounded, and correctly signed. The same sweep was independently
  re-run through `com.dylibso.chicory` (a real, different WASM engine)
  from `kotoba-lang/kotoba`'s own JVM test tooling with identical results.
  The guest math is not the problem.
- A dynamically created, DOM-attached `<canvas>` — set up and driven
  through the exact same `solar_render_host.cljs`-compiled host, in the
  same browser tab, after the page's own canvas had already gone
  black — rendered all 9 bodies correctly for hundreds of animated
  frames. The host/pipeline code is not the problem either, at least not
  in isolation.
- The failure was reproducible from a clean single-tab session with
  *no* other WebGPU activity beforehand, so it isn't purely an artifact
  of this investigation's own repeated `requestAdapter`/`requestDevice`
  calls in prior tabs (which was the first suspect, and did explain some
  — but not all — of the earlier flakiness observed while debugging).

Working conclusion, since strengthened to high confidence by the
automated-render-verification work below: this was browser/GPU-process-
level flakiness specific to the sandboxed browser-automation *tool* this
investigation used (repeated tab creation/navigation and manual
`requestAdapter`/`requestDevice` probing in the same Chrome instance),
not a bug in `demo_solar_helix.kotoba` or `solar_render_host.cljs`.
`test/render/verify-render-solar-helix.mjs` (see "Automated render
verification" below) drives the exact same compiled host/guest through a
freshly launched, real-GPU headless Chromium — no manual tab juggling,
no accumulated device churn — and passes cleanly for a full rendered
frame in *both* view modes, landmark-for-landmark, color-for-color. That
test is necessarily a single still frame per run (CI has no "watch it
animate for 30 seconds" primitive), so it doesn't directly re-run the
exact sustained-animation scenario above, but combined with the guest-math
sweep and the isolated-canvas recovery observed during the original
investigation, there are now three independent lines of evidence the
code itself is correct and zero evidence pointing at it specifically.
If a real, un-sandboxed browser left animating for an extended period
ever reproduces the blank-canvas symptom, the next place to look is
WebGPU device/resource lifecycle over a long `requestAnimationFrame` run
(e.g. whether `queue.submit`'s command buffers or bind groups need
explicit disposal this code doesn't do) — not the position math, which
is now regression-tested from two independent angles and ruled out.

## Run the tests

```bash
npm test   # runs every test/verify-*.mjs in sequence, stops on first failure

# or individually:
node test/verify-hello.mjs
node test/verify-kgraph.mjs
node test/verify-gcd.mjs
node test/verify-cap.mjs
node test/verify-actor-host.mjs
node test/verify-kami-engine-host.mjs
node test/verify-kami-survivors.mjs
node test/verify-gpu-clear-host.mjs
node test/verify-solar-render-host.mjs
```

Real-pixel WebGPU render verification is a separate command (needs the
`playwright` devDependency + a downloaded browser, and — see below — a real
GPU to be meaningful):

```bash
npm install
npx playwright install chromium
npm run test:render   # runs every test/render/verify-*.mjs
```

## Automated render verification (real pixels, CI)

A prior maturity pass (ADR-2607078000 Addendum 7) gave `gpu-clear-host.cljs`/
`solar-render-host.cljs`'s pure math/mesh helpers unit coverage but explicitly
left one gap open: the actual WebGPU draw path (pipeline creation, bind
groups, `queue.submit` timing, the real rendered pixels — where both real
bugs Addendum 6 documents were actually found) had zero CI-runnable coverage
and needed a human with claude-in-chrome to eyeball a GitHub Pages screenshot
each time. `test/render/` closes that gap with real, automated, pixel-level
assertions.

**What was investigated: does headless WebGPU actually work?** Yes, but only
under specific conditions this repo's harness (`test/render/lib/webgpu-harness.mjs`)
now encodes:
- Playwright's *default* headless Chromium resolution is not always
  WebGPU-capable — on at least one platform tested here, the default
  `chromium.launch({ headless: true })` resolves to the stripped-down
  "headless shell" binary Playwright ships alongside the full Chromium
  build, which has no `navigator.gpu` at all. The fix is `chromium.executablePath()`
  (a public, version-independent Playwright API) passed explicitly as
  `executablePath` — this reliably resolves to the *full* Chromium/"Chrome
  for Testing" binary, which does have WebGPU, regardless of `headless`.
- `navigator.gpu` is only populated on a real `http(s)` origin, not on a
  fresh `about:blank` page — the harness always navigates before checking.
- **macOS: works reliably, no special launch flags needed.** Verified
  directly: `examples/gpu-clear` renders a pixel-perfect solid opaque-red
  canvas, and `examples/solar-helix` renders all 9 bodies at their expected
  positions with their expected colors (to within ~1-9 out of 255 per
  channel — see `verify-render-solar-helix.mjs`'s header comment for why
  that's expected to be this tight), matching this repo's own prior
  claude-in-chrome/GitHub-Pages screenshots.
- **Linux + SwiftShader software rendering: tested and found unreliable —
  not wired into CI.** A Docker container matching the `mcr.microsoft.com/playwright`
  image family, with `xvfb-run` + `--enable-unsafe-webgpu --enable-features=Vulkan
  --use-angle=swiftshader --ignore-gpu-blocklist` (the flag set another repo
  in this ecosystem's own investigation, `gftdcojp/network-isekai`'s
  `scripts/isekai/capture.clj`, uses), got as far as `navigator.gpu.requestAdapter()`/
  `requestDevice()` succeeding, but actual render-pass submission failed with
  `Instance dropped in popErrorScope` and produced a blank canvas. This
  matches this ecosystem's own prior, independent finding
  (`gftdcojp/network-isekai`'s ADR-0025: "headless WebGPU itself remains
  unavailable in this sandbox"). Given that, `render-verify`'s CI job targets
  `runs-on: macos-latest` (real Apple Silicon hardware, a working Metal-backed
  GPU process) instead of forcing an unreliable Linux/SwiftShader path.

**What the two tests actually assert** (not just "did it throw"):
- `verify-render-gpu-clear.mjs` — screenshots the canvas after the guest's
  `(gpu-clear -16776961)` call, decodes the PNG (`test/render/lib/png-decode.mjs`,
  a from-scratch decoder using only Node's built-in `zlib` — no image-decoding
  npm dependency), and asserts every sampled interior pixel is opaque red
  (`rgb(255,0,0)`, ±4 tolerance) — a real per-pixel color check.
- `verify-render-solar-helix.mjs` — samples 9 hand-verified landmark screen
  positions (one per body) and checks each against that body's *exact*
  expected peak-lit color. Those expected colors aren't fuzzy estimates:
  `solar_render_host.cljs`'s WGSL shader computes `lit = color.rgb * (0.35 +
  0.65*ndotl)`, so at a sphere's most directly-lit point (`ndotl == 1`),
  `lit == color` exactly — the raw `body-palette` value this repo's own
  source already defines. A real regression (wrong color, a missing body,
  or the buffer-aliasing bug reproducing) moves a landmark's measured color
  far past this test's tolerance, not by a couple of units. Landmark
  positions were picked over blob/connected-component detection specifically
  because Venus visually overlaps the Sun's disk at this render's fixed
  camera/t=45-day orbital phase — a real ambiguity for blind blob-counting,
  not a bug, that per-landmark sampling sidesteps entirely.

**Proof these actually discriminate pass/fail** (not just theoretically):
both of Addendum 6's real historical bugs were deliberately reintroduced
against a local worktree, rebuilt via `amu compile --target wasm32-browser`, and confirmed to
fail the corresponding test before being reverted:
- Swapping the R/B channels in `gpu_clear_host.cljs`'s `clearValue` made
  `verify-render-gpu-clear.mjs` fail with every sampled pixel reading
  `rgb(0,0,255)` instead of `rgb(255,0,0)`.
- Reverting `solar_render_host.cljs`'s per-body uniform buffer/bind-group
  back to one shared buffer (the exact Addendum 6 bug) made
  `verify-render-solar-helix.mjs` fail on 8 of 9 bodies — only Neptune (drawn
  last) still rendered correctly, and the "distinct colors" check dropped
  from 9 to 2, exactly the failure signature Addendum 6 describes ("every
  draw referencing only the last write").

**What this still doesn't cover** (honest, not silently fixed): geometric/mesh
correctness beyond palette-color sampling (an entirely wrong mesh shape that
still happened to cover these same landmark pixels with the same color would
pass), camera-framing regressions too small to move a landmark color outside
its search window, and anything about `examples/kami-engine-host/`'s
`requestAnimationFrame`-driven tick loop (untouched by this pass — see its
own outstanding real-browser-confirmation gap above). `WEBGPU_RENDER_TEST_SKIP_IF_UNAVAILABLE=1`
lets these tests skip cleanly instead of failing red on a machine/CI runner
without a working WebGPU adapter (e.g. local Linux dev machines) — CI itself
does not set this, so a WebGPU regression on `macos-latest` fails loudly, not
silently.

## Scope (honest R2 advanced-partial)

- **`kgraph-*`, `has_capability`, and actor:host** (14/14 contract imports,
  with conditional network transports). `http-post`, `http-fetch`,
  `http-post-headers`, and `llm-infer` are available via inject or the
  shared SAB+COOP bridge. **`http-post`** is available via (1) `opts.httpPost` inject
  (Node/tests), (2) SAB+COOP bridge (`createSabHttpPostBridge`, needs
  `crossOriginIsolated`), (3) JSPI experimental detection only. Without a
  path, `http_post` is absent from the import object (clear link error).
  Wider `kse`/`auth`/`evm`/… surfaces are outside the `actor:host`
  contract and are not ported.
- **`has-capability.js` re-states a policy at load time, it doesn't
  re-derive one.** The granted-capabilities list you pass to
  `hasCapabilityHostImport` is trusted input from the page author, not
  cryptographically verified against anything — it's the browser-side
  equivalent of the JVM's `:kotoba.policy/capabilities` map, not a
  replacement for `kotoba wasm emit --policy`'s compile-time gate.
- **`kgraph.js`'s EDN reader/writer is intentionally minimal** — only the
  shapes the `kgraph-*` ABI carries (vectors, keyword-keyed maps, keywords,
  strings, integers, `?var` symbols), not general-purpose EDN.
- **`kgraph.js` has no capability/policy re-enforcement at load time**
  (`kotoba wasm emit --policy`/`--package-lock` gates are build-time
  checks only). `actor-host.js` is the exception: it DOES re-verify
  `HostCaps`/`RuntimeLimits` at load time (pre-flight, before
  `WebAssembly.instantiateStreaming` runs) and per host-function call —
  but only for the 4 imports it implements. Don't treat a page built on
  this library as a sandboxed multi-tenant host in general.
- **Resource limits (`maxMemoryPages`/`max-wall-ms`) are real but weaker
  than `kototama.tender`'s (JVM/Chicory) equivalents, structurally, not
  just by omission.** `kototama.contract`'s `default-runtime-limits`
  defines both `:max-memory-pages` (16 pages/1 MiB) and `:max-wall-ms`
  (5000 ms) as host-adapter-enforced limits; this repo now implements
  both, but:
  - `maxMemoryPages` (`actor-host.js`) is enforced REACTIVELY (checked on
    every gated host-import call, `-1` once over budget) and once
    PREVENTIVELY at instantiation time (`memoryWithinCap`, used by
    `kotoba-wasm-worker-host.js` before calling the guest's export) — not
    continuously during a call, unlike `tender.clj`'s `MemoryLimits`,
    which caps `memory.grow` itself at the Chicory engine level. A guest
    that grows past budget in one shot and never calls back into the host
    is not caught. This isn't an oversight: kotoba-wasm-emitted modules
    EXPORT their own memory rather than importing a host-provided one, and
    the standard `WebAssembly.instantiate` JS API gives no hook to cap an
    exported memory's growth from outside.
  - `max-wall-ms` (`kotoba-wasm-worker-element.js` only — `maxWallMs`
    attribute, default 5000) hard-`terminate()`s the guest's dedicated
    Worker past the deadline — a real, working defense, but wall-clock,
    not instruction-count, unlike `tender.clj`'s `fuel-listener`. There is
    no portable way to preempt a running, JIT-compiled WASM call from JS
    mid-instruction the way Chicory's per-instruction interpreter dispatch
    can. `KotobaWasmElement` (the non-Worker element) has NO such
    protection at all and structurally cannot: its guest runs
    synchronously on the main/DOM thread, where nothing (not even a
    `setTimeout`) can preempt it — use `KotobaWasmWorkerElement` for
    anything untrusted or capability-bearing.
  - A follow-up with true per-instruction fuel (mirroring `fuel-listener`
    exactly) would require the `kotoba-lang/amu` wasm backend to
    inject cooperative fuel-check instructions at loop back-edges/call
    sites — a compiler change, out of this repo's scope, tracked
    separately from this host-side interim fix.
- **Not every kotoba-lang repo has `.kotoba` source to point this at.**
  Most `kotoba-*`-named repos in the org (`lint-kotoba`, `kotoba-code`,
  `kotoba-procedure-clj`, ...) are regular `.cljc`/`.clj` Clojure libraries
  using language features (maps, `require`, third-party deps) well beyond
  `.kotoba`'s minimal subset (no maps, no interop, no third-party libs) —
  pointing this library at them requires rewriting their logic in that
  subset first, not just recompiling existing source. `examples/gcd/`
  demonstrates writing something new in the subset rather than pretending
  an existing repo "just becomes" a WASM WebComponent.

## License

MIT.
