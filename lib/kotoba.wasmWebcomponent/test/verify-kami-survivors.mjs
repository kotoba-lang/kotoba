// Dependency-free smoke test for src/kami-ecs.js's kami-* host-import ABI
// port: instantiate examples/kami-survivors/kami-survivors.wasm (the first
// game authored directly in a .kotoba file, kotoba-lang/kotoba
// src/kami_survivors.kotoba, compiled by the real `kotoba wasm emit`)
// backed by kamiHostImports, drive the same 300 fixed steps, and check the
// EXACT entity counts kotoba's own JVM/Chicory test pins
// (kami-survivors-plays-deterministically-through-real-chicory,
// test/kotoba/kami_game_test.clj, seed 7): 12 ghosts at tick 240, 8 after
// the tick-270 nova burst, 10 at tick 300 — plus the axis-steering check.
// Run: `node test/verify-kami-survivors.mjs`
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { createKamiEcs, kamiHostImports } from '../src/kami-ecs.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const bytes = await readFile(path.join(here, '..', 'examples', 'kami-survivors', 'kami-survivors.wasm'));

let failed = false;
function check(cond, message) {
  if (!cond) {
    failed = true;
    console.error(`FAIL: ${message}`);
  } else {
    console.log(`OK: ${message}`);
  }
}

async function newGame(seed) {
  const ecs = createKamiEcs(seed);
  const memoryBox = {};
  const importObject = { kotoba: kamiHostImports(ecs, memoryBox) };
  const { instance } = await WebAssembly.instantiate(bytes, importObject);
  memoryBox.memory = instance.exports.memory;
  const runTicks = (n) => {
    let last;
    for (let i = 0; i < n; i++) {
      ecs.step();
      last = instance.exports.main();
    }
    return last;
  };
  return { ecs, runTicks };
}

// --- the pinned 300-tick run (seed 7, axes unset) -------------------------
{
  const { ecs, runTicks } = await newGame(7);
  check(runTicks(240) === 12, 'spawn every 20 ticks -> the 12-ghost cap is exactly reached at tick 240');
  check(runTicks(30) === 8, 'tick-270 nova burst despawns the 4 ghosts that reached the player');
  check(runTicks(30) === 10, 'spawning resumes after the burst: ticks 280/300 add 2');
  check(ecs.countTagged('player') === 1, 'exactly one player');
  check(ecs.countTagged('ghost') === 10, 'host state agrees with what main reported');
  check(ecs.totalSpawned() === 15, '1 player + 14 ghosts ever spawned, nothing else');
  check(Math.abs(ecs.getX(0)) < 1e-6, 'with both axes unset the player never left the origin');
}

// --- the host-owned input axis really steers the player --------------------
{
  const { ecs, runTicks } = await newGame(7);
  ecs.setAxis('MoveX', 1.0);
  runTicks(60);
  const px = ecs.getX(0);
  check(px > 58.9 && px < 59.1, `59 integrated steps moved the player to x=${px}`);
  check(Math.abs(ecs.getY(0)) < 1e-6, 'the unset MoveY axis left y untouched');
}

if (failed) process.exit(1);
console.log('OK: kami-survivors (.kotoba) plays the same game on native WebAssembly that kotoba pins on Chicory');
