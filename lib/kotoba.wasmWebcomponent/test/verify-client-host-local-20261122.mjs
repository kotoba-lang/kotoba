// KOTOBA-968 (KOTOBA-159 PR 1): host-local storage, declared binary/text bodies, device.save, device.openLink and
// constrained route templates.
// Each section is a negative control: it fails on the runtime at kotoba-lang/kotoba main e58ae70b4
// (sha256 37e82633…2d6d) and passes with this change. Fake DOM, stubbed fetch, in-memory storage; no network.
// KOTOBA_CLIENT_RUNTIME=<path> KOTOBA_NEGATIVE_CONTROL=1 reports each section against another copy.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { DISCLOSURE } from './client-runtime-fixtures.mjs';
import { runtime, createTestHost, respondWith, storageFor, memoryKv, admit, TEST_CONFORMANCE, harnessState } from './client-runtime-host-local-harness.mjs';

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
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const fill = (n, seed = 7) => { const b = new Uint8Array(n); for (let i = 0; i < n; i++) b[i] = (i * 31 + seed) & 255; return b; };
const APP = 'org.example.notes';
const hostLocal = (over = {}) => ({
  schema: 'kotoba.host-local.v1', 'app-id': APP,
  storage: { class: 'device-only', backup: 'excluded', 'at-rest': 'encrypted', erasable: true, 'quota-bytes': 4 * MiB, 'max-entries': 100, 'max-value-bytes': MiB },
  stores: ['files', 'vault'],
  calls: ['storage.get', 'storage.put', 'storage.delete', 'storage.list', 'storage.clear', 'storage.batch', 'storage.usage', 'storage.watch', 'device.save', 'device.openLink'],
  save: { 'max-bytes': 256 * 1024, 'mime-types': ['application/json', 'text/plain', 'application/octet-stream'], 'octet-stream-extensions': ['bs1', 'bs2', 'bs3'] },
  links: { 'max-url-length': 512, targets: [
    { origin: 'https://www.wikidata.org', path: '/wiki/:item', 'path-params': { item: { charset: 'alnum', 'min-length': 2, 'max-length': 16 } }, 'query-params': { uselang: { enum: ['ja', 'en'] } } },
    { origin: 'https://etherscan.io', path: '/' },
  ] },
  ...over,
});
const op = (operation, method, extra = {}) => ({
  capability: 'net/fetch', service: 'svc', operation, consent: 'each-operation', disclosure: DISCLOSURE, 'data-categories': ['x'],
  endpoint: { origin: 'https://svc.example', routes: [{ method, 'path-prefix': '/packs/', 'query-params': [] }] }, ...extra,
});
const descriptor = (over = {}, operations = [
  op('upload', 'PUT', { 'request-body': 'bytes', 'max-request-bytes': 2 * MiB, 'content-type': 'application/octet-stream', 'response-body': 'text', 'max-response-bytes': 4096 }),
  op('download', 'GET', { 'response-body': 'bytes', 'max-response-bytes': 2 * MiB }),
]) => ({
  schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile: 'restricted-wasm-v1', entry: 'index.html',
  'local-state': { adapter: 'memory', schema: 's', version: 1 }, operations, 'host-local': hostLocal(), ...over,
});
const problems = (d) => runtime.clientRuntimeProblems(d, ['net/fetch'], 'http://tauri.localhost').map((p) => p.error);
let rootSeq = 0;
const host = (opts = {}) => createTestHost({ descriptor: descriptor(), appId: APP, storageRoot: `root-${rootSeq++}`, ...opts });
const ok = (r) => { assert.equal(r.ok, true, `expected ok, got ${JSON.stringify(r).slice(0, 160)}`); return r.result; };
const refused = (r, code) => { assert.equal(r.ok, false, JSON.stringify(r).slice(0, 160)); assert.equal(r.error, code); };

// ---- Cross-app read: one backend, two app ids; neither can read, list or decrypt the other's data.
await section('cross-app read', async () => {
  const root = `shared-${rootSeq++}`;
  const a = await createTestHost({ descriptor: descriptor(), appId: APP, storageRoot: root });
  const otherId = 'org.example.other';
  const b = await createTestHost({ descriptor: descriptor({ 'host-local': hostLocal({ 'app-id': otherId }) }), appId: otherId, storageRoot: root });
  assert.equal(a.mountProblems, null, String(a.mountProblems));
  ok(await a.local('storage.put', { store: 'files', key: 'secret.txt', value: enc('only A') }));
  assert.equal(ok(await b.local('storage.get', { store: 'files', key: 'secret.txt' })), null);
  assert.deepEqual(ok(await b.local('storage.list', { store: 'files' })).entries, []);
  for (const key of ['../org.example.notes/files/secret.txt', '/secret.txt', 'a\\b', 'a\u0000b', 'a/../../b', 'a//b', '.', 'x\u202e']) {
    refused(await b.local('storage.get', { store: 'files', key }), 'invalid-key');
  }
  // A guest cannot name the partition: an app id the host does not hold is not mounted.
  const wrong = await createTestHost({ descriptor: descriptor(), appId: 'org.example.someone-else', storageRoot: root });
  assert.match(String(wrong.mountProblems), /not the host app id/);
  // At rest a record is bound to its partition: A's records copied under B's partition do not decrypt.
  const { kv, backend } = storageFor(root);
  ok(await b.local('storage.put', { store: 'files', key: 'mine.txt', value: enc('B') }));
  for (const [name, value] of [...kv.raw.entries()].filter(([k]) => /^[md]\u0000/.test(k) && k.includes(APP))) kv.raw.set(name.replace(APP, otherId), value);
  await assert.rejects(() => backend.list(otherId), 'a copied record does not decrypt under another partition');
  for (const h of [a, b, wrong]) await h.close();
});

// ---- Egress: host-local calls make no request; a declaration cannot name a destination.
await section('no egress through storage', async () => {
  const h = await host();
  let fetched = 0; respondWith(() => { fetched += 1; return new Response(null, { status: 204 }); });
  ok(await h.local('storage.put', { store: 'files', key: 'a', value: enc('x') }));
  ok(await h.local('storage.get', { store: 'files', key: 'a' }));
  ok(await h.local('storage.batch', { ops: [{ delete: { store: 'files', key: 'a' } }] }));
  assert.equal(fetched + h.requests.length, 0, 'no fetch'); assert.equal(h.dialogs.length, 0, 'no dialog');
  for (const extra of [{ origin: 'https://svc.example' }, { endpoint: { origin: 'https://svc.example' } }, { url: 'https://svc.example/x' }, { transport: 'libp2p' }]) {
    assert.ok(problems(descriptor({ 'host-local': hostLocal(extra) })).includes('invalid-host-local-keys'), JSON.stringify(extra));
  }
  assert.ok(problems(descriptor({ 'host-local': hostLocal({ storage: { ...hostLocal().storage, endpoint: 'https://x.example' } }) })).includes('invalid-storage'));
  assert.ok(problems(descriptor({ 'host-local': hostLocal({ calls: ['storage.get', 'storage.*'] }) })).includes('invalid-calls'), 'no wildcard call');
  // Migration (App Build, 2026-11-22): a trusted-page-v1 app may declare host-local, and its host-document code
  // calls the handle directly to copy its IndexedDB data in before it moves to restricted-wasm-v1.
  assert.deepEqual(problems(descriptor({ profile: 'trusted-page-v1' })), []);
  const trusted = await admit(descriptor({ profile: 'trusted-page-v1' }));
  const direct = runtime.createClientHostLocal({ admitted: trusted, appId: APP, storage: storageFor(`tp-${rootSeq++}`).backend, consentHost: runtime.createClientConsentHost() });
  assert.deepEqual(await direct.call('storage.put', { store: 'files', key: 'migrated.json', value: enc('{}') }), { ok: true, result: { size: 2, version: 1 } });
  assert.equal(dec((await direct.call('storage.get', { store: 'files', key: 'migrated.json' })).result.value), '{}');
  assert.deepEqual(await direct.call('storage.get', { store: 'files', key: '../x' }), { ok: false, error: 'invalid-key' });
  // connect-src is unchanged by host-local: only the declared HTTP origin.
  assert.equal(runtime.clientRuntimeConnectSrc(descriptor(), ['net/fetch'], [], 'http://tauri.localhost'), 'connect-src https://svc.example');
  // Legal L1/L3/L4 at the declaration: only device-only, backup excluded, encrypted, erasable.
  for (const [k, v] of [['class', 'synced'], ['backup', 'included'], ['at-rest', 'plaintext'], ['erasable', false]]) {
    assert.ok(problems(descriptor({ 'host-local': hostLocal({ storage: { ...hostLocal().storage, [k]: v } }) })).includes('storage-must-be-device-only-excluded-encrypted-erasable'), k);
  }
  await h.close();
});

// ---- Size caps: values, quota, entries, the global caps, and declared HTTP bodies.
await section('size caps', async () => {
  const h = await host();
  refused(await h.local('storage.put', { store: 'files', key: 'big', value: fill(MiB + 1) }), 'too-large');
  for (let i = 0; i < 4; i++) ok(await h.local('storage.put', { store: 'files', key: `p${i}`, value: fill(MiB - 64) }));
  refused(await h.local('storage.put', { store: 'files', key: 'p5', value: fill(1024) }), 'quota-exceeded');
  const usage = ok(await h.local('storage.usage', {}));
  assert.ok(usage.bytes <= 4 * MiB && usage.entries === 4 && usage.quotaBytes === 4 * MiB, JSON.stringify(usage));
  const cap = runtime.CLIENT_PORT_BYTES_MAX;
  assert.equal(cap, 16 * MiB);
  assert.ok(problems(descriptor({ 'host-local': hostLocal({ storage: { ...hostLocal().storage, 'max-value-bytes': cap + 1 } }) })).includes('limit-over-global-cap'));
  assert.ok(problems(descriptor({ 'host-local': hostLocal({ storage: { ...hostLocal().storage, 'quota-bytes': runtime.CLIENT_STORAGE_QUOTA_MAX + 1 } }) })).includes('limit-over-global-cap'));
  assert.ok(problems(descriptor({ 'host-local': hostLocal({ save: { ...hostLocal().save, 'max-bytes': cap + 1 } }) })).includes('limit-over-global-cap'));
  assert.ok(problems(descriptor({}, [op('download', 'GET', { 'response-body': 'bytes', 'max-response-bytes': cap + 1 })])).includes('bytes-limit-over-global-cap'));
  assert.ok(problems(descriptor({}, [op('upload', 'PUT', { 'request-body': 'bytes', 'max-request-bytes': cap + 1 })])).includes('bytes-limit-over-global-cap'));
  assert.ok(problems(descriptor({}, [op('upload', 'PUT', { 'request-body': 'bytes' })])).includes('invalid-body-declaration'), 'a body kind needs its limit');
  assert.ok(problems(descriptor({}, [{ ...op('x', 'GET'), endpoint: { origin: 'https://svc.example', 'browser-action': 'share' }, 'response-body': 'bytes', 'max-response-bytes': 10 }])).includes('body-declaration-requires-http-endpoint'));
  await h.close();
  // A request body over max-request-bytes is refused before consent; nothing is fetched.
  const up = await host({ approve: true });
  const sel = { capability: 'net/fetch', service: 'svc', operation: 'upload' };
  const r = await up.operation(sel, { input: 'https://svc.example/packs/a', init: { method: 'PUT', body: fill(2 * MiB + 1) } });
  assert.equal(r.ok, false); assert.equal(up.dialogs.length, 0); assert.equal(up.requests.length, 0);
  // A wrong content type is refused before consent.
  const wrongType = await up.operation(sel, { input: 'https://svc.example/packs/a', init: { method: 'PUT', headers: { 'content-type': 'text/html' }, body: fill(10) } });
  assert.equal(wrongType.ok, false); assert.equal(up.dialogs.length, 0);
  // A response over max-response-bytes: refused by Content-Length before reading, or cancelled while streaming.
  const down = { capability: 'net/fetch', service: 'svc', operation: 'download' };
  let read = false;
  respondWith(() => new Response(new ReadableStream({ pull(c) { read = true; c.enqueue(fill(1024)); c.close(); } }, { highWaterMark: 0 }), { status: 200, headers: { 'content-length': String(2 * MiB + 1) } }));
  const declaredTooBig = await up.operation(down, { input: 'https://svc.example/packs/a' });
  assert.equal(declaredTooBig.ok, false); assert.match(declaredTooBig.error, /exceeds declared byte budget/);
  let cancelled = false;
  respondWith(() => new Response(new ReadableStream({ pull(c) { c.enqueue(fill(MiB)); }, cancel() { cancelled = true; } }), { status: 200 }));
  const streamedTooBig = await up.operation(down, { input: 'https://svc.example/packs/a' });
  assert.equal(streamedTooBig.ok, false); assert.equal(cancelled, true, 'stream cancelled at the limit');
  assert.equal(read, false, 'a declared oversize body is not read');
  await up.close();
});

// ---- Declared bodies: bytes both ways, exact; text bounded; the dialog shows the limits; R3 and redirects kept.
await section('binary bodies', async () => {
  const h = await host({ approve: true });
  const pack = fill(2 * MiB, 3);
  respondWith(() => new Response(JSON.stringify({ stored: true }), { status: 201, headers: { 'content-type': 'application/json' } }));
  const up = await h.operation({ capability: 'net/fetch', service: 'svc', operation: 'upload' }, { input: 'https://svc.example/packs/a', init: { method: 'PUT', body: pack } });
  assert.equal(up.ok, true, JSON.stringify(up).slice(0, 200)); assert.equal(up.content, '{"stored":true}');
  assert.deepEqual(h.requests[0].body, pack, 'request bytes unchanged');
  assert.equal(h.requests[0].headers['content-type'], 'application/octet-stream', 'the declared content type');
  assert.ok(h.dialogs[0].summary.includes('送る大きさの上限: 2 MiB（2097152 バイト）'), h.dialogs[0].summary);
  assert.ok(h.dialogs[0].summary.includes('受け取る大きさの上限: 4 KiB（4096 バイト）'));
  assert.ok(!h.dialogs[0].payload.includes(dec(pack.subarray(0, 32))), 'the dialog shows the size, not the bytes');
  const body = fill(MiB, 9);
  respondWith(() => new Response(body, { status: 206, headers: { 'content-type': 'application/warc', 'content-range': 'bytes 0-1048575/9999999' } }));
  const down = await h.operation({ capability: 'net/fetch', service: 'svc', operation: 'download' }, { input: 'https://svc.example/packs/b', init: { headers: { range: 'bytes=0-1048575' } } });
  assert.equal(down.ok, true); assert.ok(down.bytes instanceof Uint8Array); assert.deepEqual(down.bytes, body);
  assert.equal(down.status, 206); assert.equal(down.headers['content-range'], 'bytes 0-1048575/9999999');
  assert.equal(h.requests[1].headers.range, 'bytes=0-1048575');
  await h.close();
  // English wording of the limits.
  const en = await host({ approve: false, locale: 'en' });
  await en.operation({ capability: 'net/fetch', service: 'svc', operation: 'download' }, { input: 'https://svc.example/packs/c' });
  assert.ok(en.dialogs[0].summary.includes('Receives at most: 2 MiB (2097152 bytes)'), en.dialogs[0].summary);
  assert.ok(en.dialogs[0].scope.includes('Response body: bytes, at most 2097152 bytes'));
  await en.close();
  // R3 kept: while one operation awaits consent, a second is refused before its body is read.
  const r3 = await host({ approve: 'manual' });
  const first = r3.operation({ capability: 'net/fetch', service: 'svc', operation: 'upload' }, { input: 'https://svc.example/packs/a', init: { method: 'PUT', body: fill(100) } });
  await tick(); await tick();
  const second = await r3.operation({ capability: 'net/fetch', service: 'svc', operation: 'upload' }, { input: 'https://svc.example/packs/b', init: { method: 'PUT', body: fill(100) } });
  assert.equal(second.ok, false); assert.match(second.error, /awaiting consent/);
  r3.deny(); assert.equal((await first).ok, false); assert.equal(r3.requests.length, 0, 'denied: nothing sent');
  await r3.close();
});

// ---- Backend MUSTs (Legal): a host that does not declare them does not get storage; the helper checks behaviour.
await section('host conformance', async () => {
  const admitted = await admit(descriptor());
  const { conformance: _c, ...undeclared } = storageFor(`x-${rootSeq++}`).backend;
  assert.throws(() => runtime.createClientHostLocal({ admitted, appId: APP, storage: undeclared }), /not conformant: missing-conformance-declaration/);
  for (const must of ['no-cloud-backup', 'no-logging', 'user-clearable', 'removed-with-app']) {
    const backend = runtime.createEncryptedClientStorageBackend({ kv: memoryKv(), conformance: { ...TEST_CONFORMANCE, [must]: false } });
    assert.equal(runtime.clientStorageBackendProblems(backend)[0], `not-declared:${must}`);
  }
  // Review finding 2: no default declaration, and a key kept next to the data only where there is no OS backup.
  assert.throws(() => runtime.createEncryptedClientStorageBackend({ kv: memoryKv() }), /must supply its storage conformance/);
  assert.throws(() => runtime.createIndexedDbClientStorageBackend({ indexedDB: { open() { return {}; } } }), /must supply its storage conformance/);
  const backedUp = runtime.createEncryptedClientStorageBackend({ kv: memoryKv(), conformance: { ...TEST_CONFORMANCE, 'no-cloud-backup': true } });
  assert.deepEqual(runtime.clientStorageBackendProblems(backedUp), ['key-custody-requires-platform-keystore'], 'Tauri/Android: keys must come from the platform keystore');
  const keystore = new Map();
  const keyProvider = {
    async keys(partition, { create }) {
      if (!keystore.has(partition) && create) keystore.set(partition, { encryption: await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']), index: await crypto.subtle.generateKey({ name: 'HMAC', hash: 'SHA-256', length: 256 }, false, ['sign']) });
      return keystore.get(partition) ?? null;
    },
    async delete(partition) { keystore.delete(partition); },
  };
  const withKeystore = runtime.createEncryptedClientStorageBackend({ kv: memoryKv(), conformance: { ...TEST_CONFORMANCE, 'no-cloud-backup': true }, keyProvider });
  assert.deepEqual(runtime.clientStorageBackendProblems(withKeystore), []);
  assert.equal(withKeystore.conformance['key-custody'], 'platform-keystore');
  assert.equal((await runtime.verifyHostStorageConformance(withKeystore)).conformant, true);
  const extractable = runtime.createEncryptedClientStorageBackend({ kv: memoryKv(), conformance: { ...TEST_CONFORMANCE, 'no-cloud-backup': true },
    keyProvider: { async keys() { return { encryption: await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, true, ['encrypt', 'decrypt']), index: await crypto.subtle.generateKey({ name: 'HMAC', hash: 'SHA-256' }, true, ['sign']) }; }, async delete() {} } });
  await assert.rejects(() => extractable.batch('a.b', [{ put: { key: 'f/x', value: new Uint8Array(1) } }]), /unusable keys/, 'an extractable key is refused');
  const good = await runtime.verifyHostStorageConformance(storageFor(`y-${rootSeq++}`).backend);
  assert.equal(good.conformant, true, JSON.stringify(good.results));
  assert.ok(good.results.filter((r) => !r.verified).map((r) => r.case).includes('no-cloud-backup'), 'declared MUSTs are reported as not verified');
  // A backend that ignores the partition fails the helper.
  const leaky = { conformance: { schema: runtime.CLIENT_STORAGE_CONFORMANCE_SCHEMA, ...TEST_CONFORMANCE, 'encrypted-at-rest': true, 'encrypted-names': true, 'key-custody': 'host-profile' }, data: new Map(),
    async get(_p, key) { const v = this.data.get(key); return v ? { value: v, version: 1 } : null; }, async list() { return [...this.data].map(([key, v]) => ({ key, bytes: v.length, modified: 1, version: 1 })); },
    async batch(_p, ops) { const versions = {}; for (const o of ops) { if (o.put) { this.data.set(o.put.key, o.put.value); versions[o.put.key] = 1; } else { this.data.delete(o.delete.key); versions[o.delete.key] = 0; } } return { versions }; },
    async clear() { this.data.clear(); } };
  const bad = await runtime.verifyHostStorageConformance(leaky);
  assert.equal(bad.conformant, false);
  assert.equal(bad.results.find((r) => r.case === 'isolation-get').passed, false);
  assert.equal(bad.results.find((r) => r.case === 'compare-and-swap').passed, false, 'a backend without compare-and-swap fails');
  // A plain browser host declares no OS backup and may keep its keys in IndexedDB.
  const fakeIdb = { open() { return {}; } };
  assert.deepEqual(runtime.clientStorageBackendProblems(runtime.createIndexedDbClientStorageBackend({ indexedDB: fakeIdb, conformance: TEST_CONFORMANCE })), []);
});

// ---- Encrypted at rest; the per-app key cannot be extracted; nothing reaches logs or error messages (L2, L3).
await section('keys and logs', async () => {
  const root = `k-${rootSeq++}`;
  const h = await host({ storageRoot: root });
  const marker = 'MARKER-private-9c1e';
  ok(await h.local('storage.put', { store: 'vault', key: 'record', value: enc(`body ${marker}`) }));
  const { kv } = storageFor(root);
  const stored = [...kv.raw.entries()];
  const keys = stored.find(([k]) => k.startsWith('k\u0000'))[1];
  for (const key of [keys.encryption, keys.index]) {
    assert.equal(key.extractable, false, 'non-extractable');
    await assert.rejects(() => crypto.subtle.exportKey('raw', key), 'export is refused');
  }
  // Review finding 3: neither the value nor the key name is readable at rest, and sizes are padded to 4 KiB buckets.
  ok(await h.local('storage.put', { store: 'files', key: `notes/${marker}-file-name.txt`, value: fill(5000) }));
  const rawBytes = Buffer.concat([...kv.raw.entries()].flatMap(([k, v]) => [Buffer.from(k), ...(v?.data instanceof Uint8Array ? [Buffer.from(v.data)] : [])]));
  assert.ok(!rawBytes.includes(Buffer.from(marker)), 'no plaintext value or name at rest');
  for (const [k, v] of kv.raw.entries()) if (k.startsWith('d\u0000')) assert.equal((v.data.byteLength - 16) % 4096, 0, 'value sizes are bucketed');
  // Errors are fixed codes and never echo keys, values or names.
  const failing = runtime.createEncryptedClientStorageBackend({ kv: { ...memoryKv(), async update() { throw new Error(`disk full while writing ${marker}`); } }, conformance: TEST_CONFORMANCE });
  const f = await host({ storage: failing });
  const r = await f.local('storage.put', { store: 'files', key: `x/${marker}`, value: enc(marker) });
  refused(r, 'unavailable'); assert.ok(!JSON.stringify(r).includes(marker));
  const bad = await f.local('storage.put', { store: 'nope', key: marker, value: enc(marker) });
  refused(bad, 'not-declared'); assert.ok(!JSON.stringify(bad).includes(marker));
  assert.ok(!JSON.stringify(f.telemetry).includes(marker) && !JSON.stringify(h.telemetry).includes(marker), 'nothing logged');
  assert.equal(h.telemetry.length + f.telemetry.length, 0, 'the runtime writes nothing to the console');
  assert.ok(!/console\./.test(readFileSync(new URL(process.env.KOTOBA_CLIENT_RUNTIME ?? '../src/kotoba-client-runtime.js', import.meta.url), 'utf8')), 'no console call in the runtime');
  // No test-only export (for example a key peek) exists in the runtime.
  assert.deepEqual(Object.keys(runtime).filter((name) => /test|peek|debug/i.test(name)), []);
  await h.close(); await f.close();
});

// ---- Clear app data (L4): the guest's storage.clear, the host's clearAppData and clearClientAppData.
await section('clear app data', async () => {
  const root = `c-${rootSeq++}`;
  const a = await host({ storageRoot: root });
  const otherId = 'org.example.other';
  const b = await createTestHost({ descriptor: descriptor({ 'host-local': hostLocal({ 'app-id': otherId }) }), appId: otherId, storageRoot: root });
  ok(await a.local('storage.put', { store: 'files', key: 'a', value: enc('a') }));
  ok(await a.local('storage.put', { store: 'vault', key: 'v', value: enc('v') }));
  ok(await b.local('storage.put', { store: 'files', key: 'b', value: enc('b') }));
  ok(await a.local('storage.clear', { store: 'files' }));
  assert.deepEqual(ok(await a.local('storage.list', { store: 'files' })).entries, []);
  assert.equal(ok(await a.local('storage.list', { store: 'vault' })).entries.length, 1, 'clearing one store keeps the other');
  await a.clearAppData();
  assert.deepEqual(ok(await a.local('storage.list', { store: 'vault' })).entries, []);
  const { kv, backend } = storageFor(root);
  assert.ok(![...kv.raw.keys()].some((k) => k.includes(APP)), 'records and the app key are gone');
  assert.equal(dec(ok(await b.local('storage.get', { store: 'files', key: 'b' })).value), 'b', 'the other app is untouched');
  await runtime.clearClientAppData({ appId: otherId, storage: backend });
  assert.ok(![...kv.raw.keys()].some((k) => k.includes(otherId)), 'removing an app removes its data');
  await a.close(); await b.close();
});

// ---- Batch is all or nothing; compare-and-swap on versions; change notices carry key names only.
await section('batch, versions, watch', async () => {
  const root = `w-${rootSeq++}`;
  const h = await host({ storageRoot: root });
  ok(await h.local('storage.put', { store: 'files', key: 'keep', value: enc('old') }));
  refused(await h.local('storage.batch', { ops: [{ put: { store: 'files', key: 'keep', value: enc('new') } }, ...[1, 2, 3, 4].map((i) => ({ put: { store: 'files', key: `b${i}`, value: fill(MiB) } }))] }), 'quota-exceeded');
  assert.equal(dec(ok(await h.local('storage.get', { store: 'files', key: 'keep' })).value), 'old', 'nothing applied');
  refused(await h.local('storage.batch', { ops: [{ move: { from: ['files', 'missing'], to: ['vault', 'x'] } }] }), 'not-found');
  ok(await h.local('storage.batch', { ops: [{ put: { store: 'vault', key: 'stage', value: enc('A') } }, { move: { from: ['vault', 'stage'], to: ['files', 'a'] } }] }));
  assert.equal(dec(ok(await h.local('storage.get', { store: 'files', key: 'a' })).value), 'A');
  assert.equal(ok(await h.local('storage.get', { store: 'vault', key: 'stage' })), null);
  // Versions: get returns one; a put with a stale ifVersion is refused; ifVersion 0 means absent.
  const got = ok(await h.local('storage.get', { store: 'files', key: 'keep' }));
  assert.equal(got.version, 1);
  assert.equal(ok(await h.local('storage.put', { store: 'files', key: 'keep', value: enc('v2'), ifVersion: 1 })).version, 2);
  refused(await h.local('storage.put', { store: 'files', key: 'keep', value: enc('v3'), ifVersion: 1 }), 'version-conflict');
  refused(await h.local('storage.put', { store: 'files', key: 'keep', value: enc('v3'), ifVersion: 0 }), 'version-conflict');
  ok(await h.local('storage.put', { store: 'files', key: 'fresh', value: enc('n'), ifVersion: 0 }));
  refused(await h.local('storage.delete', { store: 'files', key: 'keep', ifVersion: 1 }), 'version-conflict');
  refused(await h.local('storage.put', { store: 'files', key: 'fresh', value: enc('n'), ifAbsent: true }), 'key-exists');
  // Watch: a second mount of the same app sees which keys changed, never the value; another app sees nothing.
  const twin = await host({ storageRoot: root });
  const stranger = await createTestHost({ descriptor: descriptor({ 'host-local': hostLocal({ 'app-id': 'org.example.other' }) }), appId: 'org.example.other', storageRoot: root });
  ok(await twin.local('storage.watch', { store: 'files', prefix: 'doc' }));
  ok(await stranger.local('storage.watch', { store: 'files' }));
  ok(await h.local('storage.put', { store: 'files', key: 'doc/1', value: enc('SECRET-VALUE') }));
  ok(await h.local('storage.put', { store: 'files', key: 'other', value: enc('x') }));
  await tick();
  const events = twin.events();
  assert.deepEqual(events.map((e) => e.keys), [['doc/1']]);
  assert.equal(events[0].event, 'storage.changed'); assert.equal(events[0].store, 'files');
  assert.ok(!JSON.stringify(events).includes('SECRET-VALUE'), 'a notice never carries the value');
  assert.deepEqual(stranger.events(), [], 'another app gets no notice');
  // Pages: list with a limit returns a cursor.
  for (let i = 0; i < 5; i++) ok(await h.local('storage.put', { store: 'vault', key: `p/${i}`, value: enc(String(i)) }));
  const page = ok(await h.local('storage.list', { store: 'vault', prefix: 'p/', limit: 2 }));
  assert.deepEqual(page.entries.map((e) => e.key), ['p/0', 'p/1']); assert.equal(page.cursor, 'p/1');
  assert.deepEqual(ok(await h.local('storage.list', { store: 'vault', prefix: 'p/', cursor: page.cursor })).entries.map((e) => e.key), ['p/2', 'p/3', 'p/4']);
  const part = ok(await h.local('storage.get', { store: 'files', key: 'a', offset: 0, length: 0 }));
  assert.equal(part.value.byteLength, 0); assert.equal(part.size, 1);
  for (const x of [h, twin, stranger]) await x.close();
});

// ---- device.save: only after a trusted click on the host prompt; declared type and size; safe name; no log.
await section('device.save', async () => {
  const file = { name: 'report.json', type: 'application/json', value: enc('{"a":1}') };
  for (const mode of [false, 'synthetic', 'early']) {
    const h = await host({ approve: mode });
    refused(await h.local('device.save', file), 'not-approved');
    assert.equal(h.saves.length, 0, `no save: ${mode}`);
    await h.close();
  }
  const h = await host({ approve: true });
  assert.deepEqual(ok(await h.local('device.save', file)), { saved: true, name: 'report.json' });
  assert.equal(h.saves.length, 1); assert.deepEqual(h.saves[0].bytes, file.value);
  assert.ok(h.dialogs[0].title.includes('ファイルをこの端末に保存しようとしています'));
  assert.ok(h.dialogs[0].summary.includes('ファイル名: report.json'));
  assert.equal(h.dialogs[0].allowLabel, '保存する');
  assert.equal(h.dialogs[0].note, '保存先はこの端末です。この操作で、app が外部に何かを送ることはありません。', 'Legal 2026-11-22 save notice');
  refused(await h.local('device.save', { ...file, value: fill(256 * 1024 + 1) }), 'too-large');
  refused(await h.local('device.save', { ...file, type: 'text/html' }), 'not-declared');
  refused(await h.local('device.save', { ...file, type: 'text/csv' }), 'not-declared');
  for (const [name, type, expected] of [['../../etc/passwd.json', 'application/json', 'passwd.json'], ['C:\\Users\\x\\evil.json', 'application/json', 'evil.json'],
    ['evil.html', 'text/plain', 'evil.html.txt'], ['CON.json', 'application/json', '_CON.json'], ['...', 'application/json', 'download.json'],
    ['bunsho-backup.bs2', 'application/octet-stream', 'bunsho-backup.bs2'], ['payload.exe', 'application/octet-stream', 'payload.exe.bs1'], ['a\u202egnp.json', 'application/json', 'agnp.json']]) {
    assert.equal(runtime.clientSaveFileName(name, type, ['bs1', 'bs2', 'bs3']), expected, name);
  }
  assert.equal(ok(await h.local('device.save', { ...file, name: '../../x/../secret.json' })).name, 'secret.json');
  assert.ok(problems(descriptor({ 'host-local': hostLocal({ save: { 'max-bytes': 10, 'mime-types': ['application/octet-stream'], 'octet-stream-extensions': ['exe'] } }) })).includes('save-extension-not-allowed'));
  assert.ok(problems(descriptor({ 'host-local': hostLocal({ save: { 'max-bytes': 10, 'mime-types': ['text/html'] } }) })).includes('save-type-not-allowed'));
  assert.ok(problems(descriptor({ 'host-local': hostLocal({ save: { 'max-bytes': 10, 'mime-types': ['application/octet-stream'] } }) })).includes('octet-stream-needs-extensions'));
  assert.equal(h.telemetry.length, 0, 'content is not logged');
  await h.close();
});

// ---- device.openLink: egress to a declared https origin only, after the trusted prompt names it.
await section('device.openLink', async () => {
  const h = await host({ approve: true });
  const url = 'https://www.wikidata.org/wiki/Q42?uselang=ja';
  assert.deepEqual(ok(await h.local('device.openLink', { url })), { opened: true });
  assert.deepEqual(h.links, [url]);
  assert.ok(h.dialogs[0].summary.includes('開く先: https://www.wikidata.org'));
  assert.ok(h.dialogs[0].scope.includes(url), 'the whole URL is in the details');
  assert.equal(h.dialogs[0].note, 'このサイトは、この端末の外にあります。開くと、端末の IP アドレスなどと、URL に含まれる情報がそのサイトに送られます。URL の全文は「詳細を見る」で確かめられます。', 'Legal 2026-11-22 link notice');
  refused(await h.local('device.openLink', { url: 'https://evil.example/?d=1' }), 'not-declared');
  // Legal 2026-11-22: only public or fixed data; every parameter is constrained, and nothing undeclared is added.
  for (const bad of ['https://www.wikidata.org/wiki/Q42?uselang=ja&user=alice', 'https://www.wikidata.org/wiki/Q42?uselang=fr',
    'https://www.wikidata.org/wiki/hello%20world', 'https://www.wikidata.org/wiki/Q42#me', 'https://www.wikidata.org/wiki/Q42/extra',
    'https://www.wikidata.org/wiki/Q42?uselang=ja&uselang=en', 'https://etherscan.io/?q=0xabc', 'https://etherscan.io/address/0xabc']) {
    refused(await h.local('device.openLink', { url: bad }), 'not-declared');
  }
  assert.deepEqual(ok(await h.local('device.openLink', { url: 'https://etherscan.io/' })), { opened: true }, 'a fixed URL');
  refused(await h.local('device.openLink', { url: 'http://www.wikidata.org/' }), 'invalid-arguments');
  refused(await h.local('device.openLink', { url: 'https://user:pw@www.wikidata.org/' }), 'invalid-arguments');
  refused(await h.local('device.openLink', { url: `https://www.wikidata.org/?q=${'a'.repeat(600)}` }), 'invalid-arguments');
  refused(await h.local('device.openLink', { url: 'javascript:alert(1)' }), 'invalid-arguments');
  assert.equal(h.links.length, 2);
  await h.close();
  for (const mode of [false, 'synthetic', 'early']) {
    const n = await host({ approve: mode });
    refused(await n.local('device.openLink', { url }), 'not-approved');
    assert.equal(n.links.length, 0, `no open: ${mode}`);
    await n.close();
  }
  const links = (targets, length = 512) => descriptor({ 'host-local': hostLocal({ links: { targets, 'max-url-length': length } }) });
  assert.ok(problems(links([{ origin: 'https://127.0.0.1', path: '/' }])).includes('internal-address-requires-lan-scope'));
  assert.ok(problems(links([{ origin: 'https://*.example.com', path: '/' }])).includes('invalid-links'));
  assert.ok(problems(links([{ origin: 'https://x.example', path: '/' }], 4096)).includes('limit-over-global-cap'));
  assert.ok(problems(links([{ origin: 'https://x.example', path: '/wiki/:item' }])).includes('invalid-links'), 'a free-text path parameter is refused');
  assert.ok(problems(links([{ origin: 'https://x.example', path: '/', 'query-params': { q: { pattern: '.*' } } }])).includes('invalid-links'), 'a free-text query parameter is refused');
  assert.ok(problems(descriptor({ 'host-local': hostLocal({ links: { origins: ['https://x.example'], 'max-url-length': 512 } }) })).includes('invalid-links'), 'origin-only links are gone');
  // The default browser target opens with no opener and no referrer.
  const opened = []; globalThis.open = (...args) => { opened.push(args); };
  runtime.browserClientLinkTarget?.(url);
  assert.deepEqual(opened, [[url, '_blank', 'noopener,noreferrer']]);
});

// ---- Yataverse review of #1372 (2026-11-22): findings 1, 4 and 5.
await section('review 1372', async () => {
  const MiBx = 1048576;
  const big = (quota) => descriptor({ 'host-local': hostLocal({ storage: { ...hostLocal().storage, 'quota-bytes': quota, 'max-value-bytes': 16 * MiBx } }) });
  // 1. Two mounts of one app in one document share one storage: B sees A's key, and B's ifVersion 0 cannot overwrite it.
  const root = `rv-${rootSeq++}`;
  const a = await createTestHost({ descriptor: big(64 * MiBx), appId: APP, storageRoot: root });
  const b = await createTestHost({ descriptor: big(64 * MiBx), appId: APP, storageRoot: root });
  await b.local('storage.list', { store: 'files' });
  ok(await a.local('storage.put', { store: 'files', key: 'x.txt', value: enc('from A') }));
  assert.deepEqual(ok(await b.local('storage.list', { store: 'files' })).entries.map((e) => e.key), ['x.txt']);
  refused(await b.local('storage.put', { store: 'files', key: 'x.txt', value: enc('from B'), ifVersion: 0 }), 'version-conflict');
  assert.equal(dec(ok(await a.local('storage.get', { store: 'files', key: 'x.txt' })).value), 'from A', 'no lost update');
  // Another tab is another core over the same store with a stale cache: the backend still refuses the stale write.
  const { kv } = storageFor(root);
  const otherTab = runtime.createEncryptedClientStorageBackend({ kv, conformance: TEST_CONFORMANCE });
  const c = await createTestHost({ descriptor: big(64 * MiBx), appId: APP, storage: otherTab });
  assert.equal(ok(await c.local('storage.get', { store: 'files', key: 'x.txt' })).version, 1);
  await c.local('storage.list', { store: 'files' });
  ok(await a.local('storage.put', { store: 'files', key: 'x.txt', value: enc('A2'), ifVersion: 1 }));
  refused(await c.local('storage.put', { store: 'files', key: 'x.txt', value: enc('C'), ifVersion: 1 }), 'version-conflict');
  assert.equal(dec(ok(await a.local('storage.get', { store: 'files', key: 'x.txt' })).value), 'A2', 'the stale tab did not overwrite');
  for (const x of [a, b, c]) await x.close();
  // 4. Bytes moved by a batch count toward its 64 MiB limit, like puts.
  const m = await createTestHost({ descriptor: big(256 * MiBx), appId: APP, storageRoot: `mv-${rootSeq++}` });
  for (let i = 0; i < 5; i++) ok(await m.local('storage.put', { store: 'files', key: `s${i}`, value: new Uint8Array(16 * MiBx - 64) }));
  refused(await m.local('storage.batch', { ops: [0, 1, 2, 3, 4].map((i) => ({ move: { from: ['files', `s${i}`], to: ['files', `d${i}`] } })) }), 'too-large');
  assert.equal(ok(await m.local('storage.list', { store: 'files', prefix: 'd' })).entries.length, 0, 'nothing moved');
  await m.close();
  // 5. A call's bytes are counted before it is queued: with the queue full, a huge call is refused as too-large, not busy.
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  const inner = memoryKv();
  const slowKv = { ...inner, async get(key) { await gate; return inner.get(key); } };
  const slow = runtime.createEncryptedClientStorageBackend({ kv: slowKv, conformance: TEST_CONFORMANCE });
  const q = await createTestHost({ descriptor: big(64 * MiBx), appId: APP, storage: slow });
  const queued = Array.from({ length: 16 }, (_, i) => q.local('storage.list', { store: 'files', prefix: String(i) }));
  await tick();
  refused(await q.local('storage.list', { store: 'files' }), 'busy');
  refused(await q.local('storage.batch', { ops: [1, 2, 3, 4, 5].map((i) => ({ put: { store: 'files', key: `b${i}`, value: new Uint8Array(16 * MiBx) } })) }), 'too-large');
  release(); await Promise.all(queued);
  await q.close();
  // (b) The bytes held by queued calls are capped in total (128 MiB per app): a third 48 MiB batch waits for none.
  let open2;
  const gate2 = new Promise((resolve) => { open2 = resolve; });
  const inner2 = memoryKv();
  const slow2 = runtime.createEncryptedClientStorageBackend({ kv: { ...inner2, async get(key) { await gate2; return inner2.get(key); } }, conformance: TEST_CONFORMANCE });
  const r = await createTestHost({ descriptor: big(256 * MiBx), appId: APP, storage: slow2 });
  const batch48 = (tag) => ({ ops: [1, 2, 3].map((i) => ({ put: { store: 'files', key: `${tag}${i}`, value: new Uint8Array(16 * MiBx) } })) });
  const held = [r.local('storage.batch', batch48('a')), r.local('storage.batch', batch48('b'))];
  await tick();
  refused(await r.local('storage.batch', batch48('c')), 'busy');
  open2(); await Promise.all(held);
  ok(await r.local('storage.batch', batch48('c')));
  await r.close();
});

// ---- Bodies by reference (nagare): send stored values, or write a response into storage, without the bridge.
await section('stored bodies', async () => {
  const MiBx = 1048576;
  const hl = hostLocal({ storage: { ...hostLocal().storage, 'quota-bytes': 256 * MiBx, 'max-value-bytes': 16 * MiBx } });
  const ops = [
    op('publish', 'PUT', { 'request-body': 'host-local', 'max-request-bytes': 40 * MiBx, 'content-type': 'video/mp4', 'response-body': 'text', 'max-response-bytes': 4096 }),
    op('fetch', 'GET', { 'response-body': 'host-local', 'max-response-bytes': 40 * MiBx }),
  ];
  const h = await createTestHost({ descriptor: descriptor({ 'host-local': hl }, ops), appId: APP, storageRoot: `sb-${rootSeq++}`, approve: true });
  assert.equal(h.mountProblems, null, String(h.mountProblems));
  const parts = [fill(16 * MiBx, 1), fill(16 * MiBx, 2), fill(3 * MiBx, 3)];
  for (const [i, part] of parts.entries()) ok(await h.local('storage.put', { store: 'files', key: `video/${i}`, value: part }));
  const whole = Buffer.concat(parts);
  respondWith(() => new Response('{"ok":true}', { status: 201, headers: { 'content-type': 'application/json' } }));
  const publish = { capability: 'net/fetch', service: 'svc', operation: 'publish' };
  const sent = await h.operation(publish, { input: 'https://svc.example/packs/v', init: { method: 'PUT', body: { 'host-local': { store: 'files', keys: ['video/0', 'video/1', 'video/2'] } } } });
  assert.equal(sent.ok, true, JSON.stringify(sent).slice(0, 200));
  assert.ok(Buffer.from(h.requests[0].body).equals(whole), 'the stored values are sent in order, byte for byte');
  assert.equal(h.requests[0].headers['content-type'], 'video/mp4');
  assert.ok(h.dialogs[0].summary.includes('送る大きさの上限: 40 MiB'));
  assert.ok(h.dialogs[0].scope.includes(`Body from storage: files: 3 value(s), ${whole.length} bytes`), h.dialogs[0].scope);
  // Refused before consent: over the declared size (by stored sizes, before reading), a missing key, an undeclared store.
  ok(await h.local('storage.put', { store: 'files', key: 'video/3', value: fill(16 * MiBx, 4) }));
  for (const body of [{ 'host-local': { store: 'files', keys: ['video/0', 'video/1', 'video/2', 'video/3'] } },
    { 'host-local': { store: 'files', keys: ['missing'] } }, { 'host-local': { store: 'nope', keys: ['video/0'] } }, { 'host-local': { store: 'files', keys: ['../x'] } }]) {
    const r = await h.operation(publish, { input: 'https://svc.example/packs/v', init: { method: 'PUT', body } });
    assert.equal(r.ok, false, JSON.stringify(body));
  }
  assert.equal(h.dialogs.length, 1, 'no dialog for a refused stored body'); assert.equal(h.requests.length, 1);
  // (c) Nothing is read or decrypted before consent; a value changed while the dialog is open stops the request.
  const sbRoot = `sbc-${rootSeq++}`;
  const base = storageFor(sbRoot).backend;
  let reads = 0;
  const counting = { conformance: base.conformance, get: (...a) => { reads += 1; return base.get(...a); }, list: (...a) => base.list(...a), batch: (...a) => base.batch(...a), clear: (...a) => base.clear(...a) };
  const m = await createTestHost({ descriptor: descriptor({ 'host-local': hl }, ops), appId: APP, storage: counting, approve: 'manual' });
  for (const [i, part] of parts.entries()) ok(await m.local('storage.put', { store: 'files', key: `video/${i}`, value: part }));
  respondWith(() => new Response('{"ok":true}', { status: 201 }));
  reads = 0;
  let pendingCall = m.operation(publish, { input: 'https://svc.example/packs/v', init: { method: 'PUT', body: { 'host-local': { store: 'files', keys: ['video/0', 'video/1', 'video/2'] } } } });
  await tick(); await tick();
  assert.equal(m.dialog.open, true); assert.equal(reads, 0, 'no stored value is read before consent');
  m.allow();
  assert.equal((await pendingCall).ok, true);
  assert.equal(reads, 3, 'each value is read once, after consent'); assert.ok(Buffer.from(m.requests[0].body).equals(whole));
  pendingCall = m.operation(publish, { input: 'https://svc.example/packs/v', init: { method: 'PUT', body: { 'host-local': { store: 'files', keys: ['video/0', 'video/1', 'video/2'] } } } });
  await tick(); await tick();
  ok(await m.local('storage.put', { store: 'files', key: 'video/1', value: fill(10, 7) }));
  m.allow();
  const changed = await pendingCall;
  assert.equal(changed.ok, false); assert.match(changed.error, /changed after approval/);
  assert.equal(m.requests.length, 1, 'the changed body did not complete');
  await m.close();
  // Upload paths, chosen before consent. Default: buffered by the host. With uploadStreams and engine support:
  // streamed. Without either, a declared body over the 256 MiB buffer cap is refused before the dialog.
  const bigOp = [op('publish', 'PUT', { 'request-body': 'host-local', 'max-request-bytes': 512 * MiBx, 'response-body': 'text', 'max-response-bytes': 4096 })];
  for (const [label, opts, expect] of [['buffer', {}, 'buffered by the host'], ['stream', { uploadStreams: true }, 'streamed']]) {
    const u = await createTestHost({ descriptor: descriptor({ 'host-local': hl }, ops), appId: APP, storageRoot: `up-${label}-${rootSeq++}`, approve: true, ...opts });
    ok(await u.local('storage.put', { store: 'files', key: 'v/0', value: parts[2] }));
    respondWith(() => new Response('{}', { status: 201 }));
    assert.equal((await u.operation(publish, { input: 'https://svc.example/packs/v', init: { method: 'PUT', body: { 'host-local': { store: 'files', keys: ['v/0'] } } } })).ok, true, label);
    assert.ok(u.dialogs[0].scope.includes(expect), u.dialogs[0].scope);
    assert.ok(Buffer.from(u.requests[0].body).equals(Buffer.from(parts[2])));
    await u.close();
  }
  const RealRequest = globalThis.Request;
  for (const [label, opts, patch] of [['no streams flag', {}, false], ['engine without upload streams', { uploadStreams: true }, true]]) {
    if (patch) globalThis.Request = class extends RealRequest { constructor(input, init) { if (init?.body instanceof ReadableStream) throw new TypeError('no upload streams'); super(input, init); } };
    try {
      const u = await createTestHost({ descriptor: descriptor({ 'host-local': hl }, bigOp), appId: APP, storageRoot: `up-big-${rootSeq++}`, approve: true, ...opts });
      ok(await u.local('storage.put', { store: 'files', key: 'v/0', value: parts[2] }));
      const r = await u.operation(publish, { input: 'https://svc.example/packs/v', init: { method: 'PUT', body: { 'host-local': { store: 'files', keys: ['v/0'] } } } });
      assert.equal(r.ok, false, label); assert.match(r.error, /cannot stream an upload/);
      assert.equal(u.dialogs.length, 0, `${label}: refused before the dialog`); assert.equal(u.requests.length, 0);
      await u.close();
    } finally { globalThis.Request = RealRequest; }
  }
  // A response written into storage: chunks plus a manifest; the bytes never cross the bridge.
  const fetchOp = { capability: 'net/fetch', service: 'svc', operation: 'fetch' };
  const remote = fill(20 * MiBx + 5, 9);
  respondWith(() => new Response(remote, { status: 200, headers: { 'content-type': 'video/mp4' } }));
  const got = await h.operation(fetchOp, { input: 'https://svc.example/packs/w', 'store-response': { store: 'files', key: 'download/w' } });
  assert.equal(got.ok, true, JSON.stringify(got).slice(0, 200));
  assert.equal(got.stored.bytes, remote.length); assert.equal(got.stored.chunks, 2);
  assert.ok(!Object.hasOwn(got, 'bytes'), 'no bytes cross the bridge');
  const manifest = JSON.parse(dec(ok(await h.local('storage.get', { store: 'files', key: 'download/w' })).value));
  assert.equal(manifest.bytes, remote.length); assert.equal(manifest.chunks, 2);
  const c0 = ok(await h.local('storage.get', { store: 'files', key: 'download/w/000000' })).value;
  const c1 = ok(await h.local('storage.get', { store: 'files', key: 'download/w/000001' })).value;
  assert.ok(Buffer.concat([c0, c1]).equals(Buffer.from(remote)));
  assert.ok(h.dialogs.at(-1).scope.includes('Response written to: this app\'s storage on this device: files/download/w'));
  // Over the limit while streaming: cancelled, and the chunks written so far are removed.
  let cancelled = false;
  respondWith(() => new Response(new ReadableStream({ pull(c) { c.enqueue(fill(8 * MiBx)); }, cancel() { cancelled = true; } }), { status: 200 }));
  const tooBig = await h.operation(fetchOp, { input: 'https://svc.example/packs/x', 'store-response': { store: 'files', key: 'download/x' } });
  assert.equal(tooBig.ok, false); assert.equal(cancelled, true);
  assert.deepEqual(ok(await h.local('storage.list', { store: 'files', prefix: 'download/x' })).entries, [], 'partial chunks removed');
  // The target is required exactly when declared, and checked before consent.
  assert.equal((await h.operation(fetchOp, { input: 'https://svc.example/packs/y' })).ok, false);
  assert.equal((await h.operation(fetchOp, { input: 'https://svc.example/packs/y', 'store-response': { store: 'nope', key: 'a' } })).ok, false);
  await h.close();
  // Declarations: storage is required, and the reference cap is 1 GiB.
  const { storage: _s, stores: _t, ...noStorage } = hostLocal({ calls: ['device.save', 'device.openLink'] });
  assert.ok(problems(descriptor({ 'host-local': noStorage }, ops)).includes('host-local-body-requires-storage'));
  assert.ok(problems(descriptor({}, [op('fetch', 'GET', { 'response-body': 'host-local', 'max-response-bytes': runtime.CLIENT_REFERENCE_BODY_MAX + 1 })])).includes('bytes-limit-over-global-cap'));
});

// ---- Route templates: a parameter-only path is accepted only when every parameter is constrained (finding 7 kept).
await section('route templates', async () => {
  const relay = (endpoint) => ({ ...op('read', 'GET'), endpoint });
  const topic = { topic: { charset: 'lower-alnum-dash', 'min-length': 1, 'max-length': 64 } };
  assert.deepEqual(problems(descriptor({}, [relay({ origin: 'https://relay.example', method: 'GET', path: '/:topic', 'path-params': topic })])), []);
  assert.deepEqual(problems(descriptor({}, [relay({ origin: 'https://relay.example', routes: [{ method: 'GET', path: '/:topic/:kind', 'query-params': [], 'path-params': { ...topic, kind: { enum: ['json', 'car'] } } }] })])), []);
  assert.ok(problems(descriptor({}, [relay({ origin: 'https://relay.example', method: 'GET', path: '/:topic' })])).includes('generic-network-endpoint'), 'unconstrained stays refused');
  assert.ok(problems(descriptor({}, [relay({ origin: 'https://relay.example', routes: [{ method: 'GET', path: '/:topic/:kind', 'query-params': [], 'path-params': topic }] })])).includes('generic-network-endpoint'), 'one unconstrained parameter is enough to refuse');
  assert.ok(problems(descriptor({}, [relay({ origin: 'https://*.example', method: 'GET', path: '/:topic', 'path-params': topic })])).includes('generic-network-endpoint'), 'wildcard host stays refused');
  for (const rule of [{ charset: 'any', 'min-length': 1, 'max-length': 4 }, { charset: 'hex', 'min-length': 0, 'max-length': 4 }, { charset: 'hex', 'min-length': 1, 'max-length': 999 }, { enum: [] }, { enum: ['../x'] }, { pattern: '.*' }]) {
    assert.ok(problems(descriptor({}, [relay({ origin: 'https://relay.example', method: 'GET', path: '/:topic', 'path-params': { topic: rule } })])).length > 0, JSON.stringify(rule));
  }
  assert.ok(problems(descriptor({}, [relay({ origin: 'https://relay.example', method: 'GET', path: '/fixed', 'path-params': topic })])).length > 0, 'a constraint must name a path parameter');
  const endpoint = { origin: 'https://relay.example', routes: [{ method: 'GET', path: '/:topic/json', 'query-params': [], 'path-params': topic }] };
  assert.equal(runtime.clientEndpointAllowsRequest(endpoint, 'https://relay.example/news-1/json'), true);
  for (const path of ['/News/json', `/${'a'.repeat(65)}/json`, '/a_b/json']) assert.equal(runtime.clientEndpointAllowsRequest(endpoint, `https://relay.example${path}`), false, path);
  // The dialog shows the resolved path; a value outside the constraint never reaches consent.
  const h = await createTestHost({ descriptor: descriptor({}, [relay(endpoint)]), appId: APP, storageRoot: `r-${rootSeq++}`, approve: false });
  const sel = { capability: 'net/fetch', service: 'svc', operation: 'read' };
  assert.equal((await h.operation(sel, { input: 'https://relay.example/Bad_Topic/json' })).ok, false); assert.equal(h.dialogs.length, 0);
  await h.operation(sel, { input: 'https://relay.example/news-1/json' });
  assert.ok(h.dialogs[0].scope.includes('Action: GET /news-1/json'), h.dialogs[0].scope);
  await h.close();
});

// ---- An undeclared call is refused, and a mount without host-local refuses every host-local call.
await section('undeclared calls', async () => {
  const h = await host({ descriptor: descriptor({ 'host-local': hostLocal({ calls: ['storage.get'] }) }) });
  assert.match(String(h.mountProblems), /device-save-needs-save/, 'a save declaration without its call is refused');
  const { save: _s, links: _l, ...onlyStorage } = hostLocal({ calls: ['storage.get', 'storage.put'] });
  const g = await host({ descriptor: descriptor({ 'host-local': onlyStorage }) });
  assert.equal(g.mountProblems, null, String(g.mountProblems));
  refused(await g.local('storage.delete', { store: 'files', key: 'a' }), 'not-declared');
  refused(await g.local('device.save', { name: 'a.json', type: 'application/json', value: enc('{}') }), 'not-declared');
  refused(await g.local('keys.generate', { id: 'device', type: 'secret-32' }), 'not-declared');
  refused(await g.local('storage.export', {}), 'not-declared');
  assert.equal(g.dialogs.length, 0);
  const { 'host-local': _h, ...plain } = descriptor();
  const p = await host({ descriptor: plain });
  refused(await p.local('storage.get', { store: 'files', key: 'a' }), 'not-declared');
  for (const x of [h, g, p]) await x.close();
});

if (negativeControl) {
  // stdout directly: a failed section can leave a host (and its console capture) open.
  for (const [name, result] of outcomes) process.stdout.write(`${name}: ${result}\n`);
} else {
  process.stdout.write('PASS: KOTOBA-968 host-local storage (partitioned by app id, no egress, encrypted at rest with a non-extractable key, quotas, batch, versions, watch, clear), declared binary/text bodies with limits shown and enforced, device.save and device.openLink behind the trusted prompt, constrained route templates\n');
}
void harnessState;
