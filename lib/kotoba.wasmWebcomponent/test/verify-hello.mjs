// Dependency-free smoke test: instantiate examples/hello/hello.wasm with the
// JS engine's own WebAssembly implementation (same engine -- V8 -- a
// Chromium browser uses) and confirm main() returns 42. Checks the
// AOT-execution claim only; does not exercise KotobaWasmElement's DOM/
// customElements path (no DOM in plain Node). Run: `node test/verify-hello.mjs`
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const bytes = await readFile(path.join(here, '..', 'examples', 'hello', 'hello.wasm'));

const { instance } = await WebAssembly.instantiate(bytes, {});
const result = instance.exports.main();

if (result !== 42) {
  console.error(`FAIL: expected main() === 42, got ${result}`);
  process.exit(1);
}
console.log(`OK: hello.wasm main() => ${result}`);
