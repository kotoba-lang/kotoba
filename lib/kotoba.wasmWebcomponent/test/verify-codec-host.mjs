// Byte-for-byte parity check of the browser actor-host's codec imports
// (cbor-encode / json-encode / json-extract-field) against kototama.tender's
// (JVM) known outputs. These are pure computation -- no wasm guest, no
// network -- so they are driven directly through actorHostImports with a
// throwaway WebAssembly.Memory. Expected values are the ones documented in
// kototama/docs/maturity.md's R1 fixture table.
import { actorHostImports } from '../src/actor-host.js';

function memBox() {
  return { memory: new WebAssembly.Memory({ initial: 2 }) };
}
function driveCodec(id, fnName, inputStr) {
  const box = memBox();
  const caps = { grants: [id], limits: { maxMemoryPages: 100000, maxImports: 100 } };
  const fns = actorHostImports([id], caps, box, {});
  const mem = new Uint8Array(box.memory.buffer);
  const inBytes = new TextEncoder().encode(inputStr);
  mem.set(inBytes, 0);
  const n = fns[fnName](0, inBytes.length, 4096, 4096);
  return n < 0 ? { n } : { n, bytes: mem.slice(4096, 4096 + n) };
}
function driveExtract(json, field) {
  const box = memBox();
  const caps = { grants: ['json-extract-field'], limits: { maxMemoryPages: 100000, maxImports: 100 } };
  const fns = actorHostImports(['json-extract-field'], caps, box, {});
  const mem = new Uint8Array(box.memory.buffer);
  const jb = new TextEncoder().encode(json), fb = new TextEncoder().encode(field);
  mem.set(jb, 0); mem.set(fb, 2048);
  const n = fns.json_extract_field(0, jb.length, 2048, fb.length, 4096, 4096);
  return n < 0 ? { n } : { n, str: new TextDecoder().decode(mem.slice(4096, 4096 + n)) };
}
const hex = (u8) => Array.from(u8).map((b) => b.toString(16).padStart(2, '0')).join(' ');
const str = (u8) => new TextDecoder().decode(u8);

let failures = 0;
function check(name, got, want) {
  const pass = got === want;
  if (!pass) failures++;
  console.log(`${pass ? 'PASS' : 'FAIL'} ${name}${pass ? '' : ` | got ${got} | want ${want}`}`);
}

check('cbor flat {"a":"b"}', hex(driveCodec('cbor-encode', 'cbor_encode', 'a\tb').bytes), 'a1 61 61 61 62');
check('json flat {"a":"b"}', str(driveCodec('json-encode', 'json_encode', 'a\tb').bytes), '{"a":"b"}');
check('json-extract present', driveExtract('{"k":"v"}', 'k').str, 'v');
check('json-extract absent -> -1', String(driveExtract('{"k":"v"}', 'missing').n), '-1');
check('cbor nested = 25 bytes',
  String(driveCodec('cbor-encode', 'cbor_encode', 's.t\teip4361\ns.s\tsigvalue').n), '25');
check('json nested (object + array)',
  str(driveCodec('json-encode', 'json_encode',
    's.t\teip4361\ns.s\tsigvalue\np.resources.0\ta\np.resources.1\tb').bytes),
  '{"s":{"t":"eip4361","s":"sigvalue"},"p":{"resources":["a","b"]}}');
// A value cannot contain a literal newline (that is the flat-pairs line
// separator), so escaping is exercised on the quote and backslash chars.
check('json escapes quote and backslash',
  str(driveCodec('json-encode', 'json_encode', 'q\t"a\\b').bytes), '{"q":"\\"a\\\\b"}');

if (failures === 0) console.log('codec-host: CBOR/JSON parity passed');
else { console.error(`codec-host: ${failures} parity failure(s)`); process.exit(1); }
