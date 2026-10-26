// Dependency-free smoke test for the browser-native WASM AOT path this
// directory demonstrates: instantiate demo.wasm with the JS engine's own
// WebAssembly implementation (same engine — V8 — a real browser uses) and
// confirm the exported `main` runs and returns the expected value. This does
// NOT exercise the DOM/customElements wrapper (kototama-wasm-run.js) —
// only the AOT-execution claim, which is the part that differs from the
// JVM+Chicory path in kotoba-lang/kotoba. Run: `node web/verify.mjs`
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const bytes = await readFile(path.join(here, 'demo.wasm'));

const { instance } = await WebAssembly.instantiate(bytes, {});
const result = instance.exports.main();

if (result !== 42) {
  console.error(`FAIL: expected main() === 42, got ${result}`);
  process.exit(1);
}

console.log(`OK: demo.wasm main() => ${result} (native WebAssembly engine, no JVM/Chicory/wasmtime)`);
