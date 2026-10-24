import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [webPath, wasmPath, hostPath] = process.argv.slice(2);
if (!webPath || !wasmPath || !hostPath) throw new Error("missing conformance paths");

const web = await import(pathToFileURL(path.resolve(webPath)));
if (web.kotobaArtifact.requiredCapabilities.length !== 0)
  throw new Error("ic-packaging bounded-thermal Web graph requested a capability");
if (web.instantiateKotoba().main() !== 42n) throw new Error("ic-packaging Web main mismatch");

const host = await import(pathToFileURL(path.resolve(hostPath)));
const wasmBytes = fs.readFileSync(path.resolve(wasmPath));
const wasm = await host.instantiateKotoba(wasmBytes);
if (wasm.instance.exports.main() !== 42n) throw new Error("ic-packaging Wasm main mismatch");

console.log("ic-packaging: bounded thermal Web/Wasm conformance passed");
