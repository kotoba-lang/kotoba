import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [webPath, wasmPath, hostPath] = process.argv.slice(2);
if (!webPath || !wasmPath || !hostPath) {
  throw new Error("usage: verify-kotoba.mjs WEB.mjs MODULE.wasm BROWSER-HOST.mjs");
}

const web = await import(pathToFileURL(path.resolve(webPath)));
if (web.kotobaArtifact.requiredCapabilities.length !== 0) {
  throw new Error("bounded coll Web artifact requested a capability");
}
if (web.instantiateKotoba().main() !== 42n) {
  throw new Error("bounded coll Web self-check mismatch");
}

const host = await import(pathToFileURL(path.resolve(hostPath)));
const wasmBytes = fs.readFileSync(path.resolve(wasmPath));
const wasm = await host.instantiateKotoba(wasmBytes);
if (wasm.instance.exports.main() !== 42n) {
  throw new Error("bounded coll Wasm self-check mismatch");
}

console.log("coll: bounded Web/Wasm conformance passed");
