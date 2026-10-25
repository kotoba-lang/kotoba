import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [webPath, wasmPath, hostPath] = process.argv.slice(2);
if (!webPath || !wasmPath || !hostPath) throw new Error("missing conformance paths");
const values = [-1n, 0n, 1n, 2n];
const expected = (action, booking, signed) => {
  if ((action !== 0n && action !== 1n) ||
      (booking !== 0n && booking !== 1n) ||
      (signed !== 0n && signed !== 1n)) return -1n;
  if (action === 0n) return booking === 0n && signed === 0n ? 1n : 0n;
  if (booking === 0n) return signed === 0n ? 1n : 0n;
  return signed === 1n ? 1n : 0n;
};
const web = await import(pathToFileURL(path.resolve(webPath)));
if (web.kotobaArtifact.requiredCapabilities.length !== 0)
  throw new Error("booking gate requested a capability");
if (web.instantiateKotoba().main() !== 42n) throw new Error("Web main mismatch");
const host = await import(pathToFileURL(path.resolve(hostPath)));
const wasmBytes = fs.readFileSync(path.resolve(wasmPath));
let cases = 0;
for (const action of values) for (const booking of values) for (const signed of values) {
  const result = expected(action, booking, signed);
  if (web.instantiateKotoba().delegated(action, booking, signed) !== result)
    throw new Error(`Web mismatch ${action}/${booking}/${signed}`);
  const wasm = await host.instantiateKotoba(wasmBytes);
  if (wasm.instance.exports.delegated(action, booking, signed) !== result)
    throw new Error(`Wasm mismatch ${action}/${booking}/${signed}`);
  cases += 1;
}
console.log(`koe-booking-gate: ${cases} canonical and malformed cases passed per target`);
