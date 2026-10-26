// Dependency-free smoke test for demo-kgraph.wasm against
// kotoba-lang/wasm-webcomponent's kgraph.js host-import port (this repo no
// longer carries its own copy -- see index.html and README.md). Mirrors
// kotoba-lang/kotoba's wasm-binary-runs-kgraph-round-trip-through-real-host-functions
// test (test/kotoba/wasm_exec_test.clj) byte-for-byte: same demo, same
// asserted datom, same expected query result. Run: `node web/verify-kgraph.mjs`
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

// Node has no flag-free `import()` of an https: URL; fetch the source and
// hand it to a `data:` URL instead (standard ESM, no --experimental-* flags,
// works the same on any Node >= 18). Pinned to the same commit index.html
// loads from jsdelivr -- bump both together, don't float on @main.
const WASM_WEBCOMPONENT_COMMIT = '154b09102d55b06ef10d0885504d02d91d347da9';
async function importFromJsdelivr(filePath) {
  const url = `https://cdn.jsdelivr.net/gh/kotoba-lang/wasm-webcomponent@${WASM_WEBCOMPONENT_COMMIT}/${filePath}`;
  const src = await (await fetch(url)).text();
  return import(`data:text/javascript;base64,${Buffer.from(src).toString('base64')}`);
}

const { kgraphHostImports, writeEdn } = await importFromJsdelivr('src/kgraph.js');

const here = path.dirname(fileURLToPath(import.meta.url));
const bytes = await readFile(path.join(here, 'demo-kgraph.wasm'));

const store = [];
const memoryBox = {};
const importObject = { kotoba: kgraphHostImports(store, memoryBox) };

const { instance } = await WebAssembly.instantiate(bytes, importObject);
memoryBox.memory = instance.exports.memory;

const written = instance.exports.main();

function readMemoryString(ptr, len) {
  const view = new Uint8Array(memoryBox.memory.buffer, ptr, len);
  return new TextDecoder('utf-8').decode(view);
}

const heapBase = 2048; // kotoba.runtime/wasm-binary's heap-base for this module (see kotoba-lang/kotoba's own test)
const resultText = readMemoryString(heapBase, written);

let failed = false;
function check(cond, message) {
  if (!cond) {
    failed = true;
    console.error(`FAIL: ${message}`);
  } else {
    console.log(`OK: ${message}`);
  }
}

check(written > 0, 'kgraph_query wrote a real result into the guest buffer');
check(resultText === '[["Aoi"]]', `query result read back out of guest memory is [["Aoi"]] (got ${resultText})`);
check(
  store.length === 1 && store[0][0] === 1 && store[0][1].kw === 'name' && store[0][2] === 'Aoi',
  `the browser-side kgraph store really received the asserted datom (got ${writeEdn(store)})`
);

if (failed) {
  console.error('kgraph browser host-import verification FAILED');
  process.exit(1);
}
console.log('OK: browser-native WebAssembly engine ran kgraph_assert!/kgraph_query through kotoba-lang/wasm-webcomponent\'s host-import store (no JVM/Chicory/wasmtime)');
