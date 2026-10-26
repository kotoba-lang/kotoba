// Verify http_post inject path (Node) + capabilities probe.
// Run: node test/verify-http-post.mjs
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import {
  actorHostImports,
  hostCaps,
  httpPostCapabilities,
  inMemoryStore,
  urlAllowed,
} from '../src/actor-host.js';

const here = path.dirname(fileURLToPath(import.meta.url));
let failed = false;
function check(cond, msg) {
  if (!cond) {
    failed = true;
    console.error('FAIL:', msg);
  } else {
    console.log('OK:', msg);
  }
}

const capsProbe = httpPostCapabilities();
check(capsProbe.inject === true, 'inject path always advertised');
check(typeof capsProbe.recommended === 'string', `recommended=${capsProbe.recommended}`);
console.log('capabilities:', JSON.stringify(capsProbe));

// Mock sync POST: echo body prefixed
const httpPost = (url, body) => {
  const prefix = new TextEncoder().encode(`ECHO:${url}:`);
  const out = new Uint8Array(prefix.length + body.length);
  out.set(prefix, 0);
  out.set(body, prefix.length);
  return out;
};

const memoryBox = {};
const caps = hostCaps({
  grants: ['http-post'],
  limits: { maxHttpPosts: 4 },
});
const imports = {
  kotoba: actorHostImports(['http-post'], caps, memoryBox, {
    store: inMemoryStore(),
    httpPost,
  }),
};
check(typeof imports.kotoba.http_post === 'function', 'http_post wired when inject present');

const wasmPath = path.join(here, '..', 'examples', 'http-post-echo.wasm');
const bytes = await readFile(wasmPath);
const { instance } = await WebAssembly.instantiate(bytes, imports);
memoryBox.memory = instance.exports.memory;

const n = Number(instance.exports.main());
check(n > 0, `main wrote ${n} response bytes`);
const text = new TextDecoder().decode(new Uint8Array(memoryBox.memory.buffer, 64, n));
check(text.startsWith('ECHO:http://example.test/echo:'), `response prefix ok (got ${text})`);
check(text.endsWith('ping'), `response body echo (got ${text})`);

// quota: maxHttpPosts=1 should deny second call with -1
const memoryBox2 = {};
const caps2 = hostCaps({ grants: ['http-post'], limits: { maxHttpPosts: 1 } });
const imports2 = {
  kotoba: actorHostImports(['http-post'], caps2, memoryBox2, { httpPost }),
};
const { instance: inst2 } = await WebAssembly.instantiate(bytes, imports2);
memoryBox2.memory = inst2.exports.memory;
const first = Number(inst2.exports.main());
const second = Number(inst2.exports.main());
check(first > 0, `first call ok (${first})`);
check(second === -1, `second call metered -1 (got ${second})`);

// without inject, http_post must be absent (link fail if guest needs it)
const bare = actorHostImports(['http-post'], caps, {}, {});
check(bare.http_post === undefined, 'http_post absent without inject/bridge');

// urlAllowed: unrestricted by default, prefix-matched when set
check(urlAllowed({}, 'http://anything.example/x') === true, 'urlAllowed: no allowedUrlPrefixes -- unrestricted');
check(urlAllowed({ allowedUrlPrefixes: null }, 'http://anything.example/x') === true, 'urlAllowed: null -- unrestricted');
check(urlAllowed({ allowedUrlPrefixes: [] }, 'http://anything.example/x') === false, 'urlAllowed: [] -- explicit deny-all');
check(
  urlAllowed({ allowedUrlPrefixes: ['http://example.test/'] }, 'http://example.test/echo') === true,
  'urlAllowed: matching prefix -- allowed',
);
check(
  urlAllowed({ allowedUrlPrefixes: ['http://other.test/'] }, 'http://example.test/echo') === false,
  'urlAllowed: non-matching prefix -- denied',
);

// allowlist wired into http_post: mismatched prefix -> in-band -1, same
// convention maxHttpPosts exhaustion already uses; the fixture wasm always
// posts to the baked-in "http://example.test/echo" (see the ECHO: check
// above), so a prefix for a different origin is guaranteed not to match.
const memoryBox3 = {};
const caps3 = hostCaps({
  grants: ['http-post'],
  limits: { maxHttpPosts: 4, allowedUrlPrefixes: ['http://not-example.test/'] },
});
const imports3 = {
  kotoba: actorHostImports(['http-post'], caps3, memoryBox3, { httpPost }),
};
const { instance: inst3 } = await WebAssembly.instantiate(bytes, imports3);
memoryBox3.memory = inst3.exports.memory;
const denied = Number(inst3.exports.main());
check(denied === -1, `http_post denied by allowedUrlPrefixes mismatch (got ${denied})`);

// allowlist matching the actual destination still succeeds normally
const memoryBox4 = {};
const caps4 = hostCaps({
  grants: ['http-post'],
  limits: { maxHttpPosts: 4, allowedUrlPrefixes: ['http://example.test/'] },
});
const imports4 = {
  kotoba: actorHostImports(['http-post'], caps4, memoryBox4, { httpPost }),
};
const { instance: inst4 } = await WebAssembly.instantiate(bytes, imports4);
memoryBox4.memory = inst4.exports.memory;
const allowed = Number(inst4.exports.main());
check(allowed > 0, `http_post succeeds when allowedUrlPrefixes matches the destination (got ${allowed})`);

if (failed) {
  console.error('verify-http-post FAILED');
  process.exit(1);
}
console.log('OK: http_post inject path + metering + capabilities');
