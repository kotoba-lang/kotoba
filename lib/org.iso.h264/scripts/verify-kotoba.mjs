import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [artifactDirectory, hostPath] = process.argv.slice(2);
if (!artifactDirectory || !hostPath) throw new Error("usage: verify-kotoba ARTIFACT_DIR BROWSER_HOST");

const host = await import(pathToFileURL(path.resolve(hostPath)));
for (const name of ["expgolomb", "sps", "ebsp"]) {
  const web = await import(pathToFileURL(path.resolve(artifactDirectory, `${name}.mjs`)));
  const webInstance = web.instantiateKotoba();
  if (webInstance.main() !== 42n) throw new Error(`${name}: Web result mismatch`);
  if (web.kotobaArtifact.requiredCapabilities.length !== 0)
    throw new Error(`${name}: Web artifact requested a capability`);

  const wasm = await host.instantiateKotoba(fs.readFileSync(path.resolve(artifactDirectory, `${name}.wasm`)));
  if (wasm.instance.exports.main() !== 42n) throw new Error(`${name}: Wasm result mismatch`);
  if (name === "ebsp") {
    const oversized = Array.from({ length: 129 }, () => 0n);
    if (web.instantiateKotoba()["oversize-check"](oversized) !== 42n)
      throw new Error("ebsp: Web NAL limit mismatch");
    if (wasm.instance.exports["oversize-check"](wasm.typedValues.bytes(Buffer.alloc(129))) !== 42n)
      throw new Error("ebsp: Wasm NAL limit mismatch");
  }
}

console.log("kotoba-conformance: Exp-Golomb, RBSP, and real SPS Web/Wasm parity passed");
