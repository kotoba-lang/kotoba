import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [webPath, wasmPath, hostPath] = process.argv.slice(2);
if (!webPath || !wasmPath || !hostPath) throw new Error("missing conformance paths");
const values = [
  -9223372036854775808n, -6148914691236517206n, -1n, 0n, 1n,
  6148914691236517205n, 9223372036854775807n,
];
const web = await import(pathToFileURL(path.resolve(webPath)));
if (web.kotobaArtifact.requiredCapabilities.length !== 0)
  throw new Error("SHA-256 primitive graph requested a capability");
if (web.instantiateKotoba().main() !== 42n) throw new Error("Web main mismatch");
const host = await import(pathToFileURL(path.resolve(hostPath)));
const wasmBytes = fs.readFileSync(path.resolve(wasmPath));
let checked = 0;
for (const x of values) for (const y of values) for (const z of values) {
  const expectedCh = BigInt.asIntN(64, (x & y) ^ ((x ^ -1n) & z));
  const expectedMaj = BigInt.asIntN(64, (x & y) ^ (x & z) ^ (y & z));
  const webRuntime = web.instantiateKotoba();
  if (webRuntime["ch-value"](x, y, z) !== expectedCh)
    throw new Error(`Web Ch oracle mismatch ${x}/${y}/${z}`);
  if (webRuntime["maj-value"](x, y, z) !== expectedMaj)
    throw new Error(`Web Maj oracle mismatch ${x}/${y}/${z}`);
  if (webRuntime["ch-check"](x, y, z) !== 42n) throw new Error(`Web Ch mismatch ${x}/${y}/${z}`);
  if (webRuntime["maj-check"](x, y, z) !== 42n) throw new Error(`Web Maj mismatch ${x}/${y}/${z}`);
  const wasm = await host.instantiateKotoba(wasmBytes);
  if (wasm.instance.exports["ch-value"](x, y, z) !== expectedCh)
    throw new Error(`Wasm Ch oracle mismatch ${x}/${y}/${z}`);
  if (wasm.instance.exports["maj-value"](x, y, z) !== expectedMaj)
    throw new Error(`Wasm Maj oracle mismatch ${x}/${y}/${z}`);
  if (wasm.instance.exports["ch-check"](x, y, z) !== 42n)
    throw new Error(`Wasm Ch mismatch ${x}/${y}/${z}`);
  if (wasm.instance.exports["maj-check"](x, y, z) !== 42n)
    throw new Error(`Wasm Maj mismatch ${x}/${y}/${z}`);
  checked += 2;
}
console.log(`sha256d-round-primitives: ${checked} Web/Wasm signed-i64 checks passed`);
