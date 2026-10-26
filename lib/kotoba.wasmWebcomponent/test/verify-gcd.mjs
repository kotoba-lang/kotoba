// Dependency-free smoke test: instantiate examples/gcd/gcd.wasm -- a
// brand-new .kotoba program (not reused from kotoba-lang/kotoba's demo
// fixtures) exercising real runtime recursion (Euclidean algorithm), not a
// compile-time-folded constant. Run: `node test/verify-gcd.mjs`
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const bytes = await readFile(path.join(here, '..', 'examples', 'gcd', 'gcd.wasm'));

const { instance } = await WebAssembly.instantiate(bytes, {});
const result = instance.exports.main();

if (result !== 21) {
  console.error(`FAIL: expected gcd(1071, 462) === 21, got ${result}`);
  process.exit(1);
}
console.log(`OK: gcd.wasm main() => gcd(1071, 462) = ${result}`);
