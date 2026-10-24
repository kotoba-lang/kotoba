// Conformance for search.bounded-search: RUN the compiled kernel on both
// backends and check the VALUE. `main` returns failures * 1000 + checks-run,
// never a boolean -- a boolean cannot tell one regression apart from a build
// that ran nothing, so this asserts the check COUNT too.
//
//   kbb -M:kotoba compile src/search/bounded_search.kotoba \
//     --target js-browser --output target/bs.mjs  --fuel 8192
//   kbb -M:kotoba compile src/search/bounded_search.kotoba \
//     --target wasm32     --output target/bs.wasm --fuel 8192
//   node scripts/verify-bounded-search.mjs target/bs.mjs target/bs.wasm \
//     <amu>/runtime/browser-host.mjs
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const EXPECTED_CHECKS = 52n;

const [webPath, wasmPath, hostPath] = process.argv.slice(2);
if (!webPath || !wasmPath || !hostPath)
  throw new Error("usage: verify-bounded-search.mjs <web.mjs> <wasm> <browser-host.mjs>");

const report = (backend, value) => {
  const failures = value / 1000n;
  const checks = value % 1000n;
  if (checks !== EXPECTED_CHECKS)
    throw new Error(
      `${backend} ran ${checks} checks, expected ${EXPECTED_CHECKS} ` +
      `(a self-check that runs nothing must not look like one that passed)`);
  if (failures !== 0n)
    throw new Error(`${backend} reported ${failures} failing check(s)`);
  console.log(`  ${backend}: ${checks} checks, 0 failures (main() = ${value})`);
};

const web = await import(pathToFileURL(path.resolve(webPath)));
if (web.kotobaArtifact.requiredCapabilities.length !== 0)
  throw new Error("search bounded-search Web graph requested a capability");
report("web", web.instantiateKotoba().main());

const host = await import(pathToFileURL(path.resolve(hostPath)));
const wasm = await host.instantiateKotoba(fs.readFileSync(path.resolve(wasmPath)));
report("wasm32", wasm.instance.exports.main());

console.log("search: bounded tokenize/term-count/score-doc conformance passed");
