import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [webPath, wasmPath, hostPath] = process.argv.slice(2);
if (!webPath || !wasmPath || !hostPath) {
  throw new Error("usage: verify-kotoba.mjs WEB.mjs MODULE.wasm BROWSER-HOST.mjs");
}

const web = await import(pathToFileURL(path.resolve(webPath)));
if (web.kotobaArtifact.requiredCapabilities.length !== 0) {
  throw new Error("canonical document Web artifact requested a capability");
}
if (web.instantiateKotoba().main() !== 42n) {
  throw new Error("canonical document Web self-check mismatch");
}
const webInstance = web.instantiateKotoba();
if (webInstance["symbol-roundtrip?"]() !== true) {
  throw new Error("textual EDN Web symbol roundtrip mismatch");
}
if (webInstance["write-string"](webInstance["read-string"]("(actor/run 7)")) !== "(actor/run 7)") {
  throw new Error("textual EDN Web list roundtrip mismatch");
}
if (webInstance["write-string"](webInstance["read-string"]("#{\"one\" 1 :ready}")) !== "#{1 :ready \"one\"}") {
  throw new Error("textual EDN Web set roundtrip mismatch");
}
if (webInstance["write-string"](webInstance["read-string"]("{:b false, :a 1}")) !== "{:a 1 :b false}") {
  throw new Error("textual EDN Web canonicalization mismatch");
}
if (webInstance["write-string"](webInstance["read-string"]("{[1 2] :pair, \"name\" 7, :ready true}")) !== "{:ready true \"name\" 7 [1 2] :pair}") {
  throw new Error("textual EDN Web general map mismatch");
}
let webDenied = false;
try { webInstance["reject-tag"](); } catch (_) { webDenied = true; }
if (!webDenied) throw new Error("textual EDN Web tag denial mismatch");
let webDuplicateDenied = false;
try { webInstance["reject-general-duplicate"](); } catch (_) { webDuplicateDenied = true; }
if (!webDuplicateDenied) throw new Error("textual EDN Web general duplicate denial mismatch");

const host = await import(pathToFileURL(path.resolve(hostPath)));
const wasm = await host.instantiateKotoba(fs.readFileSync(path.resolve(wasmPath)));
if (wasm.instance.exports.main() !== 42n) {
  throw new Error("canonical document Wasm self-check mismatch");
}
const wasmSymbolRoundtrip = wasm.instance.exports["symbol-roundtrip?"]();
if (!(wasmSymbolRoundtrip === true || wasmSymbolRoundtrip === 1 || wasmSymbolRoundtrip === 1n)) {
  throw new Error("textual EDN Wasm symbol roundtrip mismatch");
}
if (wasm.instance.exports["write-string"](wasm.instance.exports["read-string"]("(actor/run 7)")) !== "(actor/run 7)") {
  throw new Error("textual EDN Wasm list roundtrip mismatch");
}
if (wasm.instance.exports["write-string"](wasm.instance.exports["read-string"]("#{\"one\" 1 :ready}")) !== "#{1 :ready \"one\"}") {
  throw new Error("textual EDN Wasm set roundtrip mismatch");
}
if (wasm.instance.exports["write-string"](wasm.instance.exports["read-string"]("{[1 2] :pair, \"name\" 7, :ready true}")) !== "{:ready true \"name\" 7 [1 2] :pair}") {
  throw new Error("textual EDN Wasm general map mismatch");
}
let wasmDenied = false;
try { wasm.instance.exports["reject-tag"](); } catch (_) { wasmDenied = true; }
if (!wasmDenied) throw new Error("textual EDN Wasm tag denial mismatch");
let wasmDuplicateDenied = false;
try { wasm.instance.exports["reject-general-duplicate"](); } catch (_) { wasmDuplicateDenied = true; }
if (!wasmDuplicateDenied) throw new Error("textual EDN Wasm general duplicate denial mismatch");

console.log("edn: canonical + textual document Web/Wasm conformance passed");
