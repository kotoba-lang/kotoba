import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [webPath, wasmPath, hostPath] = process.argv.slice(2);
if (!webPath || !wasmPath || !hostPath) throw new Error("missing conformance paths");
const cases = [
  [[2n,2n,1n, 1n,1n, 2n,1n, 1n,10n,1n, 2n,20n,1n, 2n,1n],0n,0n,1n],
  [[1n,2n,0n, 1n,1n, 1n,10n,1n, 1n,10n,1n],1n,0n,0n],
  [[1n,1n,0n, 1n,1n, 1n,10n,0n],1n,0n,0n],
  [[1n,1n,0n, 1n,0n, 1n,10n,1n],0n,1n,1n],
  [[1n,1n,1n, 1n,1n, 1n,10n,1n, 1n,99n],1n,0n,0n],
  [[3n,4n,2n, 1n,0n, 2n,0n, 3n,0n,
    1n,10n,0n, 1n,10n,0n, 2n,20n,0n, 3n,30n,0n,
    1n,98n, 2n,99n],7n,3n,0n],
];
const rejected = [
  [], [0n], [0n,0n], [4n,0n,0n], [0n,5n,0n], [0n,0n,3n],
  [1n,0n,0n, 1n,2n], [2n,0n,0n, 1n,1n, 1n,0n],
  [1n,1n,0n, 1n,1n, 99n,10n,1n],
  [1n,0n,1n, 1n,1n, 99n,1n],
  [1n,1n,0n, 1n,1n, 1n,10n,2n],
  [1n,0n,0n, 1n],
];

const web = await import(pathToFileURL(path.resolve(webPath)));
if (web.kotobaArtifact.requiredCapabilities.length !== 0)
  throw new Error("DDL Web graph requested a capability");
if (web.instantiateKotoba().main() !== 42n) throw new Error("DDL Web main mismatch");
const host = await import(pathToFileURL(path.resolve(hostPath)));
const wasmBytes = fs.readFileSync(path.resolve(wasmPath));
let checked = 0;
for (const [values, errors, warnings, valid] of cases) {
  if (web.instantiateKotoba()["summary-check"](values, errors, warnings, valid) !== 42n)
    throw new Error(`Web summary mismatch at ${checked}`);
  const wasm = await host.instantiateKotoba(wasmBytes);
  if (wasm.instance.exports["summary-check"](
      wasm.typedValues.vectorI64(values), errors, warnings, valid) !== 42n)
    throw new Error(`Wasm summary mismatch at ${checked}`);
  checked++;
}
for (const values of rejected) {
  if (web.instantiateKotoba()["reject-check"](values) !== 42n)
    throw new Error(`Web rejection mismatch at ${checked}`);
  const wasm = await host.instantiateKotoba(wasmBytes);
  if (wasm.instance.exports["reject-check"](wasm.typedValues.vectorI64(values)) !== 42n)
    throw new Error(`Wasm rejection mismatch at ${checked}`);
  checked++;
}
console.log(`ddl-bounded: ${checked} Web/Wasm cases passed (including 3/4/2 ceiling)`);
