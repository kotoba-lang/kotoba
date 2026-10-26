// Dependency-free smoke test for src/kami-engine-host.js's `kami:engine/*`
// port: a real native-WebAssembly round trip through
// examples/kami-engine-host/isekai-network-01-netsurvivors.wasm — the exact
// same compiled fixture kami-script-runtime-rs/tests/fixtures/ ships and
// kami-script-runtime-rs/tests/survivors.rs's `survivors_core_loop_evolves`
// drives via wasmtime. Same scenario, same assertions, run instead through
// Node's native `WebAssembly` (the same V8 a Chromium browser uses) with no
// wasmtime/cargo/JVM involved — the parity proof for retiring that Rust
// crate's runtime role. Run: `node test/verify-kami-engine-host.mjs`
//
// NOT ported: kami-script-runtime-rs/tests/survivors.rs's second test
// (`weapon_culls_a_synthetic_scene`) shells out to a live `kotoba-lang/
// engine` checkout to compile a scene at test time — no such checkout is
// available in this repo's test environment, so that specific compile-time
// scenario isn't re-verified here (the scene/weapon host-import bindings it
// exercises are still covered by this file's own use of the same
// `kami:engine/scene@1.0.0` imports against the real isekai-network fixture).
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createKamiEngineHost, orderedTickExports } from '../src/kami-engine-host.js';

const here = path.dirname(fileURLToPath(import.meta.url));

let failed = false;
function check(cond, message) {
  if (!cond) {
    failed = true;
    console.error(`FAIL: ${message}`);
  } else {
    console.log(`OK: ${message}`);
  }
}

const wasmBytes = await readFile(
  path.join(here, '..', 'examples', 'kami-engine-host', 'isekai-network-01-netsurvivors.wasm')
);

const host = createKamiEngineHost(7n);
const memoryBox = {};
const importObject = host.imports(memoryBox);

const { instance } = await WebAssembly.instantiate(wasmBytes, importObject);
memoryBox.memory = instance.exports.memory;
host.attach(instance, wasmBytes);

const systems = orderedTickExports(wasmBytes);
check(
  systems.length > 0,
  `orderedTickExports found at least one -tick export (got ${JSON.stringify(systems)})`
);

// orderedTickExports's `(if (< len 8) [] ...)` guard against a byte buffer
// too short to contain a valid wasm header/section -- never hit by the real
// fixture above. Lock in the fail-safe-empty behavior for truncated input.
check(
  orderedTickExports(new Uint8Array(0)).length === 0,
  'orderedTickExports on an empty buffer returns [] rather than throwing'
);
check(
  orderedTickExports(new Uint8Array(4)).length === 0,
  'orderedTickExports on a 4-byte buffer (below the len<8 guard) returns []'
);

host.callInit();

for (let i = 0; i < 300; i++) {
  host.tick(16);
}

check(host.taggedCount('shiro-pico') === 1, `exactly one duo (got ${host.taggedCount('shiro-pico')})`);
check(host.taggedCount('ghost') > 0, `wave spawning produced ghosts (got ${host.taggedCount('ghost')})`);
check(host.taggedCount('ghost') < 120, `alive count stays under max-alive (got ${host.taggedCount('ghost')})`);

// At least one ghost must have moved off its spawn point by now (the
// regression kami-script-runtime-rs's README documents: before
// kotoba-lang/engine#2, ghosts spawned via an inline negative f32 literal
// never moved at all).
const moved = host
  .debugDump()
  .filter((e) => e.tag === 'ghost')
  .some((e) => e.pos[0] !== 0 || e.pos[1] !== 0);
check(moved, 'at least one ghost should have moved from (0,0)');

console.log(
  `entities=${host.entityCount()} shiro-pico=${host.taggedCount('shiro-pico')} ghost=${host.taggedCount('ghost')} beat-spark=${host.taggedCount('beat-spark')}`
);

if (failed) process.exit(1);
console.log('OK: kami-engine-host.js round-trips isekai-network\'s real compiled game logic through native WebAssembly, matching kami-script-runtime-rs (Rust/wasmtime)');
