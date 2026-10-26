// Dependency-free smoke test for actor-host-demo.wasm against
// kotoba-lang/wasm-webcomponent's actor-host.js host-import port (this repo
// carries the compiled `.wasm` only -- see index.html and README.md).
// Mirrors verify-kgraph.mjs's structure. Run: `node web/verify-actor-host.mjs`
import { readFile, mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { tmpdir } from 'node:os';
import path from 'node:path';

// Node has no flag-free `import()` of an https: URL, and a plain `data:` URL
// import (this script's original approach) can't resolve actor-host.js's own
// relative `./vendor/curves/ed25519.js` import (added when wasm-webcomponent
// landed real gen-keypair/sign/verify -- a data: URL has no base path for a
// relative specifier to resolve against). So: download actor-host.js AND its
// vendor/ tree to a real temp directory, preserving relative structure, and
// import from a file:// URL instead -- Node's normal ESM resolution then
// handles the relative imports exactly like a real checkout would. Pinned to
// the same commit index.html loads from jsdelivr -- bump both together,
// don't float on @main.
const WASM_WEBCOMPONENT_COMMIT = '1ebb54c8f5d60a8a5e8940c9ea7bf0ccb3104892';
const SRC_FILES = [
  'src/actor-host.js',
  'src/vendor/curves/ed25519.js',
  'src/vendor/curves/utils.js',
  'src/vendor/curves/abstract/curve.js',
  'src/vendor/curves/abstract/edwards.js',
  'src/vendor/curves/abstract/hash-to-curve.js',
  'src/vendor/curves/abstract/modular.js',
  'src/vendor/curves/abstract/montgomery.js',
  'src/vendor/hashes/_md.js',
  'src/vendor/hashes/_u64.js',
  'src/vendor/hashes/crypto.js',
  'src/vendor/hashes/sha2.js',
  'src/vendor/hashes/utils.js',
];

const tmpRoot = await mkdtemp(path.join(tmpdir(), 'kototama-actor-host-'));
for (const filePath of SRC_FILES) {
  const url = `https://cdn.jsdelivr.net/gh/kotoba-lang/wasm-webcomponent@${WASM_WEBCOMPONENT_COMMIT}/${filePath}`;
  const src = await (await fetch(url)).text();
  const dest = path.join(tmpRoot, filePath);
  await mkdir(path.dirname(dest), { recursive: true });
  await writeFile(dest, src);
}
const { actorHostImports, hostCaps, inMemoryStore, sessionAuthority } = await import(
  pathToFileURL(path.join(tmpRoot, 'src', 'actor-host.js'))
);

const here = path.dirname(fileURLToPath(import.meta.url));
const bytes = await readFile(path.join(here, 'actor-host-demo.wasm'));

const store = inMemoryStore();
const memoryBox = {};
const caps = hostCaps({
  grants: ['clock-monotonic', 'sha256-hex', 'log-write'],
  limits: { allowWriteImports: true },
});
const importObject = { kotoba: actorHostImports(['clock-monotonic', 'sha256-hex', 'log-write'], caps, memoryBox, { store }) };

const { instance } = await WebAssembly.instantiate(bytes, importObject);
memoryBox.memory = instance.exports.memory;

const written = Number(instance.exports.main());
const resultText = new TextDecoder('utf-8').decode(new Uint8Array(memoryBox.memory.buffer, 100, written));
const logged = new TextDecoder('utf-8').decode(store.read());

let failed = false;
function check(cond, message) {
  if (!cond) {
    failed = true;
    console.error(`FAIL: ${message}`);
  } else {
    console.log(`OK: ${message}`);
  }
}

check(written === 64, `main() wrote a 64-char sha256 hex digest (got ${written})`);
check(
  resultText === '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824',
  `guest-computed sha256("hello") matches the known digest (got ${resultText})`
);
check(logged === 'hello', `log_write recorded the guest's 5-byte payload (got ${JSON.stringify(logged)})`);

const liveAuthority = sessionAuthority(['clock-monotonic']);
const liveClock = actorHostImports(
  ['clock-monotonic'],
  hostCaps({ grants: ['clock-monotonic'] }),
  {},
  { authority: liveAuthority }
);
check(typeof liveClock.clock_monotonic() === 'bigint', 'browser session authority initially permits the linked clock');
liveAuthority.revoke('clock-monotonic');
let revoked = false;
try { liveClock.clock_monotonic(); } catch (_) { revoked = true; }
check(revoked, 'browser session revocation reaches an already-linked import');

await rm(tmpRoot, { recursive: true, force: true });

if (failed) {
  console.error('actor-host browser host-import verification FAILED');
  process.exit(1);
}
console.log('OK: browser-native WebAssembly engine ran clock_monotonic/log_write/sha256_hex through kotoba-lang/wasm-webcomponent\'s actor-host.js (no JVM/Chicory/wasmtime)');
