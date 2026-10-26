// Dependency-free smoke test for src/kgraph.js's kgraph-* host-import ABI
// port: instantiate examples/kgraph/demo-kgraph.wasm backed by
// kgraphHostImports, and check the result matches kotoba-lang/kotoba's own
// JVM/Chicory test (wasm-binary-runs-kgraph-round-trip-through-real-host-functions,
// test/kotoba/wasm_exec_test.clj) byte-for-byte. Run: `node test/verify-kgraph.mjs`
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { kgraphHostImports, readEdn, writeEdn } from '../src/kgraph.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const bytes = await readFile(path.join(here, '..', 'examples', 'kgraph', 'demo-kgraph.wasm'));

const store = [];
const memoryBox = {};
const importObject = { kotoba: kgraphHostImports(store, memoryBox) };

const { instance } = await WebAssembly.instantiate(bytes, importObject);
memoryBox.memory = instance.exports.memory;

const written = instance.exports.main();
const heapBase = 2048; // kotoba.runtime/wasm-binary's heap-base for this module
const resultBytes = new Uint8Array(memoryBox.memory.buffer, heapBase, written);
const resultText = new TextDecoder('utf-8').decode(resultBytes);

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
check(resultText === '[["Aoi"]]', `query result is [["Aoi"]] (got ${resultText})`);
check(
  store.length === 1 && store[0][0] === 1 && store[0][1].kw === 'name' && store[0][2] === 'Aoi',
  `store received the asserted datom (got ${writeEdn(store)})`
);

// readEdn/writeEdn's five error branches -- the wasm round trip above only
// ever exercises the reader/writer's happy path (a well-formed datom
// vector and query map). This library's own header comment says it's "NOT
// a general EDN implementation", so malformed input reaching these
// branches is a real, expected occurrence (a guest bug, a hand-crafted
// EDN literal typo), not just a theoretical edge case -- yet none of the
// five throw sites had ever been directly exercised.
function throws(fn, messageSubstring) {
  try {
    fn();
    return false;
  } catch (e) {
    return e.message.includes(messageSubstring);
  }
}

check(
  throws(() => readEdn('{1 2}'), 'only keyword-keyed maps are supported'),
  'readEdn rejects a non-keyword-keyed map (e.g. {1 2}), the wire ABI only ever carries keyword keys'
);
check(
  throws(() => readEdn('"abc'), 'unterminated string'),
  'readEdn rejects an unterminated string literal'
);
check(
  throws(() => readEdn('@'), 'unexpected character'),
  'readEdn rejects a character that starts neither a vector/map/string/keyword/number nor a valid symbol'
);
check(
  throws(() => writeEdn(undefined), 'cannot print'),
  'writeEdn rejects a value shape outside {vector, string, number, keyword, symbol} (e.g. undefined)'
);
check(
  throws(() => writeEdn({}), 'cannot print'),
  'writeEdn rejects a plain object that is neither a {kw} nor a {sym} wrapper'
);

if (failed) process.exit(1);
console.log('OK: kgraph.js round-trips through a real native-WebAssembly-hosted module');
