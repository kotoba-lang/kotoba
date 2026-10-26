// Dependency-free smoke test for src/has-capability.js: instantiate
// examples/cap/demo-cap.wasm (declares a single has_capability(id) host
// import) both granted and denied, and confirm the same bytes answer
// differently -- proving the check is real (per-instantiation, driven by
// the caller's granted-capabilities list), not a stub that always answers
// one way. Mirrors kotoba-lang/kotoba's docs/lang/gates.md node -e check
// for demo_cap.wasm (main() === 7 when notify/show is granted).
// Run: `node test/verify-cap.mjs`
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { hasCapabilityHostImport } from '../src/has-capability.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const bytes = await readFile(path.join(here, '..', 'examples', 'cap', 'demo-cap.wasm'));

const { instance: granted } = await WebAssembly.instantiate(bytes, {
  kotoba: hasCapabilityHostImport(['notify/show']),
});
const { instance: denied } = await WebAssembly.instantiate(bytes, {
  kotoba: hasCapabilityHostImport([]),
});

let failed = false;
function check(cond, message) {
  if (!cond) {
    failed = true;
    console.error(`FAIL: ${message}`);
  } else {
    console.log(`OK: ${message}`);
  }
}

const grantedResult = granted.exports.main();
const deniedResult = denied.exports.main();

check(grantedResult === 7, `granted notify/show: main() === 7 (got ${grantedResult})`);
check(deniedResult === 0, `denied (no capabilities): main() === 0 (got ${deniedResult})`);

// An id outside CAPABILITY_IDS' range (201-218) is a distinct fail-closed
// branch from "known id, not granted": ID_TO_CAPABILITY[id] is undefined,
// so `name && granted.has(name)` short-circuits on `name` itself rather
// than on the Set lookup. Call it directly (no wasm involved) with a
// capability granted, to prove an unrecognized id can't be smuggled past
// the check by coincidentally matching a granted name.
const unknownIdHost = hasCapabilityHostImport(['notify/show']);
check(
  unknownIdHost.has_capability(9999) === 0,
  `unrecognized id 9999 (outside 201-218, some capabilities granted): has_capability() === 0 (got ${unknownIdHost.has_capability(9999)})`
);

if (failed) process.exit(1);
console.log('OK: has_capability answers differently per-instantiation from the same bytes (real check, not a stub)');
