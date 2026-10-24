import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
const [webPath, wasmPath, hostPath] = process.argv.slice(2);
if (!webPath || !wasmPath || !hostPath) throw new Error("missing conformance paths");
const valid = [2n, 4n, 2n, 10n, 20n, 30n, 40n, 7n, 8n,
               1n, 7n, 2n, 10n, 20n, 2n, 8n, 1n, 30n, 0n];
const ceiling = [4n, 8n, 4n, 1n, 2n, 3n, 4n, 5n, 6n, 7n, 8n, 11n, 12n, 13n, 14n,
                 1n, 11n, 2n, 1n, 2n, 2n, 12n, 2n, 3n, 4n,
                 3n, 13n, 2n, 5n, 6n, 4n, 14n, 2n, 7n, 8n];
const fixtures = [
  [valid, 1n], [ceiling, 1n], [[0n, 0n, 0n], 1n],
  [[], -1n], [[0n], -1n], [[5n, 0n, 0n], -1n], [[0n, 9n, 0n], -1n], [[0n, 0n, 5n], -1n],
  [[...valid.slice(0, 9), 3n, ...valid.slice(10)], 0n],
  [[...valid.slice(0, 10), 9n, ...valid.slice(11)], 0n],
  [[...valid.slice(0, 12), 99n, ...valid.slice(13)], 0n],
  [[...valid.slice(0, 7), 7n, 7n, ...valid.slice(9)], -1n],
  [[...valid.slice(0, 3), 10n, 10n, ...valid.slice(5)], -1n],
  [[...valid.slice(0, 11), 3n, ...valid.slice(12)], -1n],
  [[...valid.slice(0, 11), 0n, 10n, 0n, ...valid.slice(14)], -1n],
  [[...valid, 0n], -1n],
];
for (const [input] of fixtures) Object.freeze(input);
const web = await import(pathToFileURL(path.resolve(webPath)));
if (web.kotobaArtifact.requiredCapabilities.length !== 0) throw new Error("capability requested");
if (web.instantiateKotoba().main() !== 42n) throw new Error("Web main mismatch");
const host = await import(pathToFileURL(path.resolve(hostPath)));
const wasmBytes = fs.readFileSync(path.resolve(wasmPath));
for (let i = 0; i < fixtures.length; i += 1) {
  const [input, expected] = fixtures[i];
  if (web.instantiateKotoba().validate(input) !== expected) throw new Error(`Web fixture ${i}`);
  const wasm = await host.instantiateKotoba(wasmBytes);
  if (wasm.instance.exports.validate(wasm.typedValues.vectorI64(input)) !== expected)
    throw new Error(`Wasm fixture ${i}`);
}
console.log(`giemon-construction-safety: ${fixtures.length} cases passed per target`);
