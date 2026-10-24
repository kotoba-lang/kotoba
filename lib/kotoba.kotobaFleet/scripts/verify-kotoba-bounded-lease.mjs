import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [webPath, wasmPath, hostPath] = process.argv.slice(2);
if (!webPath || !wasmPath || !hostPath) throw new Error("missing conformance paths");
const fixtures = [
  [[0n, 0n], 0n],
  [[1n, 50n, 11n, 4n, 0n, 100n, 0n], 11n],
  [[1n, 100n, 11n, 4n, 0n, 100n, 0n], 0n],
  [[1n, 50n, 11n, 4n, 0n, 100n, 1n], 0n],
  [[2n, 50n, 11n, 9n, 0n, 100n, 0n, 22n, 3n, 1n, 100n, 0n], 22n],
  [[3n, 50n, 11n, 9n, 0n, 100n, 1n, 22n, 3n, 1n, 100n, 0n, 33n, 7n, 2n, 10n, 0n], 22n],
  [[4n, 9223372036854775807n,
    1n, 40n, 9223372036854775806n, 2n, 0n,
    2n, 30n, 9223372036854775800n, 7n, 0n,
    3n, 20n, 0n, 9223372036854775807n, 0n,
    4n, 10n, 9223372036854775807n, 0n, 0n], 1n],
  [[], -1n], [[0n], -1n], [[-1n, 0n], -1n], [[5n, 0n], -1n],
  [[1n, -1n, 1n, 0n, 0n, 1n, 0n], -1n],
  [[1n, 0n, 0n, 0n, 0n, 1n, 0n], -1n],
  [[1n, 0n, 1n, -1n, 0n, 1n, 0n], -1n],
  [[1n, 0n, 1n, 0n, 1n, 1n, 0n], -1n],
  [[1n, 0n, 1n, 0n, 0n, -1n, 0n], -1n],
  [[1n, 0n, 1n, 0n, 0n, 1n, 2n], -1n],
  [[2n, 0n, 1n, 0n, 0n, 1n, 0n, 2n, 0n, 0n, 1n, 0n], -1n],
  [[1n, 0n, 1n, 0n, 0n, 1n], -1n],
];
for (const [input] of fixtures) Object.freeze(input);
const web = await import(pathToFileURL(path.resolve(webPath)));
if (web.kotobaArtifact.requiredCapabilities.length !== 0)
  throw new Error("bounded lease requested a capability");
if (web.instantiateKotoba().main() !== 42n) throw new Error("Web main mismatch");
const host = await import(pathToFileURL(path.resolve(hostPath)));
const wasmBytes = fs.readFileSync(path.resolve(wasmPath));
for (let i = 0; i < fixtures.length; i += 1) {
  const [input, expected] = fixtures[i];
  if (web.instantiateKotoba().holder(input) !== expected)
    throw new Error(`Web fixture ${i} mismatch`);
  const wasm = await host.instantiateKotoba(wasmBytes);
  if (wasm.instance.exports.holder(wasm.typedValues.vectorI64(input)) !== expected)
    throw new Error(`Wasm fixture ${i} mismatch`);
}
console.log(`fleet-bounded-lease: ${fixtures.length} cases passed per target`);
