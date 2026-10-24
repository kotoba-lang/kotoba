import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [webPath, wasmPath, hostPath] = process.argv.slice(2);
if (!webPath || !wasmPath || !hostPath) throw new Error("missing conformance paths");

const expectedKind = (from, to) => {
  if (from === 0 && to === 1) return 1n;
  if (from === 1 && to === 2) return 1n;
  if (from === 2 && to === 3) return 2n;
  if (from === 2 && to === 1) return 1n;
  if (from === 3 && to === 4) return 1n;
  if (from === 3 && to === 7) return 2n;
  if (from === 4 && (to === 5 || to === 6 || to === 7)) return 2n;
  return 0n;
};

const web = await import(pathToFileURL(path.resolve(webPath)));
if (web.kotobaArtifact.requiredCapabilities.length !== 0)
  throw new Error("human gate requested a capability");
if (web.instantiateKotoba().main() !== 42n) throw new Error("Web main mismatch");
const host = await import(pathToFileURL(path.resolve(hostPath)));
const wasmBytes = fs.readFileSync(path.resolve(wasmPath));
const statusValues = [-9223372036854775808n, -1n, 0n, 1n, 2n, 3n, 4n, 5n, 6n, 7n, 8n, 9223372036854775807n];
const approvalValues = [-1n, 0n, 1n, 2n];
let cases = 0;
for (const from of statusValues) {
  for (const to of statusValues) {
    for (const approved of approvalValues) {
      const expected = expectedKind(Number(from), Number(to));
      const allowed = expected === 1n || (expected === 2n && approved === 1n) ? 1n : 0n;
      const args = [from, to];
      const webRuntime = web.instantiateKotoba();
      if (webRuntime["transition-kind"](...args) !== expected)
        throw new Error(`Web kind mismatch ${from}/${to}`);
      if (webRuntime["transition-allowed"](...args, approved) !== allowed)
        throw new Error(`Web approval mismatch ${from}/${to}/${approved}`);
      const wasm = await host.instantiateKotoba(wasmBytes);
      if (wasm.instance.exports["transition-kind"](...args) !== expected)
        throw new Error(`Wasm kind mismatch ${from}/${to}`);
      if (wasm.instance.exports["transition-allowed"](...args, approved) !== allowed)
        throw new Error(`Wasm approval mismatch ${from}/${to}/${approved}`);
      cases += 1;
    }
  }
}
console.log(`kyoninka-human-gate: ${cases} transition/approval boundary cases passed per target`);
