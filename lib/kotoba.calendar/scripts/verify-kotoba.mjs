import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [webPath, wasmPath, hostPath] = process.argv.slice(2);
if (!webPath || !wasmPath || !hostPath) throw new Error("missing conformance paths");
const web = await import(pathToFileURL(path.resolve(webPath)));
if (web.kotobaArtifact.requiredCapabilities.length !== 0)
  throw new Error("calendar Web graph requested a capability");
if (web.instantiateKotoba().main() !== 42n) throw new Error("calendar Web result mismatch");
const host = await import(pathToFileURL(path.resolve(hostPath)));
const wasm = await host.instantiateKotoba(fs.readFileSync(path.resolve(wasmPath)));
if (wasm.instance.exports.main() !== 42n) throw new Error("calendar Wasm result mismatch");
console.log("calendar-kotoba: bounded Web/Wasm conformance passed");
