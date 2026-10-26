// Browser-side port of kotoba-lang/kototama's src/kototama/contract.cljc
// (the pure `actor:host` ABI authority: HostCaps/RuntimeLimits/
// validate-import-surface) plus a browser-native implementation of the
// subset of its 8 host imports that a WebAssembly host-import function can
// actually perform SYNCHRONOUSLY (see "Scope" below).
//
// Like kgraph.js, this is a from-scratch, dependency-free port, not a
// compiled build of the CLJC source -- this repo stays zero-build-step,
// CDN-servable as raw ES modules (see README).
//
// Amu wasm32-kotoba-v1 guests import `kotoba:cap`/`call` (i64,i64)->i64,
// not `actor:host`. That host lives in ClojureScript
// (`src-cljs/kotoba/kotoba_cap.cljk` → `src/kotoba-cap.js`), not here —
// new host surface is cljs; this file stays the legacy hand-JS actor:host
// plane. Importing this module must not pull the cljs runtime.
//
// ---------------------------------------------------------------------------
// Scope (honest R2): 7 of the 9 `actor:host` imports are unconditionally
// synchronous; `llm-infer` and `http-post` are each conditional, wired via
// one of:
//   (A) opts.httpPost / opts.llmInfer — sync inject (Node mock / blocking backend)
//   (B) opts.httpPostBridge / opts.llmInferBridge+llmInferUrl —
//       SharedArrayBuffer + Atomics.wait (requires crossOriginIsolated /
//       COOP+COEP headers). `llm-infer`'s bridge path reuses the identical
//       bridge shape `http-post` uses (often the SAME bridge instance) --
//       both are "sync host-import needs real async network I/O", solved
//       once. `llmInferUrl` must point at a developer-controlled proxy, NOT
//       a real LLM provider directly -- a browser tab can never hold a
//       provider API key without shipping it to every visitor.
//   (C) JSPI note — WebAssembly Promise Integration is Chrome-flagged;
//       not wired as default until multi-engine (use inject until then).
//
// A WebAssembly host-import function called from a running guest MUST
// return synchronously -- there is no `await` inside a Wasm call in a
// standard browser today (JS Promise Integration would allow this but isn't
// broadly shipped across engines yet). `gen-keypair`/`sign`/`verify`
// (Ed25519) don't actually need to go through the always-async Web Crypto
// `SubtleCrypto` API to be correct, though -- Ed25519 signing is pure
// arithmetic over bytes already in memory, not I/O, so a genuinely
// synchronous implementation is possible without SubtleCrypto at all. Unlike
// `sha256_hex` below, this isn't hand-rolled from scratch (a real,
// non-trivial correctness undertaking for elliptic-curve arithmetic
// specifically): `./vendor/curves/ed25519.js` vendors the actual,
// unmodified, audited `@noble/curves` (see `./vendor/README.md` for
// provenance and why vendored rather than CDN-imported).
//
// `http-post` cannot call `fetch` directly inside a sync host import in a
// standard browser tab. Paths that ARE implemented (see `http_post` wiring
// below + `http-post-bridge.js`):
//   - inject: opts.httpPost(url, bodyUint8) => Uint8Array|null  (Node/tests)
//   - SAB/COOP: opts.httpPostBridge worker (Atomics.wait on SharedArrayBuffer)
// JSPI (Chrome-only Promise Integration) is documented but not the default
// wire — guests that request `http_post` without a path still fail to link.
//
// Implemented (all genuinely synchronous):
//   - `clock_monotonic` -- `Date.now()`
//   - `sha256_hex`    -- hand-rolled synchronous SHA-256, zero dependencies,
//                        verified against known digests in
//                        test/verify-actor-host.mjs
//   - `gen_keypair` / `sign` / `verify` -- vendored `@noble/curves` ed25519
//                        (see above), verified via a real Chicory-equivalent
//                        WASM round trip in test/verify-actor-host.mjs
//   - `log_read` / `log_write` -- an injectable synchronous byte store
//                        (same `store` parameter shape kgraph.js uses)
//
// Field/id names (`clock-monotonic`/`log-write`, not `now`/`log-append!`)
// match `kotoba-lang/kototama`'s `kototama.contract` and
// `kotoba-core-contracts`' capability_contract.edn 1:1 -- a concurrent
// session independently registered `clock-monotonic`/`log-write` in that
// shared compiler table for aiueos's kernel-capability vocabulary with
// identical wire signatures, so kototama's side (and this browser port)
// were renamed to reuse those names instead of registering the same
// operation twice under different names.

import { ed25519 } from './vendor/curves/ed25519.js';

export const ACTOR_HOST_NAMESPACE = 'actor:host';
export const ACTOR_HOST_VERSION = 0;

// ---------------------------------------------------------------------------
// kototama.contract's import-surface, ported 1:1 (same ids, same effect
// tags -- kept complete even though only some have a browser implementation
// below, so `validateImportSurface` still recognizes and correctly denies
// the rest by name rather than treating them as unknown).

export const IMPORT_SURFACE = [
  { id: 'gen-keypair', category: 'identity', effects: new Set(['crypto', 'secret']) },
  { id: 'sign', category: 'identity', effects: new Set(['crypto', 'secret']) },
  { id: 'verify', category: 'identity', effects: new Set(['crypto']) },
  { id: 'sha256-hex', category: 'content-addressing', effects: new Set(['crypto']) },
  { id: 'http-post', category: 'network', effects: new Set(['network']) },
  { id: 'http-fetch', category: 'network', effects: new Set(['network']) },
  { id: 'log-read', category: 'storage', effects: new Set(['storage']) },
  { id: 'log-write', category: 'storage', effects: new Set(['storage', 'write']) },
  { id: 'clock-monotonic', category: 'clock', effects: new Set(['clock']) },
  // Bounded OS/Web Crypto CSPRNG fill (host-parity L5 / kototama tender
  // `:random-bytes`). Default `maxRandomBytes` is 0 — deny-by-default until
  // HostCaps raises the quota (same pattern as maxHttpPosts / maxLlmInfers).
  { id: 'random-bytes', category: 'randomness', effects: new Set(['crypto', 'write']) },
  // Decision-aware trusted-adapter sign (host-parity L5 / T8.4).
  // Key never enters the guest; default maxKagiSigns 0 deny-by-default.
  // Node-only inject via opts.kagiSigner + opts.kagiDecisions; browser
  // intentional absence (native boundary).
  { id: 'kagi-sign', category: 'identity', effects: new Set(['crypto']) },
  // `llm-infer` (`llm/infer`, capability id 225 in kotoba-core-contracts'
  // capability_contract.edn; kototama.tender's Anthropic Messages API
  // call). Unlike `http-post`, this ISN'T fundamentally un-implementable
  // here -- it's only a real browser tab that can't do synchronous network
  // I/O. A Node host (this repo's own test/*.mjs scripts, not a browser)
  // has no such constraint and can inject a genuinely synchronous
  // implementation via `opts.llmInfer` (e.g. a blocking child_process
  // call) below, so this is listed unconditionally and wired whenever a
  // caller supplies one -- same "declared but only linked when a real
  // implementation exists" honesty `http-post`'s comment above documents,
  // just environment-dependent instead of universally absent.
  { id: 'llm-infer', category: 'llm', effects: new Set(['network']) },
  // Codec imports (ADR-2607230943 second wave). Pure computation, no
  // network/DOM dependency -- a faithful byte-for-byte JS port of
  // kototama.tender's (JVM) flat-pairs -> CBOR/JSON encoders and bounded
  // JSON string-field scan, so they link in a plain browser tab (no
  // SAB/Worker bridge needed, unlike http-post/llm-infer). See the
  // `parseFlatPairs`/`treeNodeToCbor`/`treeNodeToJson`/`jsonStringFieldValue`
  // helpers below.
  { id: 'cbor-encode', category: 'codec', effects: new Set() },
  { id: 'json-encode', category: 'codec', effects: new Set() },
  { id: 'json-extract-field', category: 'codec', effects: new Set() },
  { id: 'http-post-headers', category: 'network', effects: new Set(['network']) },
  // Transport/TLS (T8.4 Node inject path). Browser intentional absence —
  // native boundary (same honesty as kagi-sign). Node wires fail-closed
  // defaults and optional opts.transportProvider overrides; no real sockets
  // unless a provider inject is supplied. Matches kototama.guest field names.
  { id: 'transport-connect', category: 'network', effects: new Set(['network']) },
  { id: 'tls-open', category: 'network', effects: new Set(['network']) },
  { id: 'tls-server-end-point', category: 'network', effects: new Set(['network']) },
  { id: 'transport-write', category: 'network', effects: new Set(['network']) },
  { id: 'transport-read', category: 'network', effects: new Set(['network']) },
  { id: 'transport-close', category: 'network', effects: new Set(['network']) },
  // PostgreSQL pool / wire / cancel / SCRAM (T8.4 Node inject). Browser
  // intentional absence. Node: fail-closed defaults; optional
  // opts.pgPoolProvider / opts.pgWireProvider / opts.scramCredentials.
  { id: 'pg-pool-open', category: 'network', effects: new Set(['network']) },
  { id: 'pg-pool-acquire', category: 'network', effects: new Set(['network']) },
  { id: 'pg-pool-query', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-pool-release', category: 'network', effects: new Set(['network']) },
  { id: 'pg-pool-stats', category: 'network', effects: new Set(['network']) },
  { id: 'pg-pool-health', category: 'network', effects: new Set(['network']) },
  { id: 'pg-pool-drain', category: 'network', effects: new Set(['network']) },
  { id: 'pg-pool-close', category: 'network', effects: new Set(['network']) },
  { id: 'pg-open', category: 'network', effects: new Set(['network']) },
  { id: 'pg-query', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-simple-query', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-cancel-register', category: 'network', effects: new Set(['network']) },
  { id: 'pg-cancel', category: 'network', effects: new Set(['network']) },
  { id: 'scram-sha256', category: 'secret', effects: new Set(['secret']) },
  // Deeper wire + SCRAM session open (T8.4 Node inject residual).
  // Browser intentional absence; Node fail-closed (match JVM wire provider).
  { id: 'pg-prepare', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-session-reset', category: 'network', effects: new Set(['network']) },
  { id: 'pg-close-statement', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-query-state', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-prepare-typed', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-execute-params2', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-execute-params', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-bind-portal', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-fetch-portal', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-close-portal', category: 'network', effects: new Set(['network']) },
  { id: 'pg-copy-out', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-copy-in', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-execute-batch', category: 'network', effects: new Set(['network', 'write']) },
  { id: 'pg-open-scram', category: 'network', effects: new Set(['network']) },
  { id: 'pg-open-scram-random', category: 'network', effects: new Set(['network']) },
  { id: 'pg-open-scram-cancellable-random', category: 'network', effects: new Set(['network']) },
  { id: 'pg-cancel-authority-use', category: 'network', effects: new Set(['network']) },
  { id: 'pg-close-scram', category: 'network', effects: new Set(['network']) },
  { id: 'http-write', category: 'component-http', effects: new Set(['network', 'write']) },
  { id: 'http-read', category: 'component-http', effects: new Set(['network']) },
  { id: 'http-close', category: 'component-http', effects: new Set(['network', 'write']) },
  { id: 'http-get', category: 'component-http', effects: new Set(['network', 'write']) },
  { id: 'db-open', category: 'component-database', effects: new Set(['network']) },
  { id: 'db-write', category: 'component-database', effects: new Set(['network', 'write']) },
  { id: 'db-read', category: 'component-database', effects: new Set(['network']) },
  { id: 'db-close', category: 'component-database', effects: new Set(['network', 'write']) },
  { id: 'db-exchange', category: 'component-database', effects: new Set(['network', 'write']) },
];

const IMPORT_BY_ID = new Map(IMPORT_SURFACE.map((i) => [i.id, i]));

export const DEFAULT_RUNTIME_LIMITS = {
  maxImports: IMPORT_SURFACE.length,
  maxHttpPosts: 0,
  maxHttpGets: 0,
  httpUrlAllowlist: [],
  transportEndpointAllowlist: [],
  transportResolvedAddressAllowlist: [],
  maxTransportConnectMs: 5000,
  maxTransportReadMs: 5000,
  maxTransportReadBytes: 1048576,
  maxTransportWriteBytes: 1048576,
  maxPgCancelRequests: 0,
  maxScramProofs: 0,
  maxPgCancelHandles: 0,
  maxHttpFetches: 0,
  maxLlmInfers: 0,
  // Finite kagi-sign invocation quota. Default 0 = deny-by-default.
  maxKagiSigns: 0,
  // CSPRNG fill quota (bytes). Default 0 = deny-by-default until raised
  // (matches kototama.contract `:max-random-bytes` 0).
  maxRandomBytes: 0,
  // Transport inject quota (handles). Default 0 = deny-by-default until
  // HostCaps raises it (same pattern as maxHttpPosts / maxKagiSigns).
  maxTransportConnections: 0,
  maxLogReadBytes: 1048576,
  maxLogWriteBytes: 65536,
  // 16 Wasm pages (64 KiB/page) = 1 MiB -- same value and rationale as
  // kototama.contract's `default-runtime-limits` :max-memory-pages
  // (contract.cljc:226). kototama.tender (JVM/Chicory) enforces this
  // PREVENTIVELY at instantiation time via Chicory's stable
  // `Instance.Builder/withMemoryLimits` (tender.clj:557-572,646-651),
  // capping how far a guest's OWN `memory.grow` can reach before the
  // engine itself refuses the grow. There is no browser/Node equivalent:
  // kotoba-wasm-emitted modules EXPORT their own memory (not host-import
  // it -- see `instance.exports.memory` throughout this repo's *-element.js
  // / *-worker-host.js), and the standard `WebAssembly.instantiate` JS API
  // gives the host no hook to override a module's own declared memory
  // ceiling. So this is enforced REACTIVELY here instead: every gated
  // host-import call below re-checks current page count via
  // `memoryPagesUsed`/`ensureMemoryWithinCap` and denies (-1) once over
  // budget, same in-band convention `maxLogReadBytes`-adjacent limits use.
  // This is real protection for the common case (a guest that grows memory
  // then calls back into the host), but NOT for a guest that blows past
  // the cap in one shot and never calls a host import again -- a genuine
  // residual gap, not an oversight (see `memoryWithinCap`'s doc comment
  // for the instantiation-time check that closes part of it).
  maxMemoryPages: 16,
  // null/undefined = unrestricted (the default -- preserves prior behavior
  // for every existing caller that never set this). When a non-empty
  // array, http-post is allowed only to URLs starting with one of these
  // prefixes -- mirrors kototama.contract's :allowed-url-prefixes /
  // url-allowed? 1:1 (same opt-in, fail-closed, per-call semantics; see
  // urlAllowed below). NOT checked by validateImportSurface, same reason
  // maxLogReadBytes-adjacent limits aren't: it doesn't gate whether the
  // import is granted, only which URLs a granted call may reach.
  allowedUrlPrefixes: null,
  allowSecretImports: false,
  allowWriteImports: false,
};

/**
 * true iff url is permitted under limits.allowedUrlPrefixes.
 * null/undefined/empty allowedUrlPrefixes means unrestricted (the default).
 *
 * Note: this is the only http-post hardening layer implemented here.
 * kototama.tender (the JVM host) additionally runs an unconditional
 * denylist against loopback/private/link-local/metadata destinations by
 * resolving the hostname via java.net.InetAddress before connecting; a
 * browser tab has no equivalent synchronous (or even straightforward
 * async) DNS-resolution API to port that check to, so that layer is NOT
 * mirrored here -- a real gap, not an oversight, left for a dedicated
 * follow-up rather than a rushed partial port.
 */
export function urlAllowed(limits, url) {
  const prefixes = limits && limits.allowedUrlPrefixes;
  if (prefixes == null) return true;
  if (prefixes.length === 0) return false;
  return prefixes.some((p) => url.startsWith(p));
}

/**
 * Current wasm linear-memory size, in 64 KiB pages. 0 before
 * `memoryBox.memory` is set (pre-instantiation) -- callers past that point
 * always have a real `WebAssembly.Memory` there. Uses division rather than
 * a `>>> 16` shift so a memory at exactly the wasm32 4 GiB ceiling doesn't
 * wrap through ToUint32.
 */
export function memoryPagesUsed(memoryBox) {
  const buf = memoryBox && memoryBox.memory && memoryBox.memory.buffer;
  return buf ? Math.floor(buf.byteLength / 65536) : 0;
}

/**
 * true iff the guest's CURRENT linear-memory size is within
 * `caps.limits.maxMemoryPages`. Callers that own the instantiate/call
 * sequence (kotoba-wasm-worker-host.js) use this right after
 * `memoryBox.memory = instance.exports.memory` and BEFORE calling the
 * guest's export, to refuse a guest that already declares an
 * over-budget memory section -- the one preventive check available
 * without engine-level support (see `maxMemoryPages`'s doc comment for
 * why growth DURING a call can only be checked reactively, per-call,
 * not prevented).
 */
export function memoryWithinCap(memoryBox, caps) {
  const c = hostCaps(caps);
  return memoryPagesUsed(memoryBox) <= c.limits.maxMemoryPages;
}

export const DEFAULT_HOST_CAPS = {
  namespace: ACTOR_HOST_NAMESPACE,
  version: ACTOR_HOST_VERSION,
  grants: new Set(),
  limits: DEFAULT_RUNTIME_LIMITS,
};

// hostCaps/validateImportSurface mirror kototama.contract/host-caps and
// kototama.contract/validate-import-surface field-for-field (grants
// normalized to known ids, limits merged over defaults, same error shapes:
// `imports/unknown`, `grants/missing`, `limit/max-imports`,
// `limit/max-http-posts`, `limit/secret-imports`, `limit/write-imports`).

export function hostCaps(m = {}) {
  const limits = { ...DEFAULT_RUNTIME_LIMITS, ...(m.limits || {}) };
  const grants = new Set([...(m.grants || [])].filter((id) => IMPORT_BY_ID.has(id)));
  return { ...DEFAULT_HOST_CAPS, ...m, grants, limits };
}

export function validateImportSurface(requestedIds, caps) {
  const c = hostCaps(caps);
  const unknown = requestedIds.filter((id) => !IMPORT_BY_ID.has(id));
  const known = requestedIds.filter((id) => IMPORT_BY_ID.has(id));
  const missing = known.filter((id) => !c.grants.has(id));
  const errors = [];
  if (unknown.length) errors.push({ error: 'imports/unknown', imports: unknown });
  if (missing.length) errors.push({ error: 'grants/missing', imports: missing });
  if (known.length > c.limits.maxImports) {
    errors.push({ error: 'limit/max-imports', limit: c.limits.maxImports, actual: known.length });
  }
  const httpPosts = known.filter((id) => id === 'http-post').length;
  const httpFetches = known.filter((id) => id === 'http-fetch').length;
  if (httpFetches > c.limits.maxHttpFetches) {
    errors.push({ error: 'limit/max-http-fetches', limit: c.limits.maxHttpFetches, actual: httpFetches });
  }
  const headerPosts = known.filter((id) => id === 'http-post-headers').length;
  if (httpPosts + headerPosts > c.limits.maxHttpPosts) {
    errors.push({
      error: 'limit/max-http-posts',
      limit: c.limits.maxHttpPosts,
      actual: httpPosts + headerPosts,
    });
  }
 const httpGets = known.filter((id) => id === 'http-get').length;
 if (httpGets > c.limits.maxHttpGets) {
   errors.push({ error: 'limit/max-http-gets', limit: c.limits.maxHttpGets, actual: httpGets });
 }

  const llmInfers = known.filter((id) => id === 'llm-infer').length;
  if (llmInfers > c.limits.maxLlmInfers) {
    errors.push({ error: 'limit/max-llm-infers', limit: c.limits.maxLlmInfers, actual: llmInfers });
  }
  const kagiSigns = known.filter((id) => id === 'kagi-sign').length;
  if (kagiSigns > c.limits.maxKagiSigns) {
    errors.push({ error: 'limit/max-kagi-signs', limit: c.limits.maxKagiSigns, actual: kagiSigns });
  }
  const transportConnects = known.filter((id) => id === 'transport-connect').length;
  if (transportConnects > c.limits.maxTransportConnections) {
    errors.push({
      error: 'limit/max-transport-connections',
      limit: c.limits.maxTransportConnections,
      actual: transportConnects,
    });
  }
  const secretImports = known.filter((id) => IMPORT_BY_ID.get(id).effects.has('secret'));
  if (!c.limits.allowSecretImports && secretImports.length) {
    errors.push({ error: 'limit/secret-imports', imports: secretImports });
  }
  const writeImports = known.filter((id) => IMPORT_BY_ID.get(id).effects.has('write'));
  if (!c.limits.allowWriteImports && writeImports.length) {
    errors.push({ error: 'limit/write-imports', imports: writeImports });
  }
  return { ok: errors.length === 0, requested: known, granted: c.grants, limits: c.limits, errors };
}

function httpUrlAllowed(allowlist, requestUrl) {
  if (!Array.isArray(allowlist) || allowlist.length === 0) return false;
  let requested;
  try {
    requested = new URL(requestUrl);
    if (requested.protocol !== 'https:' || requested.username || requested.password || requested.hash) return false;
  } catch (_) {
    return false;
  }
  return allowlist.some((entry) => {
    try {
      const scope = new URL(entry);
      if (scope.protocol !== 'https:' || scope.username || scope.password || scope.search || scope.hash) return false;
      const scopePort = Number(scope.port || 443);
      const scopePath = scope.pathname || '/';
      const pathAllowed = requested.pathname === scopePath ||
        (scopePath.endsWith('/') ? requested.pathname.startsWith(scopePath) : requested.pathname.startsWith(`${scopePath}/`));
      return scope.hostname === requested.hostname &&
        scopePort === Number(requested.port || 443) && pathAllowed;
    } catch (_) {
      return false;
    }
  });
}

function httpGetAllowed(allowlist, host, port, requestPath) {
  if (typeof host !== 'string' || !/^[A-Za-z0-9.-]+$/.test(host) ||
      !Number.isInteger(port) || port < 1 || port > 65535 ||
      typeof requestPath !== 'string' || !requestPath.startsWith('/')) return false;
  return httpUrlAllowed(allowlist, `https://${host}:${port}${requestPath}`);
}

// ---------------------------------------------------------------------------
// Hand-rolled synchronous SHA-256 (FIPS 180-4), zero dependencies -- Web
// Crypto's `crypto.subtle.digest` is async, unusable inside a synchronous
// Wasm host import (see the scope note above).

const SHA256_K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

function rotr(x, n) {
  return (x >>> n) | (x << (32 - n));
}

/** Bytes (Uint8Array) -> 32-byte SHA-256 digest (Uint8Array). */
export function sha256(bytes) {
  const bitLen = bytes.length * 8;
  const padLen = (((bytes.length + 9 + 63) >> 6) << 6);
  const padded = new Uint8Array(padLen);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(padLen - 4, bitLen >>> 0, false);
  view.setUint32(padLen - 8, Math.floor(bitLen / 0x100000000), false);

  let h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
  let h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;

  const w = new Uint32Array(64);
  for (let chunk = 0; chunk < padLen; chunk += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(chunk + i * 4, false);
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
    }
    let a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;
    for (let i = 0; i < 64; i++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const temp1 = (h + S1 + ch + SHA256_K[i] + w[i]) >>> 0;
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + maj) >>> 0;
      h = g; g = f; f = e; e = (d + temp1) >>> 0;
      d = c; c = b; b = a; a = (temp1 + temp2) >>> 0;
    }
    h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0; h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0; h5 = (h5 + f) >>> 0; h6 = (h6 + g) >>> 0; h7 = (h7 + h) >>> 0;
  }

  const out = new Uint8Array(32);
  const outView = new DataView(out.buffer);
  [h0, h1, h2, h3, h4, h5, h6, h7].forEach((v, i) => outView.setUint32(i * 4, v, false));
  return out;
}

export function sha256Hex(bytes) {
  return Array.from(sha256(bytes)).map((b) => b.toString(16).padStart(2, '0')).join('');
}

// ---------------------------------------------------------------------------
// An injectable, synchronous byte log store -- same role kgraph.js's `store`
// parameter plays, kept outside this module rather than owning a backend
// (kototama's own README stance: don't become the semantic authority).

export function inMemoryStore() {
  let buf = new Uint8Array(0);
  return {
    read: () => buf,
    append: (bytes) => {
      const next = new Uint8Array(buf.length + bytes.length);
      next.set(buf);
      next.set(bytes, buf.length);
      buf = next;
    },
  };
}

// ---------------------------------------------------------------------------
// The (module "kotoba") host imports, wired exactly like kgraph.js's
// kgraphHostImports: `memoryBox` is a mutable `{memory}` holder populated
// with `instance.exports.memory` AFTER `WebAssembly.instantiate` resolves.
//
// Fail-closed, two layers, matching kototama.tender's (JVM) design:
//   1. PRE-FLIGHT: validateImportSurface runs here, before any host
//      function is even constructed -- throws if not `ok`, so
//      `KotobaWasmElement.createImports` (which calls this) throws before
//      `WebAssembly.instantiateStreaming` ever runs, and its own
//      try/catch renders the error -- no separate wiring needed.
//   2. PER-CALL: each host function re-checks its own grant (defense in
//      depth) via `ensureGranted`.
// RuntimeLimits exhaustion (`maxLogReadBytes`/`maxLogWriteBytes`) is an
// in-band `-1`, same convention `writeBytes`'s overflow case uses -- NOT a
// thrown error -- so a well-behaved guest can see it and back off, exactly
// like `kototama.tender`'s distinction between a hard-thrown grant
// violation and a soft quota signal.
// ── Codec helpers: a byte-for-byte JS port of kototama.tender's (JVM)
// flat-pairs wire format and CBOR/JSON encoders. The guest-facing wire
// format is ONE `key<TAB>value` pair per LF-separated line, in the guest's
// own order; a key MAY be a dot-separated path ("s.t", "resources.0") for
// one interpretation of object/array nesting. This is deliberately NOT a
// general codec: only flat string->string maps (with dotted-path nesting)
// are representable. Every function below mirrors the same-named Clojure
// helper in `kototama/src/kototama/tender.clj`; keep them byte-identical.

const utf8Encoder = new TextEncoder();

// `parse-flat-pairs`: one `key<TAB>value` pair per non-blank line; a
// non-blank line with no TAB is fail-soft dropped. Order preserved.
function parseFlatPairs(s) {
  const pairs = [];
  for (const line of s.split('\n')) {
    if (line.trim() === '') continue;
    const i = line.indexOf('\t');
    if (i < 0) continue;
    pairs.push([line.slice(0, i), line.slice(i + 1)]);
  }
  return pairs;
}

function numericKey(s) {
  return /^\d+$/.test(s);
}

// `array-entries?`: entries (vector of [key,val]) has EXACTLY keys
// "0".."(count-1)" in any order.
function arrayEntries(entries) {
  if (entries.length === 0) return false;
  const ints = new Set();
  for (const [k] of entries) {
    if (!numericKey(k)) return false;
    ints.add(Number.parseInt(k, 10));
  }
  if (ints.size !== entries.length) return false;
  for (let i = 0; i < entries.length; i++) if (!ints.has(i)) return false;
  return true;
}

// `object-entries-assoc`: replace SEG's value in place, or append.
function objectEntriesAssoc(entries, seg, value) {
  for (let i = 0; i < entries.length; i++) {
    if (entries[i][0] === seg) {
      entries[i] = [seg, value];
      return entries;
    }
  }
  entries.push([seg, value]);
  return entries;
}

// `assoc-path!`: insert VALUE at PATH (array of segments) into ENTRIES,
// creating intermediate object-shaped subtrees (arrays of pairs).
function assocPath(entries, path, value) {
  const [seg, ...more] = path;
  if (more.length > 0) {
    let existing;
    for (const [k, v] of entries) if (k === seg) { existing = v; break; }
    const child = Array.isArray(existing) ? existing : [];
    return objectEntriesAssoc(entries, seg, assocPath(child, more, value));
  }
  return objectEntriesAssoc(entries, seg, value);
}

// `build-nested-tree`: fold pairs into an ordered tree of [key,val] pairs.
function buildNestedTree(pairs) {
  let entries = [];
  for (const [k, v] of pairs) entries = assocPath(entries, k.split('.'), v);
  return entries;
}

// `cbor-head`: definite-length CBOR head for MAJOR type and count N.
function cborHead(out, major, n) {
  if (n < 24) out.push((major << 5) + n);
  else if (n < 256) { out.push((major << 5) + 24); out.push(n); }
  else if (n < 65536) {
    out.push((major << 5) + 25);
    out.push((n >>> 8) & 0xff);
    out.push(n & 0xff);
  } else throw new Error('cbor len too big');
}

function cborString(out, s) {
  const b = utf8Encoder.encode(s);
  cborHead(out, 3, b.length);
  for (const byte of b) out.push(byte);
}

// `tree-node->cbor`: string leaf; non-top array node -> major 4 in ascending
// numeric-key order; else major 5 map in guest order.
function treeNodeToCbor(out, node, topLevel) {
  if (typeof node === 'string') { cborString(out, node); return; }
  if (!topLevel && arrayEntries(node)) {
    const items = [...node].sort((a, b) => Number.parseInt(a[0], 10) - Number.parseInt(b[0], 10)).map((e) => e[1]);
    cborHead(out, 4, items.length);
    for (const item of items) treeNodeToCbor(out, item, false);
    return;
  }
  cborHead(out, 5, node.length);
  for (const [k, v] of node) { cborString(out, k); treeNodeToCbor(out, v, false); }
}

function cborPairsBytes(pairs) {
  const out = [];
  treeNodeToCbor(out, buildNestedTree(pairs), true);
  return new Uint8Array(out);
}

// `json-escape`: iterate UTF-16 code units (Java `char`), short escapes for
// "/\/newline/return/tab, `\uXXXX` for other C0 controls, else pass through.
function jsonEscape(s) {
  let sb = '';
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    const code = s.charCodeAt(i);
    if (ch === '"') sb += '\\"';
    else if (ch === '\\') sb += '\\\\';
    else if (ch === '\n') sb += '\\n';
    else if (ch === '\r') sb += '\\r';
    else if (ch === '\t') sb += '\\t';
    else if (code < 0x20) sb += '\\u' + code.toString(16).padStart(4, '0');
    else sb += ch;
  }
  return sb;
}

// `tree-node->json`: string leaf (escaped+quoted); non-top array node -> JSON
// array in ascending numeric-key order; else JSON object in guest order.
function treeNodeToJson(node, topLevel) {
  if (typeof node === 'string') return '"' + jsonEscape(node) + '"';
  if (!topLevel && arrayEntries(node)) {
    const items = [...node].sort((a, b) => Number.parseInt(a[0], 10) - Number.parseInt(b[0], 10)).map((e) => e[1]);
    return '[' + items.map((it) => treeNodeToJson(it, false)).join(',') + ']';
  }
  return '{' + node.map(([k, v]) => '"' + jsonEscape(k) + '":' + treeNodeToJson(v, false)).join(',') + '}';
}

function jsonPairsBytes(pairs) {
  return utf8Encoder.encode(treeNodeToJson(buildNestedTree(pairs), true));
}

// `json-string-field-value`: bounded scan for `"FIELD":"..."`. Returns the
// unescaped value string, or null when absent/non-string/malformed.
function jsonStringFieldValue(jsonText, field) {
  const needle = '"' + field + '"';
  const keyIdx = jsonText.indexOf(needle);
  if (keyIdx < 0) return null;
  const colonIdx = jsonText.indexOf(':', keyIdx + needle.length);
  if (colonIdx < 0) return null;
  const n = jsonText.length;
  let i = colonIdx + 1;
  // skip ASCII whitespace; require an opening quote
  while (i < n && /\s/.test(jsonText[i])) i++;
  if (i >= n || jsonText[i] !== '"') return null;
  i += 1;
  let sb = '';
  while (i < n) {
    const ch = jsonText[i];
    if (ch === '\\') {
      if (i + 1 >= n) return null;
      const esc = jsonText[i + 1];
      const unescaped = esc === '"' ? '"' : esc === '\\' ? '\\' : esc === 'n' ? '\n'
        : esc === 'r' ? '\r' : esc === 't' ? '\t' : esc;
      sb += unescaped;
      i += 2;
    } else if (ch === '"') {
      return sb;
    } else {
      sb += ch;
      i += 1;
    }
  }
  return null;
}

export function sessionAuthority(grants, useBudgets = {}) {
  const active = new Set(grants || []);
  const revoked = new Set();
  const dropped = new Set();
  const consumed = new Set();
  const uses = new Map();
  const remaining = new Map(
    Object.entries(useBudgets).map(([id, value]) => {
      if (!Number.isSafeInteger(value) || value <= 0) {
        throw new Error(`kototama actor-host: invalid use budget for ${id}`);
      }
      return [id, value];
    })
  );

  const deactivate = (id, disposition) => {
    active.delete(id);
    disposition.add(id);
  };

  return Object.freeze({
    consume(id) {
      if (!active.has(id)) {
        throw new Error(`kototama actor-host: ${id} denied (grant/inactive)`);
      }
      const left = remaining.get(id);
      if (left !== undefined) {
        if (left <= 0) {
          deactivate(id, consumed);
          throw new Error(`kototama actor-host: ${id} denied (grant/exhausted)`);
        }
        remaining.set(id, left - 1);
        if (left === 1) deactivate(id, consumed);
      }
      uses.set(id, (uses.get(id) || 0) + 1);
    },
    revoke(id) { deactivate(id, revoked); },
    drop(id) { deactivate(id, dropped); },
    snapshot() {
      return {
        active: new Set(active), revoked: new Set(revoked),
        dropped: new Set(dropped), consumed: new Set(consumed),
        uses: new Map(uses), remaining: new Map(remaining),
      };
    },
  });
}

export function actorHostImports(requestedIds, caps, memoryBox, opts = {}) {
  const c = hostCaps(caps);
  const validation = validateImportSurface(requestedIds, c);
  if (!validation.ok) {
    throw new Error(`kototama actor-host: import surface rejected: ${JSON.stringify(validation.errors)}`);
  }

  const store = opts.store || inMemoryStore();
  const state = {
    logReadBytes: 0, logWriteBytes: 0, randomBytes: 0, httpPosts: 0, httpFetches: 0,
    llmInfers: 0, kagiSigns: 0, httpGets: 0
  };
  const available = new Set(validation.requested);
  const authority = opts.authority || sessionAuthority(c.grants);

  const readBytes = (ptr, len) => new Uint8Array(memoryBox.memory.buffer, ptr, len).slice();
  const writeBytes = (ptr, cap, bytes) => {
    if (bytes.length > cap) return -1;
    new Uint8Array(memoryBox.memory.buffer, ptr, bytes.length).set(bytes);
    return bytes.length;
  };
  const ensureGranted = (id) => {
    authority.consume(id);
  };
  // Reactive counterpart to `maxMemoryPages` (see its doc comment on
  // DEFAULT_RUNTIME_LIMITS for why this can't be preventive here). Every
  // host-import below that has an in-band denial value checks this FIRST,
  // same "cheapest check first" ordering `ensureGranted` already has
  // relative to the rest of each function body. Skipped by
  // `clock_monotonic` (no denial value in its return shape, and it writes
  // no attacker-controlled bytes into guest memory, so gating it adds no
  // real protection).
  const overMemoryCap = () => memoryPagesUsed(memoryBox) > c.limits.maxMemoryPages;

  const fns = {};

  if (available.has('clock-monotonic')) {
    fns.clock_monotonic = () => {
      ensureGranted('clock-monotonic');
      return BigInt(Date.now());
    };
  }

  // `(out-ptr out-cap) -> bytes-written|-1`. Fills out-cap random bytes via
  // Web Crypto CSPRNG (or opts.randomBytes for deterministic tests).
  // `#{crypto, write}` — requires grant + allowWriteImports and is metered
  // against maxRandomBytes (default 0 = deny). Caps single fill at 4096.
  if (available.has('random-bytes')) {
    fns.random_bytes = (outPtr, outCap) => {
      ensureGranted('random-bytes');
      if (outCap <= 0 || outCap > 4096 || state.randomBytes + outCap > c.limits.maxRandomBytes) return -1;
      const bytes = new Uint8Array(outCap);
      if (typeof opts.randomBytes === 'function') {
        const supplied = opts.randomBytes(outCap);
        if (!(supplied instanceof Uint8Array) || supplied.length !== outCap) return -1;
        bytes.set(supplied);
      } else {
        globalThis.crypto.getRandomValues(bytes);
      }
      state.randomBytes += outCap;
      return writeBytes(outPtr, outCap, bytes);
    };
  }

  if (available.has('sha256-hex')) {
    fns.sha256_hex = (ptr, len, outPtr, outCap) => {
      ensureGranted('sha256-hex');
      if (overMemoryCap()) return -1;
      const hex = sha256Hex(readBytes(ptr, len));
      return writeBytes(outPtr, outCap, new TextEncoder().encode(hex));
    };
  }

  // `(ref-ptr ref-len msg-ptr msg-len out-ptr out-cap) -> written|-1`.
  // Decision-aware trusted adapter only — links when opts.runtime === 'node'
  // and opts.kagiSigner.authorizedSign + non-empty opts.kagiDecisions are set.
  // Key never enters the guest; default maxKagiSigns 0 deny-by-default.
  if (available.has('kagi-sign') && opts.runtime === 'node'
      && typeof opts.kagiSigner?.authorizedSign === 'function'
      && Array.isArray(opts.kagiDecisions) && opts.kagiDecisions.length > 0) {
    fns.kagi_sign = (refPtr, refLen, msgPtr, msgLen, outPtr, outCap) => {
      ensureGranted('kagi-sign');
      if (state.kagiSigns >= c.limits.maxKagiSigns
          || refLen <= 0 || refLen > 255
          || msgLen < 0 || msgLen > 65536) return -1;
      try {
        const ref = new TextDecoder('utf-8', { fatal: true }).decode(readBytes(refPtr, refLen));
        const signature = opts.kagiSigner.authorizedSign(
          opts.kagiDecisions, ref, readBytes(msgPtr, msgLen));
        if (!(signature instanceof Uint8Array)) return -1;
        const written = writeBytes(outPtr, outCap, signature);
        if (written >= 0) state.kagiSigns += 1;
        return written;
      } catch (_) {
        return -1;
      }
    };
  }

  // ── Transport/TLS Node inject (T8.4) ─────────────────────────────────
  // Browser: intentional absence (native boundary). Node: fail-closed
  // defaults that never open sockets; opts.transportProvider may override
  // individual methods. Handles are BigInt; 0n means deny/missing.
  // Quota: maxTransportConnections (default 0 deny-by-default).
  if (opts.runtime === 'node' || opts.transport || opts.transportProvider) {
    const tp = opts.transportProvider || opts.transport || {};
    const transportState = { nextHandle: 1n, open: new Set() };
    const takeHandle = () => {
      if (transportState.open.size >= c.limits.maxTransportConnections) return 0n;
      const h = transportState.nextHandle;
      transportState.nextHandle += 1n;
      transportState.open.add(h);
      return h;
    };
    if (available.has('transport-connect')) {
      fns.transport_connect = (hostPtr, hostLen, port) => {
        ensureGranted('transport-connect');
        if (overMemoryCap()) return 0n;
        if (hostLen <= 0 || hostLen > 255 || port < 0 || port > 65535) return 0n;
        if (typeof tp.connect === 'function') {
          try {
            const host = new TextDecoder('utf-8', { fatal: true }).decode(readBytes(hostPtr, hostLen));
            const h = tp.connect(host, port | 0);
            return typeof h === 'bigint' ? h : BigInt(h || 0);
          } catch (_) {
            return 0n;
          }
        }
        // Fail-closed default: no real socket; empty allowlist semantics → 0.
        return 0n;
      };
    }
    if (available.has('tls-open')) {
      fns.tls_open = (handle, namePtr, nameLen) => {
        ensureGranted('tls-open');
        if (overMemoryCap()) return 0n;
        if (typeof tp.tlsOpen === 'function') {
          try {
            const name = nameLen > 0
              ? new TextDecoder('utf-8', { fatal: true }).decode(readBytes(namePtr, nameLen))
              : '';
            const h = tp.tlsOpen(handle, name);
            return typeof h === 'bigint' ? h : BigInt(h || 0);
          } catch (_) {
            return 0n;
          }
        }
        // Invalid/unknown TCP handle → 0 (match JVM inject fail-closed).
        return 0n;
      };
    }
    if (available.has('tls-server-end-point')) {
      fns.tls_server_end_point = (handle, outPtr, outCap) => {
        ensureGranted('tls-server-end-point');
        if (overMemoryCap()) return -1;
        if (typeof tp.tlsServerEndPoint === 'function') {
          try {
            return tp.tlsServerEndPoint(handle, outPtr, outCap, { writeBytes, readBytes }) | 0;
          } catch (_) {
            return -1;
          }
        }
        return -1;
      };
    }
    if (available.has('transport-write')) {
      fns.transport_write = (handle, ptr, len) => {
        ensureGranted('transport-write');
        if (overMemoryCap()) return -1;
        if (typeof tp.write === 'function') {
          try {
            return tp.write(handle, readBytes(ptr, len)) | 0;
          } catch (_) {
            return -1;
          }
        }
        return -1;
      };
    }
    if (available.has('transport-read')) {
      fns.transport_read = (handle, ptr, cap) => {
        ensureGranted('transport-read');
        if (overMemoryCap()) return -1;
        if (typeof tp.read === 'function') {
          try {
            const bytes = tp.read(handle, cap);
            if (!(bytes instanceof Uint8Array)) return -1;
            return writeBytes(ptr, cap, bytes);
          } catch (_) {
            return -1;
          }
        }
        return -1;
      };
    }
    if (available.has('transport-close')) {
      fns.transport_close = (handle) => {
        ensureGranted('transport-close');
        if (typeof tp.close === 'function') {
          try {
            return tp.close(handle) | 0;
          } catch (_) {
            return -1;
          }
        }
        // Unknown handle → -1 (match JVM inject).
        return -1;
      };
    }
  }

  // ── PostgreSQL pool / wire / cancel / SCRAM Node inject (T8.4) ─────
  // Browser: intentional absence. Node: fail-closed defaults (no real PG);
  // optional opts.pgPoolProvider / opts.pgWireProvider / opts.scramCredentials.
  if (opts.runtime === 'node' || typeof opts.credentials?.scramSha256 === 'function') {
    const poolP = opts.pgPoolProvider || {};
    const wireP = opts.pgWireProvider || {};
    const denyI32 = () => -1;
    const denyI64 = () => 0n;

    const wirePool = (id, field, impl) => {
      if (!available.has(id)) return;
      fns[field] = (...args) => {
        ensureGranted(id);
        if (overMemoryCap()) return field.includes('open') && !field.includes('pool') ? 0n : -1;
        try {
          return impl(...args);
        } catch (_) {
          return field === 'pg_open' ? 0n : -1;
        }
      };
    };

    // Pool — i32 handles; fail-closed unknown → -1; open → -1 (no SCRAM/PG).
    if (available.has('pg-pool-open')) {
      fns.pg_pool_open = (hPtr, hLen, port, uPtr, uLen, dPtr, dLen, cPtr, cLen) => {
        ensureGranted('pg-pool-open');
        if (overMemoryCap()) return -1;
        if (typeof poolP.open === 'function') {
          try {
            return poolP.open({
              host: new TextDecoder().decode(readBytes(hPtr, hLen)),
              port: port | 0,
              user: new TextDecoder().decode(readBytes(uPtr, uLen)),
              database: new TextDecoder().decode(readBytes(dPtr, dLen)),
              credential: new TextDecoder().decode(readBytes(cPtr, cLen)),
            }) | 0;
          } catch (_) { return -1; }
        }
        return -1;
      };
    }
    if (available.has('pg-pool-acquire')) {
      fns.pg_pool_acquire = (poolId) => {
        ensureGranted('pg-pool-acquire');
        if (typeof poolP.acquire === 'function') {
          try { return poolP.acquire(poolId | 0) | 0; } catch (_) { return -1; }
        }
        return -1;
      };
    }
    if (available.has('pg-pool-query')) {
      fns.pg_pool_query = (lease, qPtr, qLen, pPtr, pCap, oPtr, oCap) => {
        ensureGranted('pg-pool-query');
        if (overMemoryCap()) return -1;
        if (typeof poolP.query === 'function') {
          try {
            return poolP.query(lease | 0, readBytes(qPtr, qLen), pPtr, pCap, oPtr, oCap) | 0;
          } catch (_) { return -1; }
        }
        return -1;
      };
    }
    if (available.has('pg-pool-release')) {
      fns.pg_pool_release = (lease) => {
        ensureGranted('pg-pool-release');
        if (typeof poolP.release === 'function') {
          try { return poolP.release(lease | 0) | 0; } catch (_) { return -1; }
        }
        return -1;
      };
    }
    if (available.has('pg-pool-stats')) {
      fns.pg_pool_stats = (poolId, outPtr, outCap) => {
        ensureGranted('pg-pool-stats');
        if (overMemoryCap()) return -1;
        if (typeof poolP.stats === 'function') {
          try { return poolP.stats(poolId | 0, outPtr, outCap) | 0; } catch (_) { return -1; }
        }
        return -1;
      };
    }
    if (available.has('pg-pool-health')) {
      fns.pg_pool_health = (poolId) => {
        ensureGranted('pg-pool-health');
        if (typeof poolP.health === 'function') {
          try { return poolP.health(poolId | 0) | 0; } catch (_) { return -1; }
        }
        return -1;
      };
    }
    if (available.has('pg-pool-drain')) {
      fns.pg_pool_drain = (poolId) => {
        ensureGranted('pg-pool-drain');
        if (typeof poolP.drain === 'function') {
          try { return poolP.drain(poolId | 0) | 0; } catch (_) { return -1; }
        }
        return -1;
      };
    }
    if (available.has('pg-pool-close')) {
      fns.pg_pool_close = (poolId) => {
        ensureGranted('pg-pool-close');
        if (typeof poolP.close === 'function') {
          try { return poolP.close(poolId | 0) | 0; } catch (_) { return -1; }
        }
        return -1;
      };
    }

    // Wire — handle 0 / -1 fail-closed.
    if (available.has('pg-open')) {
      fns.pg_open = (hPtr, hLen, port, uPtr, uLen, dPtr, dLen) => {
        ensureGranted('pg-open');
        if (overMemoryCap()) return 0n;
        if (typeof wireP.open === 'function') {
          try {
            const h = wireP.open({
              host: new TextDecoder().decode(readBytes(hPtr, hLen)),
              port: port | 0,
              user: new TextDecoder().decode(readBytes(uPtr, uLen)),
              database: new TextDecoder().decode(readBytes(dPtr, dLen)),
            });
            return typeof h === 'bigint' ? h : BigInt(h || 0);
          } catch (_) { return 0n; }
        }
        return 0n;
      };
    }
    if (available.has('pg-query')) {
      fns.pg_query = (handle, qPtr, qLen, oPtr, oCap) => {
        ensureGranted('pg-query');
        if (overMemoryCap()) return -1;
        if (typeof wireP.query === 'function') {
          try { return wireP.query(handle, readBytes(qPtr, qLen), oPtr, oCap) | 0; }
          catch (_) { return -1; }
        }
        return -1;
      };
    }
    if (available.has('pg-simple-query')) {
      fns.pg_simple_query = (_a, _b, _c, _d, _e, _f, _g) => {
        ensureGranted('pg-simple-query');
        if (overMemoryCap()) return -1;
        if (typeof wireP.simpleQuery === 'function') {
          try { return wireP.simpleQuery(_a, _b, _c, _d, _e, _f, _g) | 0; } catch (_) { return -1; }
        }
        return -1;
      };
    }

    // Cancel
    if (available.has('pg-cancel-register')) {
      fns.pg_cancel_register = (handle, a, b) => {
        ensureGranted('pg-cancel-register');
        if (typeof opts.pgCancelRegister === 'function') {
          try { return opts.pgCancelRegister(handle, a, b) | 0; } catch (_) { return 0; }
        }
        const tpCancel = opts.transportProvider || opts.transport;
        if (tpCancel && typeof tpCancel.registerCancel === 'function') {
          try { return tpCancel.registerCancel(handle, a, b) | 0; } catch (_) { return 0; }
        }
        // non-TLS handle → 0
        return 0;
      };
    }
    if (available.has('pg-cancel')) {
      fns.pg_cancel = (handle) => {
        ensureGranted('pg-cancel');
        if (typeof opts.pgCancel === 'function') {
          try { return opts.pgCancel(handle | 0) | 0; } catch (_) { return -1; }
        }
        const tpCancel = opts.transportProvider || opts.transport;
        if (tpCancel && typeof tpCancel.cancel === 'function') {
          try { return tpCancel.cancel(handle) | 0; } catch (_) { return -1; }
        }
        return -1;
      };
    }

    // SCRAM-SHA-256 purpose-bound host crypto (Node).
    // Password never enters guest; opts.scramCredentials is ref→password map
    // (or getter), opts.scramCredentialAllowlist is a Set of allowed refs.
    // Fail-closed -1 without credentials/allowlist (match JVM deny path).
    if (available.has('scram-sha256')) {
      fns.scram_sha256 = (
        refPtr, refLen, saltPtr, saltLen, iterations,
        authPtr, authLen, outPtr, outCap,
      ) => {
        ensureGranted('scram-sha256');
        if (overMemoryCap()) return -1;
        if (outCap < 64 || refLen <= 0 || refLen > 255
            || saltLen <= 0 || saltLen > 1024
            || iterations < 4096 || iterations > 1000000
            || authLen <= 0 || authLen > 8192) return -1;
        let ref;
        try {
          ref = new TextDecoder('utf-8', { fatal: true }).decode(readBytes(refPtr, refLen));
        } catch (_) { return -1; }
        const allowRaw = opts.scramCredentialAllowlist ?? c.limits.scramCredentialAllowlist;
        const allow = allowRaw instanceof Set ? allowRaw
          : (Array.isArray(allowRaw) ? new Set(allowRaw) : null);
        if (!allow || !allow.has(ref)) return -1;
        if (opts.credentials && typeof opts.credentials.scramSha256 === 'function') {
          const salt = readBytes(saltPtr, saltLen);
          const authMessage = readBytes(authPtr, authLen);
          const proof = opts.credentials.scramSha256({ credentialRef: ref, salt, iterations, authMessage });
if (!(proof instanceof Uint8Array) || proof.length < 64 || proof.length > outCap) return -1;
          state.scramProofs = (state.scramProofs || 0) + 1;
          return writeBytes(outPtr, outCap, proof);
        }
        let creds = opts.scramCredentials;
        if (typeof creds === 'function') {
          try { creds = creds(); } catch (_) { return -1; }
        }
        const secret = creds && creds[ref];
        if (secret == null || secret === '') return -1;
        // Node crypto SCRAM-SHA-256 client-proof || server-signature (64 bytes)
        try {
          // dynamic import not available sync; use globalThis.crypto.subtle is async.
          // Prefer node:crypto when available via createRequire pattern is heavy;
          // use opts.scramProve inject for success path, else compute via WebCrypto sync? No.
          // Node 19+ has global crypto with subtle async only.
          // Use createHmac/pbkdf2Sync from node:crypto via process.getBuiltinModule if present.
          const nodeCrypto = (typeof process !== 'undefined' && process.getBuiltinModule)
            ? process.getBuiltinModule('crypto')
            : null;
          if (!nodeCrypto || typeof nodeCrypto.pbkdf2Sync !== 'function') {
            if (typeof opts.scramProve === 'function') {
              const proof = opts.scramProve({
                ref,
                password: String(secret),
                salt: readBytes(saltPtr, saltLen),
                iterations: iterations | 0,
                authMessage: readBytes(authPtr, authLen),
              });
              if (!(proof instanceof Uint8Array) || proof.length !== 64) return -1;
              return writeBytes(outPtr, outCap, proof);
            }
            return -1;
          }
          const password = String(secret);
          const salt = Buffer.from(readBytes(saltPtr, saltLen));
          const authMessage = Buffer.from(readBytes(authPtr, authLen));
          const salted = nodeCrypto.pbkdf2Sync(password, salt, iterations | 0, 32, 'sha256');
          const hmac = (key, data) => nodeCrypto.createHmac('sha256', key).update(data).digest();
          const clientKey = hmac(salted, 'Client Key');
          const storedKey = nodeCrypto.createHash('sha256').update(clientKey).digest();
          const clientSignature = hmac(storedKey, authMessage);
          const clientProof = Buffer.alloc(32);
          for (let i = 0; i < 32; i++) clientProof[i] = clientKey[i] ^ clientSignature[i];
          const serverKey = hmac(salted, 'Server Key');
          const serverSignature = hmac(serverKey, authMessage);
          const out = Buffer.concat([clientProof, serverSignature]);
          return writeBytes(outPtr, outCap, new Uint8Array(out));
        } catch (_) {
          return -1;
        }
      };
    }
  }

  // ── Deeper wire + SCRAM session open (T8.4 residual) ────────────────
  // Fail-closed i32→-1 / i64 open→0n. Optional opts.pgWireProvider overrides.
  if (opts.runtime === 'node') {
    const wireDeep = opts.pgWireProvider || {};
    const denyI32 = () => -1;
    const denyI64 = () => 0n;
    const wireDeepI32 = (id, field, override) => {
      if (!available.has(id)) return;
      fns[field] = (...args) => {
        ensureGranted(id);
        if (overMemoryCap()) return -1;
        if (typeof wireDeep[override] === 'function') {
          try { return wireDeep[override](...args) | 0; } catch (_) { return -1; }
        }
        return -1;
      };
    };
    const wireDeepI64 = (id, field, override) => {
      if (!available.has(id)) return;
      fns[field] = (...args) => {
        ensureGranted(id);
        if (overMemoryCap()) return 0n;
        if (typeof wireDeep[override] === 'function') {
          try {
            const h = wireDeep[override](...args);
            return typeof h === 'bigint' ? h : BigInt(h || 0);
          } catch (_) { return 0n; }
        }
        return 0n;
      };
    };
    // prepare / execute / portal / copy / batch (i32 fail-closed)
    wireDeepI32('pg-prepare', 'pg_prepare', 'prepare');
    wireDeepI32('pg-session-reset', 'pg_session_reset', 'sessionReset');
    wireDeepI32('pg-close-statement', 'pg_close_statement', 'closeStatement');
    wireDeepI32('pg-query-state', 'pg_query_state', 'queryState');
    wireDeepI32('pg-prepare-typed', 'pg_prepare_typed', 'prepareTyped');
    wireDeepI32('pg-execute-params2', 'pg_execute_params2', 'executeParams2');
    wireDeepI32('pg-execute-params', 'pg_execute_params', 'executeParams');
    wireDeepI32('pg-bind-portal', 'pg_bind_portal', 'bindPortal');
    wireDeepI32('pg-fetch-portal', 'pg_fetch_portal', 'fetchPortal');
    wireDeepI32('pg-close-portal', 'pg_close_portal', 'closePortal');
    wireDeepI32('pg-copy-out', 'pg_copy_out', 'copyOut');
    wireDeepI32('pg-copy-in', 'pg_copy_in', 'copyIn');
    wireDeepI32('pg-execute-batch', 'pg_execute_batch', 'executeBatch');
    wireDeepI32('pg-cancel-authority-use', 'pg_cancel_authority_use', 'cancelAuthorityUse');
    wireDeepI32('pg-close-scram', 'pg_close_scram', 'closeScram');
    // SCRAM session open → handle 0
    wireDeepI64('pg-open-scram', 'pg_open_scram', 'openScram');
    wireDeepI64('pg-open-scram-random', 'pg_open_scram_random', 'openScramRandom');
    wireDeepI64('pg-open-scram-cancellable-random', 'pg_open_scram_cancellable_random', 'openScramCancellableRandom');
  }





  // `(out-ptr out-cap) -> bytes-written|-1`. Writes a fresh 32-byte Ed25519
  // seed followed by its 32-byte derived public key (64 bytes total) --
  // same wire shape kototama.tender's (JVM) `gen-keypair-host-fn` uses.
  if (available.has('gen-keypair')) {
    fns.gen_keypair = (outPtr, outCap) => {
      ensureGranted('gen-keypair');
      if (overMemoryCap()) return -1;
      const seed = ed25519.utils.randomPrivateKey();
      const pub = ed25519.getPublicKey(seed);
      const out = new Uint8Array(64);
      out.set(seed, 0);
      out.set(pub, 32);
      return writeBytes(outPtr, outCap, out);
    };
  }

  // `(seed-ptr msg-ptr msg-len out-ptr out-cap) -> bytes-written|-1`. Signs
  // MSG with the raw 32-byte seed at SEED-PTR, writes the 64-byte signature.
  if (available.has('sign')) {
    fns.sign = (seedPtr, msgPtr, msgLen, outPtr, outCap) => {
      ensureGranted('sign');
      if (overMemoryCap()) return -1;
      const seed = readBytes(seedPtr, 32);
      const msg = readBytes(msgPtr, msgLen);
      const sig = ed25519.sign(msg, seed);
      return writeBytes(outPtr, outCap, sig);
    };
  }

  // `(pub-ptr pub-len msg-ptr msg-len sig-ptr sig-len) -> 1|0`.
  if (available.has('verify')) {
    fns.verify = (pubPtr, pubLen, msgPtr, msgLen, sigPtr, sigLen) => {
      ensureGranted('verify');
      if (overMemoryCap()) return 0; // this fn's own 1|0 denial shape, not -1
      const pub = readBytes(pubPtr, pubLen);
      const msg = readBytes(msgPtr, msgLen);
      const sig = readBytes(sigPtr, sigLen);
      return ed25519.verify(sig, msg, pub) ? 1 : 0;
    };
  }

  if (available.has('log-read')) {
    fns.log_read = (outPtr, outCap) => {
      ensureGranted('log-read');
      if (overMemoryCap()) return -1;
      const bytes = store.read();
      if (state.logReadBytes + bytes.length > c.limits.maxLogReadBytes) return -1;
      state.logReadBytes += bytes.length;
      return writeBytes(outPtr, outCap, bytes);
    };
  }

  if (available.has('log-write')) {
    fns.log_write = (ptr, len) => {
      ensureGranted('log-write');
      if (overMemoryCap()) return -1;
      const bytes = readBytes(ptr, len);
      if (state.logWriteBytes + bytes.length > c.limits.maxLogWriteBytes) return -1;
      state.logWriteBytes += bytes.length;
      store.append(bytes);
      return 0;
    };
  }

  // `(prompt-ptr prompt-len out-ptr out-cap) -> bytes-written|-1`. Wired
  // whenever a synchronous backend exists -- either:
  //   - inject: `opts.llmInfer` (a synchronous `(promptString) =>
  //     string|null` function), e.g. this repo's own Node-hosted verify
  //     scripts backing it with a blocking child_process call. Never call
  //     `opts.llmInfer` from actual browser code: a synchronous XHR-style
  //     blocking call is deprecated/discouraged platform-wide there, unlike
  //     a Node `child_process` call, which has no such constraint.
  //   - SAB/COOP bridge: `opts.llmInferBridge` (the SAME bridge shape
  //     `http-post` uses, typically the identical bridge instance) plus
  //     `opts.llmInferUrl`, a developer-controlled endpoint `llm_infer`
  //     POSTs the raw prompt bytes to and reads the raw completion text
  //     back from. This is deliberately NOT a built-in call to any real LLM
  //     provider (unlike `kototama.tender`'s JVM-only, server-side
  //     `anthropic-infer`) -- a browser tab can never hold a real provider
  //     API key without shipping it to every visitor, so the provider call
  //     itself must live behind `llmInferUrl`, on a host the caller
  //     controls.
  // Runtime-metered against maxLlmInfers (in-band -1 when exhausted), same
  // convention http_post's maxHttpPosts already uses. `text === null` (no
  // backend configured, the call failed, or an empty/malformed reply) fails
  // closed as -1, same as `kototama.tender`'s `llm-infer-host-fn` never
  // distinguishing "no credential" from "call failed" in-band.
  const llmInferSync =
    typeof opts.llmInfer === 'function'
      ? opts.llmInfer
      : (opts.llmInferBridge &&
          typeof opts.llmInferBridge.postSync === 'function' &&
          typeof opts.llmInferUrl === 'string'
          ? (promptString) => {
              const resp = opts.llmInferBridge.postSync(
                opts.llmInferUrl,
                new TextEncoder().encode(promptString),
              );
              return resp == null ? null : new TextDecoder().decode(resp);
            }
          : null);

  if (available.has('llm-infer') && llmInferSync) {
    fns.llm_infer = (promptPtr, promptLen, outPtr, outCap) => {
      ensureGranted('llm-infer');
      if (overMemoryCap()) return -1;
      if (state.llmInfers >= c.limits.maxLlmInfers) return -1;
      const prompt = new TextDecoder().decode(readBytes(promptPtr, promptLen));
      let text;
      try {
        text = llmInferSync(prompt);
      } catch (_) {
        return -1;
      }
      if (text == null) return -1;
      const n = writeBytes(outPtr, outCap, new TextEncoder().encode(text));
      if (n >= 0) state.llmInfers += 1;
      return n;
    };
  }

  // `(url-ptr url-len body-ptr body-len out-ptr out-cap) -> bytes-written|-1`.
  // Wired only when a synchronous backend exists (inject or SAB bridge).
  // Runtime-metered against maxHttpPosts (in-band -1 when exhausted), and
  // against limits.allowedUrlPrefixes (opt-in, unrestricted by default;
  // see urlAllowed above) -- same in-band -1 fail-closed convention.
  const httpPostSync =
    typeof opts.httpPost === 'function'
      ? (opts.httpPost.length >= 2
          ? opts.httpPost
          : (u, b) => opts.httpPost({ url: u, body: b, maxBytes: b.length, redirect: 'manual' }))
      : (opts.httpPostBridge && typeof opts.httpPostBridge.postSync === 'function'
          ? (url, body) => opts.httpPostBridge.postSync(url, body)
          : null);

  if (available.has('http-post') && httpPostSync) {
    fns.http_post = (urlPtr, urlLen, bodyPtr, bodyLen, outPtr, outCap) => {
      ensureGranted('http-post');
      if (overMemoryCap()) return -1;
      if (state.httpPosts >= c.limits.maxHttpPosts) return -1;
      const url = new TextDecoder().decode(readBytes(urlPtr, urlLen));
      if (!urlAllowed(c.limits, url)) return -1;
      const body = readBytes(bodyPtr, bodyLen);
      let resp;
      try {
        resp = httpPostSync(url, body);
      } catch (_) {
        return -1;
      }
      if (resp == null) return -1;
      const bytes = resp instanceof Uint8Array ? resp : new TextEncoder().encode(String(resp));
      const n = writeBytes(outPtr, outCap, bytes);
      if (n >= 0) state.httpPosts += 1;
      return n;
    };
  }

  const httpFetchSync =
    typeof opts.httpFetch === 'function'
      ? opts.httpFetch
      : (opts.httpPostBridge && typeof opts.httpPostBridge.getSync === 'function'
          ? (url) => opts.httpPostBridge.getSync(url)
          : null);

  // `(url-ptr url-len out-ptr out-cap) -> bytes-written|-1`. GET-only,
  // independently granted and metered, while sharing the same destination
  // allowlist and synchronous inject/SAB transport as http_post.
  if (available.has('http-fetch') && httpFetchSync) {
    fns.http_fetch = (urlPtr, urlLen, outPtr, outCap) => {
      ensureGranted('http-fetch');
      if (overMemoryCap()) return -1;
      if (state.httpFetches >= c.limits.maxHttpFetches) return -1;
      const url = new TextDecoder().decode(readBytes(urlPtr, urlLen));
      if (!urlAllowed(c.limits, url)) return -1;
      let resp;
      try {
        resp = httpFetchSync(url);
      } catch (_) {
        return -1;
      }
      if (resp == null) return -1;
      const bytes = resp instanceof Uint8Array ? resp : utf8Encoder.encode(String(resp));
      const n = writeBytes(outPtr, outCap, bytes);
      if (n >= 0) state.httpFetches += 1;
      return n;
    };
  }

  const httpPostHeadersSync =
    typeof opts.httpPostHeaders === 'function'
      ? opts.httpPostHeaders
      : (opts.httpPostBridge && typeof opts.httpPostBridge.postHeadersSync === 'function'
          ? (url, body, headers) => opts.httpPostBridge.postHeadersSync(url, body, headers)
          : null);

  // Headers use the same key<TAB>value, LF-separated wire format as the
  // codec imports and the JVM host. It shares maxHttpPosts with http_post.
  if (available.has('http-post-headers') && httpPostHeadersSync) {
    fns.http_post_headers =
      (urlPtr, urlLen, bodyPtr, bodyLen, headersPtr, headersLen, outPtr, outCap) => {
        ensureGranted('http-post-headers');
        if (overMemoryCap()) return -1;
        if (state.httpPosts >= c.limits.maxHttpPosts) return -1;
        const url = new TextDecoder().decode(readBytes(urlPtr, urlLen));
        if (!urlAllowed(c.limits, url)) return -1;
        const body = readBytes(bodyPtr, bodyLen);
        const headerText = new TextDecoder().decode(readBytes(headersPtr, headersLen));
        const headers = parseFlatPairs(headerText);
        let resp;
        try {
          resp = httpPostHeadersSync(url, body, headers);
        } catch (_) {
          return -1;
        }
        if (resp == null) return -1;
        const bytes = resp instanceof Uint8Array ? resp : utf8Encoder.encode(String(resp));
        const n = writeBytes(outPtr, outCap, bytes);
        if (n >= 0) state.httpPosts += 1;
        return n;
      };
  }

  // Codec imports -- pure computation, byte-for-byte ports of
  // kototama.tender's JVM host fns. Not gated by any RuntimeLimits count
  // (same as sha256_hex). `(pairs-ptr pairs-len out-ptr out-cap) ->
  // bytes-written|-1`.
  if (available.has('cbor-encode')) {
    fns.cbor_encode = (ptr, len, outPtr, outCap) => {
      ensureGranted('cbor-encode');
      if (overMemoryCap()) return -1;
      const pairs = parseFlatPairs(new TextDecoder().decode(readBytes(ptr, len)));
      return writeBytes(outPtr, outCap, cborPairsBytes(pairs));
    };
  }

  if (available.has('json-encode')) {
    fns.json_encode = (ptr, len, outPtr, outCap) => {
      ensureGranted('json-encode');
      if (overMemoryCap()) return -1;
      const pairs = parseFlatPairs(new TextDecoder().decode(readBytes(ptr, len)));
      return writeBytes(outPtr, outCap, jsonPairsBytes(pairs));
    };
  }

  // `(json-ptr json-len field-ptr field-len out-ptr out-cap) ->
  // bytes-written|-1`. -1 when FIELD is absent/non-string/malformed.
  if (available.has('json-extract-field')) {
    fns.json_extract_field = (jsonPtr, jsonLen, fieldPtr, fieldLen, outPtr, outCap) => {
      ensureGranted('json-extract-field');
      if (overMemoryCap()) return -1;
      const jsonText = new TextDecoder().decode(readBytes(jsonPtr, jsonLen));
      const field = new TextDecoder().decode(readBytes(fieldPtr, fieldLen));
      const value = jsonStringFieldValue(jsonText, field);
      if (value === null) return -1;
      return writeBytes(outPtr, outCap, utf8Encoder.encode(value));
    };
  }

  // High-level component HTTP capability. Browser tabs and Node cannot expose
  // raw synchronous sockets safely, but a caller may inject a synchronous
  // fetch/SAB/worker bridge. The callback receives an exact endpoint and a
  // manual-redirect requirement; absence leaves the Wasm import unlinked.
    if (available.has('http-get') && typeof opts.httpGet === 'function') {
    fns.http_get = (hostPtr, hostLen, port, pathPtr, pathLen, outPtr, outCap) => {
      ensureGranted('http-get');
      const host = new TextDecoder('utf-8', { fatal: true }).decode(readBytes(hostPtr, hostLen));
      const requestPath = new TextDecoder('utf-8', { fatal: true }).decode(readBytes(pathPtr, pathLen));
      if (state.httpGets >= c.limits.maxHttpGets ||
          !httpGetAllowed(c.limits.httpUrlAllowlist, host, port, requestPath)) return -1;
      const reply = opts.httpGet({
        host,
        port,
        path: requestPath,
        maxBytes: outCap,
        redirect: 'manual',
      });
      if (!(reply instanceof Uint8Array)) return -1;
      state.httpGets += 1;
      return writeBytes(outPtr, outCap, reply);
    };
  }


  return fns;
}

/**
 * Detect which http-post backends are available in this environment.
 * Pure observation — does not perform network I/O.
 */
export function httpPostCapabilities() {
  const crossOriginIsolated =
    typeof globalThis.crossOriginIsolated === 'boolean'
      ? globalThis.crossOriginIsolated
      : false;
  const hasSab =
    typeof SharedArrayBuffer !== 'undefined' &&
    typeof Atomics !== 'undefined' &&
    typeof Atomics.wait === 'function';
  // JSPI: WebAssembly.promising / Suspending — Chrome experimental
  const hasJspi =
    typeof WebAssembly !== 'undefined' &&
    typeof WebAssembly.promising === 'function';
  return {
    inject: true, // always available as programming interface
    sabCoop: Boolean(crossOriginIsolated && hasSab),
    jspi: hasJspi,
    crossOriginIsolated,
    hasSharedArrayBuffer: hasSab,
    recommended: hasSab && crossOriginIsolated
      ? 'sab-coop'
      : hasJspi
        ? 'jspi-experimental'
        : 'inject',
  };
}
