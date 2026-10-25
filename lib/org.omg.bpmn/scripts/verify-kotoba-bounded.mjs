import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [webPath, wasmPath, hostPath] = process.argv.slice(2);
if (!webPath || !wasmPath || !hostPath) throw new Error("missing conformance paths");

const cases = [
  [[3n, 2n, 1n, 0n, -1n, 2n, 4n, -1n, 3n, 1n, -1n,
    10n, 1n, 2n, 0n, 11n, 2n, 3n, 0n], 0n, 0n, 1n],
  [[2n, 2n, 1n, 0n, -1n, 2n, 1n, -1n,
    10n, 1n, 99n, 0n, 11n, 1n, 2n, 0n], 1n, 0n, 0n],
  [[1n, 0n, 1n, 4n, -1n], 0n, 4n, 1n],
  [[4n, 3n, 1n, 0n, -1n, 2n, 2n, -1n, 3n, 1n, -1n, 4n, 1n, -1n,
    10n, 1n, 2n, 0n, 11n, 2n, 3n, 1n, 12n, 2n, 4n, 0n], 0n, 1n, 1n],
  [[4n, 3n, 1n, 0n, -1n, 2n, 3n, -1n, 3n, 1n, -1n, 4n, 1n, -1n,
    10n, 1n, 2n, 0n, 11n, 2n, 3n, 1n, 12n, 2n, 4n, 1n], 0n, 1n, 1n],
  [[4n, 3n, 1n, 0n, -1n, 2n, 3n, 12n, 3n, 1n, -1n, 4n, 1n, -1n,
    10n, 1n, 2n, 0n, 11n, 2n, 3n, 1n, 12n, 2n, 4n, 0n], 0n, 0n, 1n],
  [[4n, 3n, 1n, 0n, -1n, 2n, 4n, -1n, 3n, 4n, -1n, 4n, 1n, -1n,
    10n, 99n, 98n, 0n, 11n, 99n, 98n, 0n, 12n, 99n, 98n, 0n], 6n, 6n, 0n],
];
const rejected = [
  [], [1n], [5n, 0n], [0n, 4n], [1n, 0n, 1n, 5n, -1n],
  [1n, 0n, -1n, 4n, -1n], [2n, 0n, 1n, 0n, -1n, 1n, 1n, -1n],
  [1n, 1n, 1n, 0n, -1n, 10n, 1n, 1n, 2n], [1n, 0n, 1n, 0n],
];

const web = await import(pathToFileURL(path.resolve(webPath)));
if (web.kotobaArtifact.requiredCapabilities.length !== 0)
  throw new Error("BPMN Web graph requested a capability");
if (web.instantiateKotoba().main() !== 42n) throw new Error("BPMN Web main mismatch");

const host = await import(pathToFileURL(path.resolve(hostPath)));
const wasmBytes = fs.readFileSync(path.resolve(wasmPath));
let checked = 0;
for (const [values, errors, warnings, valid] of cases) {
  const webRuntime = web.instantiateKotoba();
  if (webRuntime["summary-check"](values, errors, warnings, valid) !== 42n)
    throw new Error(`Web summary mismatch at case ${checked}`);
  const wasm = await host.instantiateKotoba(wasmBytes);
  if (wasm.instance.exports["summary-check"](
      wasm.typedValues.vectorI64(values), errors, warnings, valid) !== 42n)
    throw new Error(`Wasm summary mismatch at case ${checked}`);
  checked++;
}
for (const values of rejected) {
  const webRuntime = web.instantiateKotoba();
  if (webRuntime["reject-check"](values) !== 42n)
    throw new Error(`Web rejection mismatch at case ${checked}`);
  const wasm = await host.instantiateKotoba(wasmBytes);
  if (wasm.instance.exports["reject-check"](wasm.typedValues.vectorI64(values)) !== 42n)
    throw new Error(`Wasm rejection mismatch at case ${checked}`);
  checked++;
}
console.log(`bpmn-bounded: ${checked} Web/Wasm conformance cases passed (including 4/3 ceiling)`);
