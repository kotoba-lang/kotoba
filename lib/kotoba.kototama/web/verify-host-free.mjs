// Host-free pure guests under the browser/Node WebAssembly engine (R2).
// No actor-host imports — empty importObject. Mirrors JVM tender host-free path.
// Run: `node web/verify-host-free.mjs`
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));

async function runHostFree(name, expected) {
  const bytes = await readFile(path.join(here, name));
  const { instance } = await WebAssembly.instantiate(bytes, {});
  const result = Number(instance.exports.main());
  if (result !== expected) {
    throw new Error(`${name}: expected main()=${expected}, got ${result}`);
  }
  console.log(`OK: ${name} main()=${result} (host-free, zero imports)`);
}

await runHostFree('demo.wasm', 42);
await runHostFree('host-free-fact.wasm', 120);
await runHostFree('host-free-peak-cells.wasm', 240);

console.log(
  'OK: browser/Node WebAssembly engine ran host-free kotoba guests (fact + peak-cells + demo)',
);
