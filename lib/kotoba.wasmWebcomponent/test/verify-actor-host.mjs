// Dependency-free smoke test for src/actor-host.js's `actor:host` ABI port:
// (1) the hand-rolled synchronous SHA-256 against known digests, (2)
// validateImportSurface's grant/limit denials as pure data, (3) a real
// native-WebAssembly round trip through examples/actor-host/actor-host-demo.wasm
// (clock_monotonic/log_write/sha256_hex, module "kotoba" -- same fixture shape
// kotoba-lang/kototama's tender_test.clj compiles via wasm-tools, here
// compiled once and checked in). Run: `node test/verify-actor-host.mjs`
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import {
  sha256Hex,
  hostCaps,
  validateImportSurface,
  actorHostImports,
  inMemoryStore,
  memoryPagesUsed,
  memoryWithinCap,
  IMPORT_SURFACE,
  sessionAuthority,
} from '../src/actor-host.js';

const here = path.dirname(fileURLToPath(import.meta.url));

let failed = false;
function check(cond, message) {
  if (!cond) {
    failed = true;
    console.error(`FAIL: ${message}`);
  } else {
    console.log(`OK: ${message}`);
  }
}

// ── known SHA-256 digests (FIPS 180-4 / common test vectors) ───────────────
const emptyDigest = sha256Hex(new TextEncoder().encode(''));
check(
  emptyDigest === 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
  `sha256("") = e3b0c442...b855 (got ${emptyDigest})`
);
const helloDigest = sha256Hex(new TextEncoder().encode('hello'));
check(
  helloDigest === '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824',
  `sha256("hello") = 2cf24dba...9824 (got ${helloDigest})`
);
const abcDigest = sha256Hex(new TextEncoder().encode('abc'));
check(
  abcDigest === 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
  `sha256("abc") = ba7816bf...5ad (got ${abcDigest})`
);
// a 64-byte-aligned-boundary message (exercises the multi-chunk padding path)
const longMsg = 'a'.repeat(64);
const longDigest = sha256Hex(new TextEncoder().encode(longMsg));
check(typeof longDigest === 'string' && longDigest.length === 64, `sha256(64 "a"s) produces a 64-char hex digest (got length ${longDigest.length})`);

// ── validateImportSurface: grant/limit denials as pure data ────────────────
const deniedByDefault = validateImportSurface(['http-post'], hostCaps());
check(deniedByDefault.ok === false, 'http-post is denied under default HostCaps (no grants)');
check(
  deniedByDefault.errors.some((e) => e.error === 'grants/missing'),
  `denial reason is grants/missing (got ${JSON.stringify(deniedByDefault.errors)})`
);

const secretDenied = validateImportSurface(['sign'], hostCaps({ grants: ['sign'] }));
check(
  secretDenied.ok === false && secretDenied.errors.some((e) => e.error === 'limit/secret-imports'),
  `sign is denied without allowSecretImports even when granted (got ${JSON.stringify(secretDenied.errors)})`
);

const granted = validateImportSurface(['clock-monotonic', 'sha256-hex'], hostCaps({ grants: ['clock-monotonic', 'sha256-hex'] }));
check(granted.ok === true, `clock-monotonic+sha256-hex granted and requested both pass validation (got ${JSON.stringify(granted.errors)})`);
check(
  IMPORT_SURFACE.length === 63 &&
    IMPORT_SURFACE.some(({ id }) => id === 'http-fetch') &&
    IMPORT_SURFACE.some(({ id }) => id === 'http-post-headers') &&
    IMPORT_SURFACE.some(({ id }) => id === 'transport-connect') &&
    IMPORT_SURFACE.some(({ id }) => id === 'transport-close'),
  'browser authority table covers codec/network/transport/pg+deep-wire surface (54 imports)'
);

const httpGetDenied = validateImportSurface(
  ['http-get'],
  hostCaps({ grants: ['http-get'], limits: { allowWriteImports: true } })
);
check(
  httpGetDenied.ok === false && httpGetDenied.errors.some((e) => e.error === 'limit/max-http-gets'),
  `http-get is default-denied by maxHttpGets=0 (got ${JSON.stringify(httpGetDenied.errors)})`
);

// ── validateImportSurface: the remaining four denial branches, previously
// untested (only grants/missing and limit/secret-imports had coverage
// above) ────────────────────────────────────────────────────────────────
const unknownImport = validateImportSurface(['bogus-import'], hostCaps());
check(
  unknownImport.ok === false && unknownImport.errors.some((e) => e.error === 'imports/unknown'),
  `an id outside IMPORT_SURFACE is imports/unknown, not silently ignored (got ${JSON.stringify(unknownImport.errors)})`
);

const overMaxImports = validateImportSurface(
  ['clock-monotonic', 'sha256-hex'],
  hostCaps({ grants: ['clock-monotonic', 'sha256-hex'], limits: { maxImports: 1 } })
);
check(
  overMaxImports.ok === false && overMaxImports.errors.some((e) => e.error === 'limit/max-imports'),
  `requesting 2 known imports against maxImports:1 is limit/max-imports (got ${JSON.stringify(overMaxImports.errors)})`
);

const overMaxHttpPosts = validateImportSurface(['http-post'], hostCaps({ grants: ['http-post'], limits: { maxHttpPosts: 0 } }));
check(
  overMaxHttpPosts.ok === false && overMaxHttpPosts.errors.some((e) => e.error === 'limit/max-http-posts'),
  `http-post granted but over maxHttpPosts:0 is limit/max-http-posts, distinct from grants/missing (got ${JSON.stringify(overMaxHttpPosts.errors)})`
);
const overMaxHttpFetches = validateImportSurface(
  ['http-fetch'],
  hostCaps({ grants: ['http-fetch'], limits: { maxHttpFetches: 0 } })
);
check(
  overMaxHttpFetches.ok === false &&
    overMaxHttpFetches.errors.some((e) => e.error === 'limit/max-http-fetches'),
  `http-fetch has an independent deny-by-default quota (got ${JSON.stringify(overMaxHttpFetches.errors)})`
);

const writeDeniedByDefault = validateImportSurface(['log-write'], hostCaps({ grants: ['log-write'] }));
check(
  writeDeniedByDefault.ok === false && writeDeniedByDefault.errors.some((e) => e.error === 'limit/write-imports'),
  `log-write granted but allowWriteImports defaults to false is limit/write-imports (got ${JSON.stringify(writeDeniedByDefault.errors)})`
);

// ── actorHostImports: pre-flight rejection (no memory box even touched) ────
let preflightThrew = false;
try {
  actorHostImports(['log-write'], hostCaps({ grants: [] }), {});
} catch (e) {
  preflightThrew = true;
}
check(preflightThrew, 'actorHostImports throws pre-flight when the surface is rejected, before touching memoryBox');

// ── session authority: every declared import has the same post-link
// revocation and bounded-use semantics as Kototama's JVM tender ───────────
for (const { id } of IMPORT_SURFACE) {
  const authority = sessionAuthority([id], { [id]: 1 });
  authority.consume(id);
  check(
    authority.snapshot().consumed.has(id),
    `${id} is atomically exhausted after its one admitted use`
  );
  let exhausted = false;
  try { authority.consume(id); } catch (_) { exhausted = true; }
  check(exhausted, `${id} rejects a second use`);
}

{
  const authority = sessionAuthority(['clock-monotonic']);
  const fns = actorHostImports(
    ['clock-monotonic'],
    hostCaps({ grants: ['clock-monotonic'] }),
    {},
    { authority }
  );
  check(typeof fns.clock_monotonic() === 'bigint', 'linked clock import is initially active');
  authority.revoke('clock-monotonic');
  let revoked = false;
  try { fns.clock_monotonic(); } catch (_) { revoked = true; }
  check(revoked, 'already-linked clock import observes session revocation without re-instantiation');
}

// ── actorHostImports: RuntimeLimits exhaustion is an in-band -1, not a throw ─
{
  const store = inMemoryStore();
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  const fns = actorHostImports(
    ['log-write'],
    hostCaps({ grants: ['log-write'], limits: { allowWriteImports: true, maxLogWriteBytes: 4 } }),
    memoryBox,
    { store }
  );
  new Uint8Array(memoryBox.memory.buffer, 0, 4).set([1, 2, 3, 4]);
  const first = fns.log_write(0, 4);
  const second = fns.log_write(0, 4); // now 8 bytes total, over the 4-byte cap
  check(first === 0, `first 4-byte write succeeds (got ${first})`);
  check(second === -1, `second write exceeding maxLogWriteBytes=4 returns -1, not a throw (got ${second})`);
}

// ── actorHostImports: log_read's maxLogReadBytes exhaustion, the read-side
// mirror of maxLogWriteBytes above -- previously untested (only the write
// side had a test) ─────────────────────────────────────────────────────
{
  const store = inMemoryStore();
  store.append(new Uint8Array([1, 2, 3])); // 3 bytes, read again (not consumed) each call
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  const fns = actorHostImports(
    ['log-read'],
    hostCaps({ grants: ['log-read'], limits: { maxLogReadBytes: 4 } }),
    memoryBox,
    { store }
  );
  const first = fns.log_read(0, 100);
  const second = fns.log_read(0, 100); // now 6 accumulated bytes, over the 4-byte cap
  check(first === 3, `first read (3 bytes, under maxLogReadBytes=4) succeeds (got ${first})`);
  check(second === -1, `second read pushes accumulated logReadBytes to 6, over the cap -- returns -1, not a throw (got ${second})`);
}

// ── real native-WebAssembly round trip (module "kotoba", same convention
// kotoba.wasm-exec / kototama.tender use) ───────────────────────────────────
{
  const bytes = await readFile(path.join(here, '..', 'examples', 'actor-host', 'actor-host-demo.wasm'));
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
  check(written === 64, `main() wrote a 64-char sha256 hex digest (got ${written})`);

  const resultBytes = new Uint8Array(memoryBox.memory.buffer, 100, written);
  const resultText = new TextDecoder('utf-8').decode(resultBytes);
  check(
    resultText === '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824',
    `guest-computed sha256("hello") matches the known digest (got ${resultText})`
  );

  const logged = new TextDecoder('utf-8').decode(store.read());
  check(logged === 'hello', `log_write recorded the guest's 5-byte payload (got ${JSON.stringify(logged)})`);
}

// ── gen_keypair/sign/verify: real native-WebAssembly round trip through the
// vendored ed25519, same fixture shape kototama.tender's (JVM) tender_test.clj
// compiles via wasm-tools (module "kotoba", gen_keypair/sign/verify) ────────
{
  const bytes = await readFile(path.join(here, '..', 'examples', 'actor-host', 'crypto-demo.wasm'));
  const memoryBox = {};
  const caps = hostCaps({
    grants: ['gen-keypair', 'sign', 'verify'],
    limits: { allowSecretImports: true },
  });
  const importObject = {
    kotoba: actorHostImports(['gen-keypair', 'sign', 'verify'], caps, memoryBox, {}),
  };

  const { instance } = await WebAssembly.instantiate(bytes, importObject);
  memoryBox.memory = instance.exports.memory;

  const ok = Number(instance.exports.main());
  check(ok === 1, `guest gen_keypair -> sign -> verify round-trips true through real Chicory-equivalent WASM (got ${ok})`);
}

// ── kagi-sign: only a decision-aware trusted adapter is linkable; the guest
// receives signature bytes, never key material or an unrestricted signer. ──
{
  const denied = validateImportSurface(['kagi-sign'], hostCaps({ grants: ['kagi-sign'] }));
  check(!denied.ok && denied.errors.some(e => e.error === 'limit/max-kagi-signs'),
    'kagi-sign is default-denied by its finite invocation quota');
  const memory = new WebAssembly.Memory({ initial: 1 }), memoryBox = { memory };
  const caps = hostCaps({ grants: ['kagi-sign'], limits: { maxKagiSigns: 1 } });
  const absent = actorHostImports(['kagi-sign'], caps, memoryBox, {});
  check(typeof absent.kagi_sign === 'undefined', 'kagi-sign stays unlinked without a decision-aware trusted adapter');
  const decisions = [{ ref: 'kagi://ops/key', purpose: 'release' }];
  const calls = [];
  const fns = actorHostImports(['kagi-sign'], caps, memoryBox, {
    runtime: 'node',
    kagiDecisions: decisions,
    kagiSigner: { authorizedSign(actualDecisions, ref, message) {
      calls.push({ actualDecisions, ref, message: [...message] }); return new Uint8Array(64).fill(7);
    } },
  });
  const ref = new TextEncoder().encode('kagi://ops/key'), message = new Uint8Array([1,2,3]);
  new Uint8Array(memory.buffer, 0, ref.length).set(ref); new Uint8Array(memory.buffer, 64, message.length).set(message);
  check(fns.kagi_sign(0, ref.length, 64, message.length, 128, 64) === 64,
    'kagi-sign returns only bounded signature bytes through the trusted adapter');
  check(calls.length === 1 && calls[0].actualDecisions === decisions && calls[0].ref === 'kagi://ops/key' && calls[0].message.join(',') === '1,2,3',
    'kagi-sign threads the exact decision set, opaque reference and message');
  check(fns.kagi_sign(0, ref.length, 64, message.length, 128, 64) === -1,
    'kagi-sign exhausts its finite per-session quota');
}

// ── gen_keypair/sign/verify without allowSecretImports: denied pre-flight,
// same limit/secret-imports gate kototama.contract's default-runtime-limits
// enforces (RuntimeLimits' :allow-secret-imports? false by default) ────────
{
  const denied = validateImportSurface(['gen-keypair'], hostCaps({ grants: ['gen-keypair'] }));
  check(
    denied.ok === false && denied.errors.some((e) => e.error === 'limit/secret-imports'),
    `gen-keypair is denied without allowSecretImports even when granted (got ${JSON.stringify(denied.errors)})`
  );
}

// ── llm-infer: denied by default (maxLlmInfers 0, same convention
// max-http-posts uses), same limit/max-llm-infers shape kototama.tender's
// (JVM) :limit/max-llm-infers denial uses ──────────────────────────────────
{
  const denied = validateImportSurface(['llm-infer'], hostCaps({ grants: ['llm-infer'] }));
  check(
    denied.ok === false && denied.errors.some((e) => e.error === 'limit/max-llm-infers'),
    `llm-infer is denied without raising maxLlmInfers even when granted (got ${JSON.stringify(denied.errors)})`
  );
  const granted = validateImportSurface(['llm-infer'], hostCaps({ grants: ['llm-infer'], limits: { maxLlmInfers: 1 } }));
  check(granted.ok === true, `llm-infer granted + maxLlmInfers raised passes validation (got ${JSON.stringify(granted.errors)})`);
}

// ── llm-infer: without opts.llmInfer, fns.llm_infer is never wired even
// when granted -- same "declared but not linked" honesty http-post's
// permanent absence uses, just conditional on the Node caller's choice
// instead of universal ──────────────────────────────────────────────────
{
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  const fns = actorHostImports(
    ['llm-infer'],
    hostCaps({ grants: ['llm-infer'], limits: { maxLlmInfers: 1 } }),
    memoryBox
    // no opts.llmInfer
  );
  check(fns.llm_infer === undefined, 'fns.llm_infer is absent when no opts.llmInfer backend is supplied');
}

// ── high-level http-get: injected sync bridge only; exact endpoint/path,
// manual redirects, output cap, and fail-closed absence/invalid reply. ─────
{
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  const encoder = new TextEncoder();
  const host = encoder.encode('example.test');
  const requestPath = encoder.encode('/bounded');
  new Uint8Array(memoryBox.memory.buffer, 0, host.length).set(host);
  new Uint8Array(memoryBox.memory.buffer, 32, requestPath.length).set(requestPath);
  let seen = null;
  const caps = hostCaps({
    grants: ['http-get'],
    limits: {
      maxHttpGets: 1,
      allowWriteImports: true,
      httpUrlAllowlist: ['https://example.test:443/bounded'],
    },
  });
  const absent = actorHostImports(['http-get'], caps, memoryBox);
  check(absent.http_get === undefined, 'http_get stays unlinked without an explicit synchronous bridge');
  const fns = actorHostImports(['http-get'], caps, memoryBox, {
    httpGet: (request) => {
      seen = request;
      return encoder.encode('HTTP/1.1 200 OK\r\n\r\nok');
    },
  });
  const n = fns.http_get(0, host.length, 443, 32, requestPath.length, 128, 64);
  check(
    JSON.stringify(seen) === JSON.stringify({
      host: 'example.test', port: 443, path: '/bounded', maxBytes: 64, redirect: 'manual',
    }),
    `http_get bridge receives exact scoped request (got ${JSON.stringify(seen)})`
  );
  const response = new TextDecoder().decode(new Uint8Array(memoryBox.memory.buffer, 128, n));
  check(response === 'HTTP/1.1 200 OK\r\n\r\nok', `http_get writes bounded response bytes (got ${JSON.stringify(response)})`);
  check(fns.http_get(0, host.length, 443, 32, requestPath.length, 128, 64) === -1,
    'http_get enforces its per-session request quota');

  const wrongScope = actorHostImports(['http-get'], hostCaps({
    grants: ['http-get'],
    limits: {
      maxHttpGets: 1,
      allowWriteImports: true,
      httpUrlAllowlist: ['https://example.test:443/bounded'],
    },
  }), memoryBox, { httpGet: () => encoder.encode('unexpected') });
  check(wrongScope.http_get(0, host.length, 443, 32, requestPath.length - 1, 128, 64) === -1,
    'http_get rejects a path outside the structured HTTPS allowlist before injection');
}

// ── http-post: injected sync bridge, structured HTTPS scope and quota. ───
{
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  const encoder = new TextEncoder();
  const url = encoder.encode('https://api.example.test/v1/messages');
  const body = encoder.encode('{"prompt":"hi"}');
  new Uint8Array(memoryBox.memory.buffer, 0, url.length).set(url);
  new Uint8Array(memoryBox.memory.buffer, 64, body.length).set(body);
  let seen = null;
  const caps = hostCaps({
    grants: ['http-post'],
    limits: {
      maxHttpPosts: 1,
      httpUrlAllowlist: ['https://api.example.test/v1'],
    },
  });
  const absent = actorHostImports(['http-post'], caps, memoryBox);
  check(absent.http_post === undefined, 'http_post stays unlinked without an explicit synchronous bridge');
  const fns = actorHostImports(['http-post'], caps, memoryBox, {
    httpPost: (request) => {
      seen = request;
      return encoder.encode('accepted');
    },
  });
  const n = fns.http_post(0, url.length, 64, body.length, 128, 32);
  check(seen?.url === 'https://api.example.test/v1/messages' &&
        new TextDecoder().decode(seen.body) === '{"prompt":"hi"}' &&
        seen.redirect === 'manual',
    `http_post bridge receives scoped URL/body (got ${JSON.stringify(seen)})`);
  check(new TextDecoder().decode(new Uint8Array(memoryBox.memory.buffer, 128, n)) === 'accepted',
    'http_post writes the bounded response');
  check(fns.http_post(0, url.length, 64, body.length, 128, 32) === -1,
    'http_post enforces its per-session request quota');
}

// ── llm-infer: with a fake synchronous opts.llmInfer, a real prompt/reply
// round-trips through guest memory, and a null reply (no key configured /
// call failed) fails closed as -1, matching kototama.tender's
// llm-infer-host-fn never distinguishing the two in-band ──────────────────
{
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  let lastPrompt = null;
  const fns = actorHostImports(
    ['llm-infer'],
    hostCaps({ grants: ['llm-infer'], limits: { maxLlmInfers: 2 } }),
    memoryBox,
    { llmInfer: (prompt) => { lastPrompt = prompt; return prompt === 'fail' ? null : `echo:${prompt}`; } }
  );
  const promptBytes = new TextEncoder().encode('hi');
  new Uint8Array(memoryBox.memory.buffer, 0, promptBytes.length).set(promptBytes);
  const written = fns.llm_infer(0, promptBytes.length, 100, 64);
  const reply = new TextDecoder('utf-8').decode(new Uint8Array(memoryBox.memory.buffer, 100, written));
  check(lastPrompt === 'hi', `opts.llmInfer receives the guest's decoded prompt (got ${JSON.stringify(lastPrompt)})`);
  check(reply === 'echo:hi', `opts.llmInfer's reply is written back into guest memory (got ${JSON.stringify(reply)})`);

  const failBytes = new TextEncoder().encode('fail');
  new Uint8Array(memoryBox.memory.buffer, 0, failBytes.length).set(failBytes);
  const failResult = fns.llm_infer(0, failBytes.length, 100, 64);
  check(failResult === -1, `a null opts.llmInfer reply fails closed as -1 (got ${failResult})`);
}

// ── llm-infer: per-call metering against maxLlmInfers, the same in-band -1
// convention http_post's maxHttpPosts already uses (previously unenforced
// here -- only the pre-flight import-declaration count was checked, which
// is always <=1 per guest and never actually limits repeated calls) ───────
{
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  const fns = actorHostImports(
    ['llm-infer'],
    hostCaps({ grants: ['llm-infer'], limits: { maxLlmInfers: 1 } }),
    memoryBox,
    { llmInfer: () => 'ok' },
  );
  const promptBytes = new TextEncoder().encode('hi');
  new Uint8Array(memoryBox.memory.buffer, 0, promptBytes.length).set(promptBytes);
  const first = fns.llm_infer(0, promptBytes.length, 100, 64);
  const second = fns.llm_infer(0, promptBytes.length, 100, 64);
  check(first > 0, `first llm_infer call ok (${first})`);
  check(second === -1, `second llm_infer call metered -1 once maxLlmInfers is exhausted (got ${second})`);
}

// ── llm-infer: SAB-bridge path (opts.llmInferBridge + opts.llmInferUrl) --
// the SAME bridge shape http_post uses (a mock postSync here stands in for
// the real createSabHttpPostBridge instance kotoba-wasm-worker-host.js
// passes for BOTH capabilities; the real browser round-trip is covered by
// test/browser/verify_llm_infer_browser.cljk) ──────────────────────────────
{
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  const calls = [];
  const bridge = {
    postSync: (url, body) => {
      calls.push({ url, body: new TextDecoder().decode(body) });
      return new TextEncoder().encode(`proxied:${new TextDecoder().decode(body)}`);
    },
  };
  const fns = actorHostImports(
    ['llm-infer'],
    hostCaps({ grants: ['llm-infer'], limits: { maxLlmInfers: 1 } }),
    memoryBox,
    { llmInferBridge: bridge, llmInferUrl: 'http://proxy.example.test/infer' },
  );
  check(typeof fns.llm_infer === 'function', 'fns.llm_infer wired via llmInferBridge+llmInferUrl');
  const promptBytes = new TextEncoder().encode('hi');
  new Uint8Array(memoryBox.memory.buffer, 0, promptBytes.length).set(promptBytes);
  const written = fns.llm_infer(0, promptBytes.length, 100, 64);
  const reply = new TextDecoder('utf-8').decode(new Uint8Array(memoryBox.memory.buffer, 100, written));
  check(calls.length === 1 && calls[0].url === 'http://proxy.example.test/infer',
    `llm_infer POSTs to opts.llmInferUrl via the bridge (got ${JSON.stringify(calls)})`);
  check(calls[0].body === 'hi', `the bridge receives the raw decoded prompt as the POST body (got ${JSON.stringify(calls[0]?.body)})`);
  check(reply === 'proxied:hi', `the bridge's reply is written back into guest memory (got ${JSON.stringify(reply)})`);
}

// ── remaining JVM parity: GET and POST-with-headers share policy,
// transport, memory and lifecycle gates while preserving their exact ABI. ─
{
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  const enc = new TextEncoder();
  const dec = new TextDecoder();
  const put = (ptr, text) => {
    const bytes = enc.encode(text);
    new Uint8Array(memoryBox.memory.buffer, ptr, bytes.length).set(bytes);
    return bytes.length;
  };
  const calls = [];
  const authority = sessionAuthority(
    ['http-fetch', 'http-post-headers'],
    { 'http-fetch': 1, 'http-post-headers': 1 },
  );
  const fns = actorHostImports(
    ['http-fetch', 'http-post-headers'],
    hostCaps({
      grants: ['http-fetch', 'http-post-headers'],
      limits: {
        maxHttpFetches: 1,
        maxHttpPosts: 1,
        allowedUrlPrefixes: ['https://api.example.test/'],
      },
    }),
    memoryBox,
    {
      authority,
      httpFetch: (url) => {
        calls.push({ method: 'GET', url });
        return enc.encode('fetched');
      },
      httpPostHeaders: (url, body, headers) => {
        calls.push({ method: 'POST', url, body: dec.decode(body), headers });
        return enc.encode('posted');
      },
    },
  );
  const getUrlLen = put(0, 'https://api.example.test/feed');
  const fetched = fns.http_fetch(0, getUrlLen, 512, 32);
  check(
    fetched === 7 && dec.decode(new Uint8Array(memoryBox.memory.buffer, 512, fetched)) === 'fetched',
    'http_fetch executes GET and writes its bounded response'
  );
  const postUrlLen = put(64, 'https://api.example.test/records');
  const bodyLen = put(160, '{"ok":true}');
  const headersLen = put(256, 'authorization\tBearer proof\ncontent-type\tapplication/json');
  const posted = fns.http_post_headers(64, postUrlLen, 160, bodyLen, 256, headersLen, 544, 32);
  check(
    posted === 6 && calls[1].headers[0][0] === 'authorization' &&
      calls[1].headers[0][1] === 'Bearer proof',
    `http_post_headers preserves flat-pair headers (got ${JSON.stringify(calls[1])})`
  );
  check(
    authority.snapshot().consumed.has('http-fetch') &&
      authority.snapshot().consumed.has('http-post-headers'),
    'both new browser imports consume their one-shot authority handles'
  );
}

// ── maxMemoryPages: memoryPagesUsed/memoryWithinCap pure helpers ───────────
// kototama.contract's default-runtime-limits :max-memory-pages is 16 (1
// MiB) -- same default DEFAULT_RUNTIME_LIMITS.maxMemoryPages uses here.
{
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  check(memoryPagesUsed(memoryBox) === 1, `1-page memory reports 1 page (got ${memoryPagesUsed(memoryBox)})`);
  check(memoryWithinCap(memoryBox, hostCaps()), '1-page memory is within the default 16-page cap');

  memoryBox.memory.grow(20); // now 21 pages, over the 16-page default cap
  check(memoryPagesUsed(memoryBox) === 21, `after grow(20), reports 21 pages (got ${memoryPagesUsed(memoryBox)})`);
  check(!memoryWithinCap(memoryBox, hostCaps()), '21-page memory exceeds the default 16-page cap');
  check(
    memoryWithinCap(memoryBox, hostCaps({ limits: { maxMemoryPages: 32 } })),
    '21-page memory is within an explicitly-raised 32-page cap'
  );
}

// ── maxMemoryPages: reactive per-call gating inside actorHostImports --
// growth AFTER instantiation (simulated here by growing memoryBox.memory
// directly, since these unit tests don't run a real guest export) is
// caught the next time a gated host-import is called, same in-band -1
// convention maxLogWriteBytes-adjacent limits use (see overMemoryCap's
// doc comment in actor-host.js for why this is reactive, not preventive,
// in a browser/Node host) ───────────────────────────────────────────────
{
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  const fns = actorHostImports(
    ['sha256-hex', 'verify'],
    hostCaps({ grants: ['sha256-hex', 'verify'] }),
    memoryBox,
    {}
  );
  const before = fns.sha256_hex(0, 0, 100, 64);
  check(before >= 0, `sha256_hex succeeds while memory is within the default cap (got ${before})`);

  memoryBox.memory.grow(20); // now 21 pages, over the 16-page default cap
  const after = fns.sha256_hex(0, 0, 100, 64);
  check(after === -1, `sha256_hex returns -1 once memory exceeds maxMemoryPages, not a throw (got ${after})`);

  const verifyDenied = fns.verify(0, 0, 0, 0, 0, 0);
  check(verifyDenied === 0, `verify returns its own 0 (not -1) denial shape once over the memory cap (got ${verifyDenied})`);
}

// ── maxMemoryPages: raising the cap via HostCaps limits (same "guest that
// legitimately needs more grows this explicitly" escape hatch every other
// limit here has) permits the same call that was just denied above ──────
{
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  memoryBox.memory.grow(20); // 21 pages, over the default 16-page cap
  const fns = actorHostImports(
    ['sha256-hex'],
    hostCaps({ grants: ['sha256-hex'], limits: { maxMemoryPages: 32 } }),
    memoryBox,
    {}
  );
  const result = fns.sha256_hex(0, 0, 100, 64);
  check(result >= 0, `sha256_hex succeeds at 21 pages once maxMemoryPages is explicitly raised to 32 (got ${result})`);
}


// ── T8.4 Node transport inject fail-closed ─────────────────────────────
{
  const denied = validateImportSurface(
    ['transport-connect'],
    hostCaps({ grants: ['transport-connect'] }),
  );
  check(
    denied.ok === false &&
      denied.errors.some((e) => e.error === 'limit/max-transport-connections'),
    'transport-connect denied under maxTransportConnections 0 (deny-by-default)',
  );

  const okSurf = validateImportSurface(
    ['transport-connect', 'transport-close', 'tls-open', 'transport-write', 'transport-read'],
    hostCaps({
      grants: ['transport-connect', 'transport-close', 'tls-open', 'transport-write', 'transport-read'],
      limits: { maxTransportConnections: 2 },
    }),
  );
  check(okSurf.ok === true, `transport surface validates when quota raised (got ${JSON.stringify(okSurf.errors)})`);

  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  const imports = actorHostImports(
    ['transport-connect', 'transport-close', 'tls-open', 'transport-write', 'transport-read', 'tls-server-end-point'],
    hostCaps({
      grants: [
        'transport-connect', 'transport-close', 'tls-open',
        'transport-write', 'transport-read', 'tls-server-end-point',
      ],
      limits: { maxTransportConnections: 2 },
    }),
    memoryBox,
    { runtime: 'node' },
  );
  const kotoba = imports.kotoba || imports;
  check(typeof kotoba.transport_connect === 'function', 'Node wires transport_connect');
  check(typeof kotoba.transport_close === 'function', 'Node wires transport_close');
  check(typeof kotoba.tls_open === 'function', 'Node wires tls_open');
  // fail-closed: empty allowlist semantics → handle 0
  const enc = new TextEncoder();
  const host = enc.encode('example.com');
  new Uint8Array(memoryBox.memory.buffer, 0, host.length).set(host);
  const h = kotoba.transport_connect(0, host.length, 443);
  check(h === 0n || h === 0, `fail-closed transport_connect returns 0 (got ${h})`);
  const tls = kotoba.tls_open(0n, 0, 0);
  check(tls === 0n || tls === 0, `fail-closed tls_open returns 0 (got ${tls})`);
  check(kotoba.transport_write(0n, 0, 0) === -1, 'fail-closed transport_write returns -1');
  check(kotoba.transport_read(0n, 0, 8) === -1, 'fail-closed transport_read returns -1');
  check(kotoba.transport_close(0n) === -1, 'fail-closed transport_close returns -1');
  check(kotoba.tls_server_end_point(0n, 0, 8) === -1, 'fail-closed tls_server_end_point returns -1');

  // browser runtime does NOT wire transport
  const browserImports = actorHostImports(
    ['transport-connect'],
    hostCaps({
      grants: ['transport-connect'],
      limits: { maxTransportConnections: 1 },
    }),
    memoryBox,
    { runtime: 'browser' },
  );
  const b = browserImports.kotoba || browserImports;
  check(typeof b.transport_connect !== 'function', 'browser does not wire transport_connect');
}


// ── T8.4 Node pg-pool / wire / scram inject fail-closed ───────────────
{
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  const grants = [
    'pg-pool-open', 'pg-pool-acquire', 'pg-pool-query', 'pg-pool-release',
    'pg-pool-stats', 'pg-pool-health', 'pg-pool-drain', 'pg-pool-close',
    'pg-open', 'pg-query', 'pg-simple-query',
    'pg-cancel-register', 'pg-cancel', 'scram-sha256',
  ];
  // write/secret required for query + scram surface admission
  const deniedWrite = validateImportSurface(
    ['pg-pool-query'],
    hostCaps({ grants: ['pg-pool-query'] }),
  );
  check(
    deniedWrite.ok === false &&
      deniedWrite.errors.some((e) => e.error === 'limit/write-imports'),
    'pg-pool-query denied without allowWriteImports',
  );
  const deniedSecret = validateImportSurface(
    ['scram-sha256'],
    hostCaps({ grants: ['scram-sha256'] }),
  );
  check(
    deniedSecret.ok === false &&
      deniedSecret.errors.some((e) => e.error === 'limit/secret-imports'),
    'scram-sha256 denied without allowSecretImports',
  );

  const caps = hostCaps({
    grants,
    limits: { allowWriteImports: true, allowSecretImports: true },
  });
  const okSurf = validateImportSurface(grants, caps);
  check(okSurf.ok === true, `pg surface validates (got ${JSON.stringify(okSurf.errors)})`);

  const imports = actorHostImports(grants, caps, memoryBox, { runtime: 'node' });
  check(typeof imports.pg_pool_open === 'function', 'Node wires pg_pool_open');
  check(typeof imports.pg_open === 'function', 'Node wires pg_open');
  check(typeof imports.scram_sha256 === 'function', 'Node wires scram_sha256');
  // fail-closed defaults
  check(imports.pg_pool_open(0, 1, 5432, 0, 1, 0, 1, 0, 1) === -1, 'pg_pool_open fail-closed -1');
  check(imports.pg_pool_acquire(99) === -1, 'pg_pool_acquire fail-closed -1');
  check(imports.pg_pool_health(99) === -1, 'pg_pool_health fail-closed -1');
  check(imports.pg_pool_close(99) === -1, 'pg_pool_close fail-closed -1');
  check(imports.pg_pool_query(99, 0, 0, 0, 0, 0, 0) === -1, 'pg_pool_query fail-closed -1');
  check(imports.pg_pool_release(99) === -1, 'pg_pool_release fail-closed -1');
  check(imports.pg_pool_stats(99, 0, 32) === -1, 'pg_pool_stats fail-closed -1');
  check(imports.pg_pool_drain(99) === -1, 'pg_pool_drain fail-closed -1');
  const openH = imports.pg_open(0, 1, 5432, 0, 1, 0, 1);
  check(openH === 0n || openH === 0, `pg_open fail-closed 0 (got ${openH})`);
  check(imports.pg_query(0n, 0, 0, 0, 0) === -1, 'pg_query fail-closed -1');
  check(imports.pg_cancel_register(0n, 1, 2) === 0, 'pg_cancel_register fail-closed 0');
  check(imports.pg_cancel(1) === -1, 'pg_cancel fail-closed -1');
  // scram deny without allowlist/credentials
  check(
    imports.scram_sha256(0, 10, 32, 8, 4096, 64, 28, 128, 64) === -1,
    'scram_sha256 deny without credentials',
  );
  // scram success with inject
  const enc = new TextEncoder();
  const ref = enc.encode('db/primary');
  const salt = enc.encode('saltsalt');
  const auth = enc.encode('n,,n=u,r=r1,r=r2,c=biws,p=x');
  new Uint8Array(memoryBox.memory.buffer, 0, ref.length).set(ref);
  new Uint8Array(memoryBox.memory.buffer, 32, salt.length).set(salt);
  new Uint8Array(memoryBox.memory.buffer, 64, auth.length).set(auth);
  const scramImports = actorHostImports(['scram-sha256'], caps, memoryBox, {
    runtime: 'node',
    scramCredentials: { 'db/primary': 's3cret' },
    scramCredentialAllowlist: new Set(['db/primary']),
  });
  const n = scramImports.scram_sha256(0, 10, 32, 8, 4096, 64, 28, 128, 64);
  check(n === 64, `scram_sha256 with credentials writes 64 (got ${n})`);

  // browser does not wire pg
  const b = actorHostImports(['pg-pool-open'], hostCaps({
    grants: ['pg-pool-open'],
  }), memoryBox, { runtime: 'browser' });
  check(typeof b.pg_pool_open !== 'function', 'browser does not wire pg_pool_open');
}


// ── T8.4 Node deeper wire inject fail-closed ──────────────────────────
{
  const memoryBox = { memory: new WebAssembly.Memory({ initial: 1 }) };
  const deep = [
    'pg-prepare', 'pg-session-reset', 'pg-close-statement', 'pg-query-state',
    'pg-prepare-typed', 'pg-execute-params2', 'pg-execute-params',
    'pg-bind-portal', 'pg-fetch-portal', 'pg-close-portal',
    'pg-copy-out', 'pg-copy-in', 'pg-execute-batch',
    'pg-open-scram', 'pg-open-scram-random', 'pg-open-scram-cancellable-random',
    'pg-cancel-authority-use', 'pg-close-scram',
  ];
  const caps = hostCaps({
    grants: deep,
    limits: { allowWriteImports: true },
  });
  const ok = validateImportSurface(deep, caps);
  check(ok.ok === true, `deep wire surface validates (got ${JSON.stringify(ok.errors)})`);
  const imports = actorHostImports(deep, caps, memoryBox, { runtime: 'node' });
  check(typeof imports.pg_prepare === 'function', 'Node wires pg_prepare');
  check(typeof imports.pg_bind_portal === 'function', 'Node wires pg_bind_portal');
  check(typeof imports.pg_open_scram === 'function', 'Node wires pg_open_scram');
  check(imports.pg_prepare(0n, 0, 0, 0, 0, 0, 0, 0, 0) === -1, 'pg_prepare fail-closed -1');
  check(imports.pg_session_reset(0n, 0, 0, 0, 0) === -1, 'pg_session_reset fail-closed -1');
  check(imports.pg_close_statement(0n, 0, 0, 0, 0, 0, 0) === -1, 'pg_close_statement fail-closed -1');
  check(imports.pg_query_state(0n, 0, 0, 0, 0, 0, 0) === -1, 'pg_query_state fail-closed -1');
  check(imports.pg_bind_portal(0n, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0) === -1, 'pg_bind_portal fail-closed -1');
  check(imports.pg_fetch_portal(0n, 0, 0, 0, 0, 0, 0, 0) === -1, 'pg_fetch_portal fail-closed -1');
  check(imports.pg_close_portal(0n, 0, 0, 0, 0, 0, 0) === -1, 'pg_close_portal fail-closed -1');
  check(imports.pg_copy_out(0n, 0, 0, 0, 0, 0, 0) === -1, 'pg_copy_out fail-closed -1');
  check(imports.pg_copy_in(0n, 0, 0, 0, 0, 0, 0, 0, 0) === -1, 'pg_copy_in fail-closed -1');
  check(imports.pg_execute_batch(0n, 0, 0, 0, 0, 0, 0, 0) === -1, 'pg_execute_batch fail-closed -1');
  const h = imports.pg_open_scram(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);
  check(h === 0n || h === 0, `pg_open_scram fail-closed 0 (got ${h})`);
  const hr = imports.pg_open_scram_random(0, 0, 0, 0, 0, 0, 0, 0, 0);
  check(hr === 0n || hr === 0, `pg_open_scram_random fail-closed 0 (got ${hr})`);
  check(imports.pg_cancel_authority_use(1) === -1, 'pg_cancel_authority_use fail-closed -1');
  check(imports.pg_close_scram(0n) === -1, 'pg_close_scram fail-closed -1');
  const b = actorHostImports(['pg-prepare'], hostCaps({
    grants: ['pg-prepare'], limits: { allowWriteImports: true },
  }), memoryBox, { runtime: 'browser' });
  check(typeof b.pg_prepare !== 'function', 'browser does not wire pg_prepare');
}

if (failed) process.exit(1);
console.log('OK: actor-host.js round-trips through a real native-WebAssembly-hosted module');
