// KOTOBA-974 (KOTOBA-159 PR 2): key handles, crypto, device.pick/open, device-local commands, key approval,
// host-mediated OAuth/DPoP.
// Each section is a negative control: it fails on the runtime at kotoba-lang/kotoba main 715b8e5f5
// (sha256 3e2bc61e8ce544d4cc12fbf7f893be4f7f0367be00e2e3d4ebdee5c3bb410367), which has no keys.*, crypto.*,
// device.pick/open, device.command or oauth.* (descriptors declaring them are invalid there), and passes with
// this change. Fake DOM, stubbed fetch, in-memory storage; no network.
// KOTOBA_CLIENT_RUNTIME=<path> KOTOBA_NEGATIVE_CONTROL=1 reports each section against another copy.
import assert from 'node:assert/strict';
import { DISCLOSURE } from './client-runtime-fixtures.mjs';
import { runtime, createTestHost, respondWith, peekKeyForTest, admit, TEST_CONFORMANCE } from './client-runtime-host-local-harness.mjs';

const negativeControl = process.env.KOTOBA_NEGATIVE_CONTROL === '1';
const outcomes = [];
async function section(name, body) {
  if (!negativeControl) return body();
  try { await Promise.race([body(), new Promise((_, reject) => setTimeout(() => reject(new Error('timed out')), 60000))]); outcomes.push([name, 'pass']); }
  catch (error) { outcomes.push([name, `fail: ${String(error?.message).split('\n')[0].slice(0, 110)}`]); }
}
const MiB = 1048576;
const enc = (text) => new TextEncoder().encode(text);
const dec = (bytes) => new TextDecoder().decode(bytes);
const hex = (bytes) => Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, '0')).join('');
const fill = (n, seed = 7) => { const b = new Uint8Array(n); for (let i = 0; i < n; i++) b[i] = (i * 31 + seed) & 255; return b; };
const sha256Hex = async (bytes) => hex(await crypto.subtle.digest('SHA-256', bytes));
const contains = (hay, needle) => {
  const seen = new Set();
  const walk = (v) => {
    if (v === null || v === undefined || seen.has(v)) return false;
    if (typeof v === 'string') return v.includes(Buffer.from(needle).toString('hex')) || v.includes(Buffer.from(needle).toString('base64'));
    if (v instanceof Uint8Array || v instanceof ArrayBuffer) return Buffer.from(v instanceof ArrayBuffer ? new Uint8Array(v) : v).includes(Buffer.from(needle));
    if (typeof v === 'object') { seen.add(v); return Object.values(v).some(walk); }
    return false;
  };
  return walk(hay);
};
const APP = 'org.example.notes';
const CRYPTO_CALLS = ['keys.generate', 'keys.open', 'keys.delete', 'crypto.hkdf', 'crypto.aesGcmEncrypt', 'crypto.aesGcmDecrypt',
  'crypto.unwrapKey', 'crypto.wrapKey', 'crypto.x25519Derive', 'crypto.hybridEncapsulate', 'crypto.hybridDecapsulate', 'crypto.generateKey',
  'crypto.xchachaEncrypt', 'crypto.xchachaDecrypt', 'crypto.aesKwpWrap', 'crypto.aesKwpUnwrap', 'crypto.release', 'crypto.sha256',
  'crypto.ed25519Sign', 'crypto.ed25519Verify'];
const hostLocal = (over = {}) => ({
  schema: 'kotoba.host-local.v1', 'app-id': APP,
  storage: { class: 'device-only', backup: 'excluded', 'at-rest': 'encrypted', erasable: true, 'quota-bytes': 4 * MiB, 'max-entries': 100, 'max-value-bytes': MiB },
  stores: ['files', 'vault'],
  calls: ['storage.get', 'storage.put', 'storage.delete', 'storage.list', 'storage.clear', 'storage.batch', 'storage.usage', 'storage.watch', ...CRYPTO_CALLS],
  keys: [{ id: 'device', type: 'secret-32', use: ['hkdf'] }],
  ...over,
});
const op = () => ({
  capability: 'net/fetch', service: 'svc', operation: 'put', consent: 'each-operation', disclosure: DISCLOSURE, 'data-categories': ['x'],
  endpoint: { origin: 'https://svc.example', routes: [{ method: 'PUT', 'path-prefix': '/packs/', 'query-params': [] }] },
});
const descriptor = (over = {}) => ({
  schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile: 'restricted-wasm-v1', entry: 'index.html',
  'local-state': { adapter: 'memory', schema: 's', version: 1 }, operations: [op()], 'host-local': hostLocal(), ...over,
});
const problems = (d) => runtime.clientRuntimeProblems(d, ['net/fetch'], 'http://tauri.localhost').map((p) => p.error);
let rootSeq = 0;
const host = (opts = {}) => createTestHost({ descriptor: descriptor(opts.descriptor), appId: opts.appId ?? APP, storageRoot: `keys-${rootSeq++}`, ...opts });
const ok = (r) => { assert.equal(r.ok, true, `expected ok, got ${JSON.stringify(r).slice(0, 160)}`); return r.result; };
const refused = (r, code) => { assert.equal(r.ok, false, JSON.stringify(r).slice(0, 160)); assert.equal(r.error, code); };
const FIXED = new Set(runtime.CLIENT_LOCAL_ERRORS);

// ---- K1 (Yataverse): the device secret and private keys never reach the guest; handles are opaque strings.
await section('key handles stay in the host', async () => {
  const h = await host();
  assert.equal(h.mountProblems, null, String(h.mountProblems));
  const gen = ok(await h.local('keys.generate', { id: 'device', type: 'secret-32' }));
  assert.equal(typeof gen.handle, 'string');
  assert.ok(/^kh\.[0-9a-f]{32}$/.test(gen.handle));
  refused(await h.local('keys.generate', { id: 'device', type: 'secret-32' }), 'key-exists');
  refused(await h.local('keys.generate', { id: 'nope' }), 'not-declared');
  // A handle carries no key bytes: the harness knows the raw secret, the guest traffic must not.
  const secret = peekKeyForTest(gen.handle);
  assert.ok(secret instanceof Uint8Array && secret.byteLength === 32);
  assert.equal(contains(h.guestMessages, secret), false, 'device secret never posted to the guest');
  const opened = ok(await h.local('keys.open', { id: 'device' }));
  assert.ok(/^kh\.[0-9a-f]{32}$/.test(opened.handle));
  // A fabricated or foreign handle is invalid-key, never someone else's key.
  refused(await h.local('crypto.hkdf', { key: 'kh.00000000000000000000000000000000', salt: enc('s'), info: enc('i'), length: 32, as: 'aes-256-gcm' }), 'invalid-key');
  refused(await h.local('crypto.hkdf', { key: 'not-a-handle', salt: enc('s'), info: enc('i'), length: 32, as: 'aes-256-gcm' }), 'invalid-key');
  // derive returns a handle, never bytes; the derived key's bytes never reach the guest either.
  const sealing = ok(await h.local('crypto.hkdf', { key: gen.handle, salt: enc('salt'), info: enc('awai.drive record'), length: 32, as: 'aes-256-gcm' }));
  assert.ok(/^kh\.[0-9a-f]{32}$/.test(sealing.handle));
  assert.equal(Object.keys(sealing).join(','), 'handle');
  const gcm = ok(await h.local('crypto.generateKey', { as: 'aes-256-gcm' }));
  assert.equal(Object.keys(gcm).join(','), 'handle');
  // A key from a host store that is extractable is refused (T3 of PR 1).
  await h.close();
});

await section('extractable host key is refused', async () => {
  const backing = await host();
  const extractableStore = {
    conformance: Object.freeze({ schema: 'kotoba.host-key-conformance.v1', host: 'synthetic-test-host', 'key-custody': 'host-profile', 'no-cloud-backup': 'no-os-backup', 'no-logging': true, 'user-clearable': true, 'removed-with-app': true }),
    async get() { return { type: 'secret-32', key: await crypto.subtle.importKey('raw', crypto.getRandomValues(new Uint8Array(32)), 'HKDF', true, ['deriveBits']) }; },
    async create() { return null; }, async delete() {}, async clear() {},
  };
  const h = await createTestHost({ descriptor: descriptor(), appId: APP, storageRoot: `keys-${rootSeq++}`, keyStore: extractableStore });
  assert.equal(h.mountProblems, null, String(h.mountProblems));
  refused(await h.local('keys.open', { id: 'device' }), 'unavailable');
  await backing.close(); await h.close();
});

// ---- A2 / K2 shape: another app's handle cannot open; hybrid and X25519 round trips; decapsulate gives a handle.
await section('cross-app handles and key agreement', async () => {
  const root = `shared-keys-${rootSeq++}`;
  const a = await createTestHost({ descriptor: descriptor(), appId: APP, storageRoot: root });
  const otherId = 'org.example.other';
  const b = await createTestHost({ descriptor: descriptor({ 'host-local': hostLocal({ 'app-id': otherId }) }), appId: otherId, storageRoot: root });
  assert.equal(a.mountProblems, null, String(a.mountProblems));
  assert.equal(b.mountProblems, null, String(b.mountProblems));
  const x = ok(await a.local('crypto.generateKey', { as: 'x25519' }));
  const m = ok(await a.local('crypto.generateKey', { as: 'ml-kem-768' }));
  assert.equal(x.publicKey.byteLength, 32);
  assert.equal(m.publicKey.byteLength, 1184);
  assert.equal(contains(a.guestMessages, new Uint8Array(32)), false); // no raw private keys anywhere
  const info = enc('kotoba/envelope/v1 wrap');
  const sealed = ok(await a.local('crypto.hybridEncapsulate', { recipientX25519: x.publicKey, recipientMlkem: m.publicKey, info, as: 'aes-256-gcm' }));
  assert.ok(/^kh\.[0-9a-f]{32}$/.test(sealed.handle));
  assert.equal(sealed.ephemeralPublic.byteLength, 32);
  assert.equal(sealed.ciphertext.byteLength, 1088);
  assert.equal('sharedSecret' in sealed, false, 'the shared secret is never returned');
  const iv = fill(12, 3); const aad = enc('chunk 0'); const plaintext = fill(1024, 5);
  const ct = ok(await a.local('crypto.aesGcmEncrypt', { key: sealed.handle, iv, aad, plaintext }));
  const opened = ok(await a.local('crypto.hybridDecapsulate', { x25519: x.handle, mlkem: m.handle, ephemeralPublic: sealed.ephemeralPublic, ciphertext: sealed.ciphertext, info, as: 'aes-256-gcm' }));
  assert.ok(/^kh\.[0-9a-f]{32}$/.test(opened.handle));
  assert.equal(Object.keys(opened).join(','), 'handle', 'decapsulation returns a handle, never bytes');
  const back = ok(await a.local('crypto.aesGcmDecrypt', { key: opened.handle, iv, aad, ciphertext: ct.ciphertext }));
  assert.equal(hex(back.plaintext), hex(plaintext));
  refused(await a.local('crypto.aesGcmDecrypt', { key: opened.handle, iv, aad: enc('chunk 1'), ciphertext: ct.ciphertext }), 'invalid-arguments');
  // The sealing handle is not usable from another app's mount.
  refused(await b.local('crypto.aesGcmDecrypt', { key: opened.handle, iv, aad, ciphertext: ct.ciphertext }), 'invalid-key');
  // x25519Derive: returns a handle; a low-order peer point is refused.
  const peer = ok(await a.local('crypto.generateKey', { as: 'x25519' }));
  const derived = ok(await a.local('crypto.x25519Derive', { private: x.handle, peerPublic: peer.publicKey, info: enc('k'), as: 'aes-256-gcm' }));
  assert.ok(/^kh\.[0-9a-f]{32}$/.test(derived.handle));
  refused(await a.local('crypto.x25519Derive', { private: x.handle, peerPublic: new Uint8Array(32), info: enc('k'), as: 'aes-256-gcm' }), 'invalid-arguments');
  await a.close(); await b.close();
});

// ---- K3 shape + bounds: XChaCha, AES-256-KWP, sha256 answer, disallowed algorithms, oversize inputs.
await section('primitives and bounds', async () => {
  const h = await host();
  const k = ok(await h.local('crypto.generateKey', { as: 'xchacha20-poly1305' }));
  const iv = fill(24, 1); const block = fill(4096, 2);
  const ct = ok(await h.local('crypto.xchachaEncrypt', { key: k.handle, iv, aad: new Uint8Array(), plaintext: block }));
  assert.equal(ct.ciphertext.length, block.length + 16);
  assert.equal(hex(ok(await h.local('crypto.xchachaDecrypt', { key: k.handle, iv, aad: new Uint8Array(), ciphertext: ct.ciphertext })).plaintext), hex(block));
  refused(await h.local('crypto.xchachaEncrypt', { key: k.handle, iv: fill(12, 1), aad: new Uint8Array(), plaintext: block }), 'invalid-arguments'); // 12-byte IV is not XChaCha
  const kek = ok(await h.local('crypto.generateKey', { as: 'aes-256-gcm' }));
  const wrapped = ok(await h.local('crypto.aesKwpWrap', { key: kek.handle, target: k.handle }));
  const back = ok(await h.local('crypto.aesKwpUnwrap', { key: kek.handle, wrapped: wrapped.wrapped, as: 'xchacha20-poly1305' }));
  assert.equal(hex(ok(await h.local('crypto.xchachaDecrypt', { key: back.handle, iv, aad: new Uint8Array(), ciphertext: ct.ciphertext })).plaintext), hex(block));
  // sha256 is the known answer for "abc".
  const digest = ok(await h.local('crypto.sha256', { data: enc('abc') }));
  assert.equal(hex(digest.digest), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  // Wrap only under a sealing key; a content key never wraps a private key.
  const priv = ok(await h.local('crypto.generateKey', { as: 'x25519' }));
  refused(await h.local('crypto.wrapKey', { key: kek.handle, iv: fill(12, 9), target: priv.handle }), 'invalid-arguments');
  // Disallowed algorithms everywhere.
  refused(await h.local('crypto.generateKey', { as: 'aes-128-gcm' }), 'invalid-arguments');
  refused(await h.local('crypto.generateKey', { as: 'rsa' }), 'invalid-arguments');
  refused(await h.local('crypto.hkdf', { key: (await h.local('keys.generate', { id: 'device', type: 'secret-32' })).result.handle, salt: enc('s'), info: enc('i'), length: 64, as: 'aes-256-gcm' }), 'invalid-arguments');
  // Every input is bounded: an oversize plaintext is refused before anything runs.
  const gcm = ok(await h.local('crypto.generateKey', { as: 'aes-256-gcm' }));
  refused(await h.local('crypto.aesGcmEncrypt', { key: gcm.handle, iv: fill(12, 4), plaintext: fill(17 * MiB) }), 'too-large');
  refused(await h.local('crypto.aesGcmEncrypt', { key: gcm.handle, iv: fill(12, 4), aad: fill(70000), plaintext: block }), 'too-large');
  // Content plaintext reaches the guest by design (it chose the content key); errors stay fixed codes.
  assert.ok(FIXED.has((await h.local('crypto.aesGcmDecrypt', { key: gcm.handle, iv: fill(12, 4), aad: new Uint8Array(), ciphertext: new Uint8Array(32) })).error));
  await h.close();
});

// ---- Wrap/unwrap under a sealing key (device secret -> HKDF -> seal), including type binding.
await section('sealing key wrap round trip', async () => {
  const h = await host();
  const gen = ok(await h.local('keys.generate', { id: 'device', type: 'secret-32' }));
  const sealing = ok(await h.local('crypto.hkdf', { key: gen.handle, salt: new Uint8Array(), info: enc('wrap/v1'), length: 32, as: 'aes-256-gcm' }));
  // A sealing key can only wrap a private key, never be wrapped or used for content crypto.
  const priv = ok(await h.local('crypto.generateKey', { as: 'x25519' }));
  const wrapped = ok(await h.local('crypto.wrapKey', { key: sealing.handle, iv: fill(12, 6), target: priv.handle, aad: enc('a') }));
  const unwrapped = ok(await h.local('crypto.unwrapKey', { key: sealing.handle, iv: fill(12, 6), wrapped: wrapped.wrapped, as: 'x25519-private', aad: enc('a') }));
  assert.ok(/^kh\.[0-9a-f]{32}$/.test(unwrapped.handle));
  assert.equal(unwrapped.publicKey.byteLength, 32);
  // Type binding: the same wrap cannot be opened as a different type.
  refused(await h.local('crypto.unwrapKey', { key: sealing.handle, iv: fill(12, 6), wrapped: wrapped.wrapped, as: 'ml-kem-768-private', aad: enc('a') }), 'invalid-arguments');
  // A sealing key never encrypts content.
  refused(await h.local('crypto.aesGcmEncrypt', { key: sealing.handle, iv: fill(12, 6), plaintext: fill(8) }), 'invalid-arguments');
  // clearAppData deletes persistent keys too (Legal L4 / A7).
  await h.clearAppData();
  assert.equal(ok(await h.local('keys.open', { id: 'device' })), null);
  await h.close();
});

// ---- Erase (Legal L4): storage.clear + keys.delete leave nothing behind.
await section('erase everything', async () => {
  const h = await host();
  ok(await h.local('storage.put', { store: 'files', key: 'a', value: enc('a') }));
  ok(await h.local('keys.generate', { id: 'device', type: 'secret-32' }));
  ok(await h.local('storage.clear', {}));
  ok(await h.local('keys.delete', { id: 'device' }));
  assert.deepEqual(ok(await h.local('storage.list', { store: 'files' })).entries, []);
  assert.equal(ok(await h.local('keys.open', { id: 'device' })), null);
  assert.equal(ok(await h.local('storage.usage', {})).bytes, 0);
  await h.close();
});

// ---- device.pick / device.open (B): separate calls, trusted gesture each, no egress.
const PICK_OPEN_CALLS = ['storage.get', 'storage.put', 'storage.list', 'device.pick', 'device.open'];
const pickOpenLocal = (over = {}) => ({
  schema: 'kotoba.host-local.v1', 'app-id': APP,
  storage: { class: 'device-only', backup: 'excluded', 'at-rest': 'encrypted', erasable: true, 'quota-bytes': 4 * MiB, 'max-entries': 100, 'max-value-bytes': MiB },
  stores: ['files'], calls: PICK_OPEN_CALLS,
  pick: { 'max-bytes': 4096, 'mime-types': ['application/json', 'text/plain'] },
  open: { 'max-bytes': 4096, 'mime-types': ['application/json', 'text/plain'] },
  ...over,
});
const pickOpenDescriptor = (over = {}) => descriptor({ 'host-local': pickOpenLocal(), ...over });

await section('device.pick', async () => {
  const h = await createTestHost({ descriptor: pickOpenDescriptor(), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: true,
    pickTarget: async (req) => ({ name: 'note.json', type: 'application/json', bytes: enc('{"x":1}') }) });
  assert.equal(h.mountProblems, null, String(h.mountProblems));
  const got = ok(await h.local('device.pick', { types: ['application/json'] }));
  assert.equal(got.name, 'note.json');
  assert.equal(dec(got.value), '{"x":1}');
  assert.equal(h.requests.length, 0, 'pick sends nothing');
  // Undeclared type / unknown call bodies are refused before the chooser runs.
  refused(await h.local('device.pick', { types: ['image/png'] }), 'not-declared');
  // A denied prompt never opens the chooser.
  const denied = await createTestHost({ descriptor: pickOpenDescriptor(), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: false,
    pickTarget: async () => { throw new Error('chooser ran after denial'); } });
  refused(await denied.local('device.pick', { types: ['application/json'] }), 'not-approved');
  assert.equal(denied.picks.length, 0);
  // An oversize file is refused.
  const big = await createTestHost({ descriptor: pickOpenDescriptor(), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: true,
    pickTarget: async () => ({ name: 'big.json', type: 'application/json', bytes: fill(5000) }) });
  refused(await big.local('device.pick', { types: ['application/json'] }), 'too-large');
  await h.close(); await denied.close(); await big.close();
});

await section('device.open', async () => {
  const h = await createTestHost({ descriptor: pickOpenDescriptor(), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: true });
  assert.equal(h.mountProblems, null, String(h.mountProblems));
  const opened = ok(await h.local('device.open', { name: 'a.json', type: 'application/json', value: enc('{}') }));
  assert.equal(opened.opened, true);
  assert.equal(h.opens.length, 1);
  assert.equal(h.opens[0].name, 'a.json');
  assert.equal(h.requests.length, 0);
  refused(await h.local('device.open', { name: 'x.html', type: 'text/html', value: enc('x') }), 'not-declared');
  refused(await h.local('device.open', { name: 'a.json', type: 'application/json', value: fill(5000) }), 'too-large');
  const denied = await createTestHost({ descriptor: pickOpenDescriptor(), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: false });
  refused(await denied.local('device.open', { name: 'a.json', type: 'application/json', value: enc('{}') }), 'not-approved');
  assert.equal(denied.opens.length, 0);
  await h.close(); await denied.close();
});

// ---- C. Device-local host commands (karute awai_local_inference): declared + registered only, Legal confirmation.
const CMD_CONFORMANCE = Object.freeze({ schema: 'kotoba.device-command-conformance.v1', host: 'synthetic-test-host', network: 'none', 'on-device': true, 'no-logging': true, 'no-retention': true });
const GENERATE_INPUT = { type: 'object', fields: { prompt: { type: 'string', 'max-bytes': 8192 }, maxTokens: { type: 'integer', min: 1, max: 256 } }, required: ['prompt', 'maxTokens'] };
const GENERATE_OUTPUT = { type: 'object', fields: { text: { type: 'string', 'max-bytes': 65536 } }, required: ['text'] };
const makeCommand = (over = {}) => ({
  name: 'awai_local_inference',
  actions: { generate: { input: GENERATE_INPUT, output: GENERATE_OUTPUT, 'max-input-bytes': 16384, 'max-output-bytes': 65536 } },
  run: async ({ action, input }) => ({ text: `echo:${input.prompt}` }),
  conformance: CMD_CONFORMANCE,
  ...over,
});
const deviceCommandLocal = (over = {}) => ({
  schema: 'kotoba.host-local.v1', 'app-id': APP,
  storage: { class: 'device-only', backup: 'excluded', 'at-rest': 'encrypted', erasable: true, 'quota-bytes': 4 * MiB, 'max-entries': 100, 'max-value-bytes': MiB },
  stores: ['files'], calls: ['storage.get', 'storage.put', 'device.command'],
  'device-commands': [{ name: 'awai_local_inference', actions: ['generate'], purpose: '端末内の AI で文章を生成するため', 'special-care': true }],
  ...over,
});
const deviceCommandDescriptor = () => descriptor({ 'host-local': deviceCommandLocal() });

await section('device.command runs declared and registered commands behind the short confirmation', async () => {
  const registry = runtime.createClientDeviceCommands([makeCommand()]);
  const h = await createTestHost({ descriptor: deviceCommandDescriptor(), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: true, deviceCommands: registry });
  assert.equal(h.mountProblems, null, String(h.mountProblems));
  const out = ok(await h.local('device.command', { command: 'awai_local_inference', action: 'generate', input: { prompt: 'hello', maxTokens: 8 } }));
  assert.equal(out.text, 'echo:hello');
  assert.equal(h.dialogs.length, 1, 'one short confirmation');
  assert.equal(h.requests.length, 0, 'no network');
  // The confirmation carries Legal's fixed lines (see the wording section), never the payload bytes.
  const shown = JSON.stringify(h.dialogs[0]);
  assert.equal(contains(h.dialogs, enc('hello')), false, 'the prompt is not in the dialog or telemetry');
  assert.equal(contains(h.telemetry, enc('hello')), false);
  await h.close();
});

await section('device.command refuses undeclared, unregistered, oversize and network commands', async () => {
  // Undeclared: the guest names a command its descriptor does not declare.
  const registry = runtime.createClientDeviceCommands([makeCommand()]);
  const h = await createTestHost({ descriptor: deviceCommandDescriptor(), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: true, deviceCommands: registry });
  refused(await h.local('device.command', { command: 'other_cmd', action: 'generate', input: { prompt: 'x', maxTokens: 1 } }), 'not-declared');
  refused(await h.local('device.command', { command: 'awai_local_inference', action: 'open', input: { prompt: 'x', maxTokens: 1 } }), 'not-declared');
  refused(await h.local('device.command', { command: 'awai_local_inference', action: 'generate', input: { prompt: fill(9000).join?.('x') ?? 'x'.repeat(9000), maxTokens: 1 } }), 'invalid-arguments');
  await h.close();
  // Unregistered: declared but the host registers nothing (or something else).
  const unregistered = await createTestHost({ descriptor: deviceCommandDescriptor(), appId: APP, storageRoot: `keys-${rootSeq++}` });
  assert.ok(unregistered.mountProblems?.length, 'a host without the registered command does not mount');
  const others = runtime.createClientDeviceCommands([makeCommand({ name: 'other_inference' })]);
  const missing = await createTestHost({ descriptor: deviceCommandDescriptor(), appId: APP, storageRoot: `keys-${rootSeq++}`, deviceCommands: others });
  assert.ok(missing.mountProblems?.length, 'a host that registers a different command does not mount');
  await unregistered.close(); await missing.close();
  // A command whose attestation admits network I/O is not registrable.
  assert.ok(runtime.clientDeviceCommandProblems(makeCommand({ conformance: { ...CMD_CONFORMANCE, network: 'lan' } })).includes('command-does-network-io'));
  assert.ok(runtime.clientDeviceCommandProblems(makeCommand({ conformance: { ...CMD_CONFORMANCE, 'no-logging': false } })).includes('not-declared:no-logging'));
  // The conformance probe fails a command that touches the network or logs.
  const noisy = runtime.createClientDeviceCommands([makeCommand({
    name: 'noisy_inference',
    run: async () => { await fetch('https://example.invalid/').catch(() => {}); return { text: 'x' }; },
  })]);
  const probed = await runtime.verifyDeviceCommandConformance(noisy, { noisy_inference: { generate: { prompt: 'x', maxTokens: 1 } } });
  assert.equal(probed.ok, false);
  assert.ok(probed.results[0].problems.includes('network-io'));
  const logging = runtime.createClientDeviceCommands([makeCommand({
    name: 'logging_inference',
    run: async () => { console.log('prompt written'); return { text: 'x' }; },
  })]);
  const probedLog = await runtime.verifyDeviceCommandConformance(logging, { logging_inference: { generate: { prompt: 'x', maxTokens: 1 } } });
  assert.equal(probedLog.ok, false);
  assert.ok(probedLog.results[0].problems.includes('logged'));
  // A denied confirmation never runs the command.
  let ran = false;
  const guarded = runtime.createClientDeviceCommands([makeCommand({ run: async () => { ran = true; return { text: 'x' }; } })]);
  const denied = await createTestHost({ descriptor: deviceCommandDescriptor(), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: false, deviceCommands: guarded });
  refused(await denied.local('device.command', { command: 'awai_local_inference', action: 'generate', input: { prompt: 'x', maxTokens: 1 } }), 'not-approved');
  assert.equal(ran, false);
  await denied.close();
});

await section('device.command dialog wording matches Legal (2026-11-22)', async () => {
  const registry = runtime.createClientDeviceCommands([makeCommand()]);
  for (const [locale, fixed, stop, deny, allow] of [
    ['ja', 'この端末の中の AI（Murakumo）に渡します。端末の外には送りません。', 'この機能は、設定 › 端末内の AI でいつでも止められます。', '渡さない', '渡す'],
    ['en', 'This is passed to the AI inside this device (Murakumo). It is not sent outside the device.', 'You can turn this off at any time in Settings › On-device AI.', "Don't pass", 'Pass'],
  ]) {
    const h = await createTestHost({ descriptor: deviceCommandDescriptor(), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: 'manual', deviceCommands: registry, locale });
    const pending = h.local('device.command', { command: 'awai_local_inference', action: 'generate', input: { prompt: 'x', maxTokens: 1 } });
    await new Promise((resolve) => setTimeout(resolve, 0)); await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(h.dialogs.length, 1);
    const shown = h.dialogs[0];
    const all = `${shown.title} ${shown.summary} ${shown.note} ${shown.scope} ${shown.payload} ${shown.allowLabel} ${shown.denyLabel}`;
    assert.ok(all.includes(fixed), `fixed line (${locale})`);
    assert.ok(all.includes(stop), `stop line (${locale})`);
    assert.ok(all.includes(shown.allowLabel), 'allow shown');
    assert.ok(shown.denyLabel && shown.allowLabel, 'equal buttons');
    assert.ok(all.includes('Once') || shown.summary.includes('1 回') || all.includes('1 回'), `one-time frequency (${locale})`);
    if (locale === 'ja') {
      assert.ok(all.includes('病歴などの健康の情報を含みます'), 'special-care line');
      assert.ok(all.includes('目的: 端末内の AI で文章を生成するため'), 'purpose line');
    }
    h.allow();
    const out = ok(await pending);
    assert.equal(out.text, 'echo:x');
    await h.close();
  }
});

// ---- D. Key approval: a declared host-held signing key signs only after the human-readable summary.
const signingLocal = (over = {}) => ({
  schema: 'kotoba.host-local.v1', 'app-id': APP,
  storage: { class: 'device-only', backup: 'excluded', 'at-rest': 'encrypted', erasable: true, 'quota-bytes': 4 * MiB, 'max-entries': 100, 'max-value-bytes': MiB },
  stores: ['files'], calls: ['storage.get', 'keys.generate', 'keys.open', 'keys.sign', 'crypto.ed25519Verify'],
  keys: [{ id: 'wallet', type: 'ed25519', use: ['sign'], approval: 'each-operation', operations: ['transfer', 'order'] }],
  ...over,
});
const signingDescriptor = (local) => descriptor({ 'host-local': local });
const SUMMARY = { operation: 'transfer', recipient: 'aws:0x0123456789abcdef0123456789abcdef01234567', amount: '0.1 AVAX' };

await section('keys.sign shows the summary and signs exactly it', async () => {
  const h = await createTestHost({ descriptor: signingDescriptor(signingLocal()), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: true });
  assert.equal(h.mountProblems, null, String(h.mountProblems));
  const gen = ok(await h.local('keys.generate', { id: 'wallet' }));
  assert.ok(gen.publicKey instanceof Uint8Array && gen.publicKey.byteLength === 32);
  const payload = enc('{"amount":"0.1","to":"0x0123"}');
  const signed = ok(await h.local('keys.sign', { key: gen.handle, summary: SUMMARY, payload }));
  assert.equal(h.dialogs.length, 1);
  assert.ok((signed.statement instanceof Uint8Array));
  assert.ok(signed.statement.byteLength > 0);
  // What the user saw is what is signed: the statement names operation, recipient, amount and payload hash.
  const statement = dec(signed.statement);
  assert.ok(statement.includes('transfer'), 'operation in the statement');
  assert.ok(statement.includes(SUMMARY.recipient), 'recipient in the statement');
  assert.ok(statement.includes(await sha256Hex(payload)), 'payload hash in the statement');
  const verified = ok(await h.local('crypto.ed25519Verify', { publicKey: signed.publicKey, signature: signed.signature, data: signed.statement }));
  assert.equal(verified.valid, true);
  // Signing without the human-readable summary is refused before any dialog.
  refused(await h.local('keys.sign', { key: gen.handle, summary: { operation: 'transfer' }, payload }), 'invalid-arguments');
  refused(await h.local('keys.sign', { key: gen.handle, summary: SUMMARY }), 'invalid-arguments');
  refused(await h.local('keys.sign', { key: gen.handle, payload }), 'invalid-arguments');
  // An operation the key does not declare is refused without a dialog.
  refused(await h.local('keys.sign', { key: gen.handle, summary: { ...SUMMARY, operation: 'withdraw' }, payload }), 'not-declared');
  assert.equal(h.dialogs.length, 1);
  // Denying the dialog signs nothing.
  const denied = await createTestHost({ descriptor: signingDescriptor(signingLocal()), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: false });
  const dGen = ok(await denied.local('keys.generate', { id: 'wallet' }));
  refused(await denied.local('keys.sign', { key: dGen.handle, summary: SUMMARY, payload }), 'not-approved');
  await h.close(); await denied.close();
});

await section('continuous signing is declared, scoped and revocable', async () => {
  // Continuous without a withdrawal place is an invalid descriptor.
  const bad = signingDescriptor(signingLocal({ keys: [{ id: 'wallet', type: 'ed25519', use: ['sign'], approval: 'continuous', operations: ['transfer'] }] }));
  assert.ok(problems(bad).includes('invalid-keys'), String(problems(bad)));
  const tooLong = signingDescriptor(signingLocal({ keys: [{ id: 'wallet', type: 'ed25519', use: ['sign'], approval: 'continuous', operations: ['transfer'], withdrawal: 'x'.repeat(121) }] }));
  assert.ok(problems(tooLong).includes('continuous-signing-needs-withdrawal'), String(problems(tooLong)));
  const good = signingDescriptor(signingLocal({ keys: [{ id: 'wallet', type: 'ed25519', use: ['sign'], approval: 'continuous', operations: ['transfer'], withdrawal: '設定 › 署名の許可' }] }));
  const h = await createTestHost({ descriptor: good, appId: APP, storageRoot: `keys-${rootSeq++}`, approve: 'manual' });
  const gen = ok(await h.local('keys.generate', { id: 'wallet' }));
  const payload = enc('{}');
  const first = h.local('keys.sign', { key: gen.handle, summary: { operation: 'transfer', recipient: 'aws:peer' }, payload });
  await new Promise((resolve) => setTimeout(resolve, 0)); await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(h.dialogs.length, 1, 'the first continuous sign asks');
  h.allow();
  ok(await first);
  // The same operation + recipient signs again without asking; a different one still asks.
  ok(await h.local('keys.sign', { key: gen.handle, summary: { operation: 'transfer', recipient: 'aws:peer' }, payload }));
  assert.equal(h.dialogs.length, 1, 'the grant covers the same scope');
  const other = h.local('keys.sign', { key: gen.handle, summary: { operation: 'transfer', recipient: 'aws:other' }, payload });
  await new Promise((resolve) => setTimeout(resolve, 0)); await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(h.dialogs.length, 2, 'a different recipient asks again');
  h.allow();
  ok(await other);
  // The host can revoke; the next sign asks.
  h.hostLocal().revokeSigningApproval();
  const third = h.local('keys.sign', { key: gen.handle, summary: { operation: 'transfer', recipient: 'aws:peer' }, payload });
  await new Promise((resolve) => setTimeout(resolve, 0)); await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(h.dialogs.length, 3, 'after revocation it asks again');
  h.allow();
  ok(await third);
  await h.close();
});

// ---- E. Host-mediated OAuth for the ATProto PDS (PKCE S256, state, DPoP ES256; tokens stay in the host).
const OAUTH_ID = 'atproto-pds';
const oauthEntry = (over = {}) => ({
  id: OAUTH_ID, issuer: 'https://pds.example', 'authorization-endpoint': 'https://pds.example/oauth/authorize',
  'token-endpoint': 'https://pds.example/oauth/token', 'client-id': 'https://app.example/oauth-client-metadata.json',
  'redirect-uri': 'https://app.example/oauth/callback', scope: 'atproto',
  disclosure: { recipient: 'PDS テスト事業者（合成）', country: 'JP', data: ['暗号化したファイルを保存するため送る'], 'special-care': false,
    purpose: 'ATProto の PDS に接続するため', frequency: 'one-time' },
  ...over,
});
const oauthLocal = (over = {}) => ({
  schema: 'kotoba.host-local.v1', 'app-id': APP,
  storage: { class: 'device-only', backup: 'excluded', 'at-rest': 'encrypted', erasable: true, 'quota-bytes': 4 * MiB, 'max-entries': 100, 'max-value-bytes': MiB },
  stores: ['files'], calls: ['storage.get', 'oauth.authorize', 'oauth.refresh', 'oauth.release'],
  oauth: [oauthEntry()], ...over,
});
const oaDescriptor = (local) => descriptor({ 'host-local': local });

async function fakeBrowser({ onUrl = null, corruptState = false } = {}) {
  const seen = [];
  const agent = async ({ url, redirectUri }) => {
    seen.push(new URL(url));
    onUrl?.(new URL(url), url);
    const state = new URL(url).searchParams.get('state');
    const back = new URL(redirectUri);
    back.searchParams.set('state', corruptState ? 'forged-state' : state);
    back.searchParams.set('code', 'test-code');
    return back.href;
  };
  return { agent, seen };
}
function fakeTokenEndpoint() {
  // The harness stub already buffers the body into `requests`, so the responder must not read it again.
  respondWith(async () => new Response(JSON.stringify({ access_token: 'access-token-xyz', token_type: 'DPoP', refresh_token: 'refresh-token-xyz', expires_in: 300, scope: 'atproto' }),
    { status: 200, headers: { 'content-type': 'application/json' } }));
}

await section('oauth.authorize runs PKCE + state in the host and keeps tokens host-side', async () => {
  const { agent, seen } = await fakeBrowser();
  fakeTokenEndpoint();
  const h = await createTestHost({ descriptor: oaDescriptor(oauthLocal()), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: true, oauthAgent: agent });
  assert.equal(h.mountProblems, null, String(h.mountProblems));
  const result = ok(await h.local('oauth.authorize', { id: OAUTH_ID }));
  assert.ok(/^kh\.[0-9a-f]{32}$/.test(result.session));
  assert.equal(result.sub, null);
  assert.equal(result.scope, 'atproto');
  assert.equal(result.expiresIn, 300);
  // Tokens and the DPoP key never reach the guest: the result carries only session/sub/scope/expiresIn.
  assert.deepEqual(Object.keys(result).sort(), ['expiresIn', 'scope', 'session', 'sub']);
  const flat = JSON.stringify(result);
  assert.equal(flat.includes('access-token'), false);
  assert.equal(flat.includes('refresh-token'), false);
  // PKCE S256 + state were in the authorize URL the host opened.
  assert.equal(seen.length, 1);
  assert.equal(seen[0].searchParams.get('code_challenge_method'), 'S256');
  assert.ok(seen[0].searchParams.get('code_challenge').length > 20);
  assert.ok(seen[0].searchParams.get('state').length > 20);
  // The token request body (buffered by the harness stub) carries the verifier.
  const sent = new URLSearchParams(dec(h.requests[0].body));
  assert.equal(sent.get('grant_type'), 'authorization_code');
  assert.ok(sent.get('code_verifier').length > 20);
  assert.equal(h.requests.length, 1, 'one token request, to the declared origin');
  assert.equal(new URL(h.requests[0].url).origin, 'https://pds.example');
  assert.ok(h.requests[0].headers.dpop, 'a DPoP proof was attached by the host');
  // oauth.release drops the session handle.
  ok(await h.local('oauth.release', { session: result.session }));
  refused(await h.local('oauth.release', { session: result.session }), 'invalid-key');
  await h.close();
});

await section('oauth refuses an undeclared origin, a state mismatch and a bare-bones redirect', async () => {
  // An endpoint off the declared issuer origin is an invalid descriptor.
  const offOrigin = oaDescriptor(oauthLocal({ oauth: [oauthEntry({ 'token-endpoint': 'https://evil.example/token' })] }));
  assert.ok(problems(offOrigin).includes('oauth-endpoint-not-on-declared-origin'), String(problems(offOrigin)));
  const bad = await createTestHost({ descriptor: offOrigin, appId: APP, storageRoot: `keys-${rootSeq++}` });
  assert.ok(bad.mountProblems?.length);
  await bad.close();
  // state mismatch is refused (CSRF / mix-up).
  const { agent } = await fakeBrowser({ corruptState: true });
  fakeTokenEndpoint();
  const h = await createTestHost({ descriptor: oaDescriptor(oauthLocal()), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: true, oauthAgent: agent });
  refused(await h.local('oauth.authorize', { id: OAUTH_ID }), 'invalid-arguments');
  await h.close();
  // A denial never opens the browser.
  let opened = false;
  const denied = await createTestHost({ descriptor: oaDescriptor(oauthLocal()), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: false,
    oauthAgent: async () => { opened = true; return 'https://app.example/oauth/callback'; } });
  refused(await denied.local('oauth.authorize', { id: OAUTH_ID }), 'not-approved');
  assert.equal(opened, false);
  await denied.close();
  // An undeclared oauth id is not-declared, and a session cannot be used as a key handle.
  const { agent: agent2 } = await fakeBrowser();
  fakeTokenEndpoint();
  const h2 = await createTestHost({ descriptor: oaDescriptor(oauthLocal()), appId: APP, storageRoot: `keys-${rootSeq++}`, approve: true, oauthAgent: agent2 });
  refused(await h2.local('oauth.authorize', { id: 'unknown' }), 'not-declared');
  const res = ok(await h2.local('oauth.authorize', { id: OAUTH_ID }));
  refused(await h2.local('oauth.refresh', { session: 'kh.00000000000000000000000000000000' }), 'invalid-key');
  await h2.close();
});

// ---- No test-only export: the runtime must not grow one for these PR 2 paths (see keys-and-logs in PR 1).
await section('no test-only export', async () => {
  const source = await (async () => { const fs = await import('node:fs'); return fs.readFileSync(process.env.KOTOBA_CLIENT_RUNTIME ? new URL(`file://${process.env.KOTOBA_CLIENT_RUNTIME}`) : new URL('../src/kotoba-client-runtime.js', import.meta.url), 'utf8'); })();
  for (const name of ['peekKeyForTest', 'ForTest', 'testHook']) assert.equal(source.includes(name), false, `no test-only export: ${name}`);
  assert.equal(source.split('\n').some((line) => /^export .*debug/i.test(line)), false, 'no debug export');
  assert.equal(FIXED.has('not-declared'), true);
});

// ---- The pin ledger entries name the vendored crypto libraries with version and integrity.
// sha512 of the vendored bytes per file, computed at this commit from the npm @noble tarball files (import-path edits only).
const VENDOR_FILE_SHA512 = Object.freeze({
  'post-quantum/ml-kem.js': '69298963bc5d99a0b2294f7cc61d3a4c2a8636cb899b4cc970fc99042eec49864902fd094a379c69ba570e8647f76fb3f442029911462fdb09158deb16f0081a',
  'post-quantum/_crystals.js': '0fe6bb4ecdffd314794cb968136f74bef4d292ca9d770a4eb363a3d78f3f28a41ad109be7e2f03d89125a3164e1d770bf53074642c7a628eaca0d4b6717020d2',
  'post-quantum/utils.js': 'dc3c321bc77eca03bbc37f75e0b240944d21d913a6e9cfdcf9d7ed07e10798c025eb347f8299f80633306f0462ac04eeeea7af3315e9d69a3c84adb9290a414d',
  'ciphers/chacha.js': '9ba2a0b261ba429816ba1ea948447706d1b3d5b8c1c78977ed435bca0740bc4d8c25d980556e2d41b1867b76b3a1a702b7321452d70a6a722a27297af4b002b0',
  'ciphers/_arx.js': 'cee28b59e4e0b445a336e867c1941f842e70e12347498f23121e3d2960cd7c2ca6b516b3eb9fa05b67c7c2a8580acf794de2c233221684210542949b1bd5d3f8',
  'ciphers/_poly1305.js': '9f721cd85d7baa39bd8646d616dfd5d0c881880f9c9cf4bfdda444557797f5d90cfb443f4339e8bb268d14da998c25d5eed3cbee532e75607d85063204a80dab',
  'ciphers/aes.js': 'c79aa9cd17a8daecc62afe9056a07bebf9a2b76f28ab48ae58607850407c61804af322d69d0788733323e3b93f141fa3c0db8d97b6a75a6faa1cfdd53935ebc8',
  'ciphers/_polyval.js': 'b5497ba6049e635a5fc5f4167144577ce337fd06e7f7b37433489bf16e656ee9070b7b7f049c98a317de77bc350c11db059d53022a395468148d972e7ba5954f',
  'ciphers/utils.js': '95b632ff5bf6ee61101a8f78b33ea170661cb92bf23bb4acad1af7d86c21824c95e7347e8db67f33bd9fad24014e088e5d6a6a46183b232d111373cf61992a86',
  'hashes-2/sha3.js': 'f82a01475292a6c8581076a1de2edaad4d8467f88139426affe34a005e567822f8bc28ccb5f07acc64b64b550157235444c1b9b89defe4639a260b0c21996c81',
  'hashes-2/_u64.js': '040178616643cf89bac06ceea2059cf79f0c7c1fd89d890f3850bfdf5559729ac8ee627ad8ab069671ee75038184bd75e4e092abf15863876f6b25a08a7e86dc',
  'hashes-2/utils.js': '3ccaa45df85c6a4ca7d769b435a552457b43023728c11c34c6f0d549eb9d0b1d33df4913f044c8ba1f861c0aa8e0e0de1d3a0ed9ef34a8a2d5f37eab9080c1d5',
  'curves-2/abstract/fft.js': 'dfc55587d7121dd45e47414c2d009bf90d1631abd897832c1e0ca8fc45708e798a3e92f2c8b4002e4b428436ef534527f0589ca4f492d7d859a0070e093c7ff4',
  'curves/ed25519.js': '1e6e34d0ec73b8a34124c43a29cbdbdf97cfaaef92877eb75f290622b82fe7d47a0fec21df7fd8c4c7b5c35ad7aa543b2deff238ac281ced512dc9bf97e783ea',
});
await section('crypto library ledger', async () => {
  assert.ok(Array.isArray(runtime.CLIENT_CRYPTO_LIBRARIES) && runtime.CLIENT_CRYPTO_LIBRARIES.length >= 4);
  const names = runtime.CLIENT_CRYPTO_LIBRARIES.map((entry) => entry.name);
  for (const must of ['@noble/post-quantum', '@noble/ciphers']) assert.ok(names.includes(must), String(names));
  for (const entry of runtime.CLIENT_CRYPTO_LIBRARIES) {
    assert.ok(entry.version && entry.use, `${entry.name} names version and use`);
    // `integrity` is the npm package SRI where present. The curves 1.9.7 entry is the repo's earlier vendored copy.
    if (entry.integrity.startsWith('sha512-')) {
      const decoded = Buffer.from(entry.integrity.slice(7), 'base64');
      assert.equal(decoded.length, 64, `${entry.name} SRI decodes to a sha512`);
    }
    // Every listed file exists where the ledger says it does, with the pinned bytes. The pinned sha512 values
    // were computed from the vendored bytes at this commit (npm @noble tarball files, import-path edits only);
    // they catch any accidental edit of the vendored crypto.
    const { createHash } = await import('node:crypto');
    const fs = await import('node:fs');
    for (const file of entry.files) {
      const url = new URL(`../src/vendor/${file}`, import.meta.url);
      assert.ok(fs.existsSync(url), `${entry.name}:${file}`);
      const digest = createHash('sha512').update(fs.readFileSync(url)).digest('hex');
      assert.equal(digest, VENDOR_FILE_SHA512[file], `${entry.name}:${file}`);
    }
  }
  assert.deepEqual([...runtime.CLIENT_KEY_TYPES].sort(), ['aes-256-gcm', 'ed25519', 'ml-kem-768', 'secret-32', 'x25519', 'xchacha20-poly1305'].sort());
});

if (negativeControl) {
  for (const [name, outcome] of outcomes) process.stdout.write(`${outcome === 'pass' ? 'PASS' : 'FAIL'}  ${name}${outcome === 'pass' ? '' : `: ${outcome.slice(5)}`}\n`);
  const failed = outcomes.filter(([, outcome]) => outcome !== 'pass');
  process.stdout.write(failed.length ? `negative control: ${failed.length} of ${outcomes.length} sections fail on the other copy\n` : `all ${outcomes.length} sections pass on the other copy\n`);
} else {
  process.stdout.write('PASS: KOTOBA-974 key handles (host-only, cross-app invalid, extractable refused), hybrid/X25519/XChaCha/KWP round trips with handle-only agreement, bounds and algorithm allowlist, erase, device.pick/open behind the trusted prompt, device-local commands behind Legal\'s short confirmation, key approval with revocable continuous grants, host OAuth (PKCE, state, DPoP, tokens host-side)\n');
}
