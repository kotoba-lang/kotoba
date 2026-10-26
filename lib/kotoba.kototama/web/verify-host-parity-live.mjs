// T8.4 Node/browser live host runner for host-parity critical imports.
//
// Runs the same class of proofs as kototama.host-parity-live (JVM) against
// wasm-webcomponent's actor-host.js under Node's WebAssembly engine.
// Case ids align with lang/host-parity.edn where listed.
//
// Run: node web/verify-host-parity-live.mjs
// Requires: wasm-tools on PATH; network to fetch pinned actor-host sources.
import { readFile, mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { writeFileSync, readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { tmpdir } from 'node:os';
import path from 'node:path';

// Prefer sibling checkout (superproject west layout) so actor-host surface
// matches local wasm-webcomponent tip; fall back to pinned CDN commit.
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
// web/ -> kototama-t84 -> kotoba-lang siblings
const siblingActorHost = path.resolve(here, '../../wasm-webcomponent/src/actor-host.js');
// also try when this repo is named kototama (not kototama-t84)
const siblingActorHostAlt = path.resolve(here, '../../../orgs/kotoba-lang/wasm-webcomponent/src/actor-host.js');
// Includes actor-host `random-bytes` + `kagi-sign` inject (2026-07-31).
const WASM_WEBCOMPONENT_COMMIT = '1c353beaa8eb34d82511c81354f70cf63cf3f46e';
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

function watToWasm(wat, workDir) {
  const watPath = path.join(workDir, 'guest.wat');
  const wasmPath = path.join(workDir, 'guest.wasm');
  writeFileSync(watPath, wat);
  const r = spawnSync('wasm-tools', ['parse', watPath, '-o', wasmPath], { encoding: 'utf8' });
  if (r.status !== 0) {
    throw new Error(`wasm-tools parse failed: ${r.stderr || r.stdout}`);
  }
  return readFileSync(wasmPath);
}

const corpus = [
  {
    id: 'sha256-hex-all-available',
    imports: ['sha256-hex'],
    check: (n) => Number(n) === 64,
    wat: `(module
      (import "kotoba" "sha256_hex" (func $sha256_hex (param i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "hello")
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $sha256_hex (i32.const 0) (i32.const 5) (i32.const 100) (i32.const 64)))))`,
  },
  {
    id: 'clock-monotonic-all',
    imports: ['clock-monotonic'],
    check: (n) => Number(n) > 0,
    wat: `(module
      (import "kotoba" "clock_monotonic" (func $clock_monotonic (result i64)))
      (func (export "main") (result i64) (call $clock_monotonic)))`,
  },
  {
    id: 'log-write-all-available',
    imports: ['log-write'],
    check: (n) => Number(n) >= 0,
    wat: `(module
      (import "kotoba" "log_write" (func $log_write (param i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "ok")
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $log_write (i32.const 0) (i32.const 2)))))`,
  },
  {
    id: 'log-read-all-available',
    imports: ['log-read'],
    check: (n) => Number(n) >= 0,
    wat: `(module
      (import "kotoba" "log_read" (func $log_read (param i32 i32) (result i32)))
      (memory (export "memory") 1)
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $log_read (i32.const 0) (i32.const 256)))))`,
  },
  {
    id: 'gen-keypair-all-available',
    imports: ['gen-keypair'],
    check: (n) => Number(n) === 64,
    wat: `(module
      (import "kotoba" "gen_keypair" (func $gen_keypair (param i32 i32) (result i32)))
      (memory (export "memory") 1)
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $gen_keypair (i32.const 0) (i32.const 64)))))`,
  },
  {
    id: 'sign-all-available',
    imports: ['gen-keypair', 'sign'],
    check: (n) => Number(n) === 64,
    wat: `(module
      (import "kotoba" "gen_keypair" (func $gen_keypair (param i32 i32) (result i32)))
      (import "kotoba" "sign" (func $sign (param i32 i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 64) "ok")
      (func (export "main") (result i64)
        (drop (call $gen_keypair (i32.const 0) (i32.const 64)))
        (i64.extend_i32_s
          (call $sign (i32.const 0) (i32.const 64) (i32.const 2) (i32.const 128) (i32.const 64)))))`,
  },
  {
    id: 'verify-all-available',
    imports: ['gen-keypair', 'sign', 'verify'],
    check: (n) => Number(n) === 1,
    wat: `(module
      (import "kotoba" "gen_keypair" (func $gen_keypair (param i32 i32) (result i32)))
      (import "kotoba" "sign" (func $sign (param i32 i32 i32 i32 i32) (result i32)))
      (import "kotoba" "verify" (func $verify (param i32 i32 i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 64) "ok")
      (func (export "main") (result i64)
        (drop (call $gen_keypair (i32.const 0) (i32.const 64)))
        (drop (call $sign (i32.const 0) (i32.const 64) (i32.const 2) (i32.const 128) (i32.const 64)))
        (i64.extend_i32_s
          (call $verify (i32.const 32) (i32.const 32) (i32.const 64) (i32.const 2)
                        (i32.const 128) (i32.const 64)))))`,
  },
  {
    id: 'random-bytes-all-available',
    imports: ['random-bytes'],
    check: (n) => Number(n) === 16,
    wat: `(module
      (import "kotoba" "random_bytes" (func $random_bytes (param i32 i32) (result i32)))
      (memory (export "memory") 1)
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $random_bytes (i32.const 0) (i32.const 16)))))`,
  },
  {
    id: 'http-post-node-inject-available',
    imports: ['http-post'],
    // Injected host callback — no real network; proves link + inject path.
    // URL must match https allowlist entry (exact host + path prefix).
    limits: {
      maxHttpPosts: 8,
      allowedUrlPrefixes: ['https://example.test/'],
    },
    inject: { httpPost: () => new TextEncoder().encode('pong') },
    check: (n) => Number(n) === 4,
    wat: `(module
      (import "kotoba" "http_post" (func $http_post (param i32 i32 i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "https://example.test/x")
      (data (i32.const 50) "body")
      (func (export "main") (result i64)
        (i64.extend_i32_s
          (call $http_post (i32.const 0) (i32.const 22)
                           (i32.const 50) (i32.const 4)
                           (i32.const 200) (i32.const 256)))))`,
  },
  {
    id: 'llm-infer-node-available',
    imports: ['llm-infer'],
    limits: { maxLlmInfers: 2 },
    inject: { llmInfer: () => 'pong' },
    check: (n) => Number(n) === 4,
    wat: `(module
      (import "kotoba" "llm_infer" (func $llm_infer (param i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "hi")
      (func (export "main") (result i64)
        (i64.extend_i32_s
          (call $llm_infer (i32.const 0) (i32.const 2) (i32.const 100) (i32.const 64)))))`,
  },
  {
    id: 'kagi-sign-node-inject-available',
    imports: ['kagi-sign'],
    limits: { maxKagiSigns: 1 },
    inject: {
      kagiDecisions: [{ ref: 'kagi://ops/key', purpose: 'release' }],
      kagiSigner: {
        authorizedSign(_decisions, _ref, _message) {
          return new Uint8Array(64).fill(7);
        },
      },
    },
    check: (n) => Number(n) === 64,
    wat: `(module
      (import "kotoba" "kagi_sign" (func $kagi_sign (param i32 i32 i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "kagi://ops/key")
      (data (i32.const 32) "msg")
      (func (export "main") (result i64)
        (i64.extend_i32_s
          (call $kagi_sign (i32.const 0) (i32.const 14)
                           (i32.const 32) (i32.const 3)
                           (i32.const 64) (i32.const 64)))))`,
  },
  {
    id: 'http-fetch-node-inject-available',
    imports: ['http-fetch'],
    limits: {
      maxHttpFetches: 8,
      allowedUrlPrefixes: ['https://example.test/'],
    },
    // Injected GET — no real network; proves link + inject path.
    inject: { httpFetch: () => new TextEncoder().encode('pong') },
    check: (n) => Number(n) === 4,
    wat: `(module
      (import "kotoba" "http_fetch" (func $http_fetch (param i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "https://example.test/x")
      (func (export "main") (result i64)
        (i64.extend_i32_s
          (call $http_fetch (i32.const 0) (i32.const 22)
                            (i32.const 200) (i32.const 256)))))`,
  },
  {
    id: 'http-post-headers-node-inject-available',
    imports: ['http-post-headers'],
    limits: {
      maxHttpPosts: 8,
      allowedUrlPrefixes: ['https://example.test/'],
    },
    inject: {
      httpPostHeaders: (_url, _body, _headers) => new TextEncoder().encode('pong'),
    },
    check: (n) => Number(n) === 4,
    // Headers: key\tvalue (WAT \t → tab). URL length 22, body 4, headers "X-T\t1" = 5.
    wat: `(module
      (import "kotoba" "http_post_headers"
        (func $h (param i32 i32 i32 i32 i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "https://example.test/x")
      (data (i32.const 100) "body")
      (data (i32.const 200) "X-T\\t1")
      (func (export "main") (result i64)
        (i64.extend_i32_s
          (call $h (i32.const 0) (i32.const 22)
                   (i32.const 100) (i32.const 4)
                   (i32.const 200) (i32.const 5)
                   (i32.const 500) (i32.const 256)))))`,
  },
  {
    id: 'json-extract-field-node-live',
    imports: ['json-extract-field'],
    check: (n) => Number(n) === 2,
    // Extract "ok" from {"x":"ok"} — pure codec, no inject.
    wat: `(module
      (import "kotoba" "json_extract_field"
        (func $j (param i32 i32 i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "{\\\"x\\\":\\\"ok\\\"}")
      (data (i32.const 100) "x")
      (func (export "main") (result i64)
        (i64.extend_i32_s
          (call $j (i32.const 0) (i32.const 11)
                   (i32.const 100) (i32.const 1)
                   (i32.const 300) (i32.const 64)))))`,
  },
  {
    id: 'cbor-encode-node-live',
    imports: ['cbor-encode'],
    // flat pairs a<TAB>b via WAT hex escapes (3 bytes)
    check: (n) => Number(n) > 0,
    wat: `(module
      (import "kotoba" "cbor_encode" (func $c (param i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "\\61\\09\\62")
      (func (export "main") (result i64)
        (i64.extend_i32_s
          (call $c (i32.const 0) (i32.const 3)
                   (i32.const 64) (i32.const 256)))))`,
  },
  {
    id: 'json-encode-node-live',
    imports: ['json-encode'],
    check: (n) => Number(n) > 0,
    wat: `(module
      (import "kotoba" "json_encode" (func $j (param i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "\\61\\09\\62")
      (func (export "main") (result i64)
        (i64.extend_i32_s
          (call $j (i32.const 0) (i32.const 3)
                   (i32.const 64) (i32.const 256)))))`,
  },

  {
    id: 'transport-connect-node-inject-available',
    imports: ['transport-connect'],
    limits: { maxTransportConnections: 1 },
    check: (n) => Number(n) === 0,
    // fail-closed empty-allowlist semantics → handle 0
    wat: `(module
      (import "kotoba" "transport_connect" (func $tc (param i32 i32 i32) (result i64)))
      (memory (export "memory") 1)
      (data (i32.const 0) "example.com")
      (func (export "main") (result i64)
        (call $tc (i32.const 0) (i32.const 11) (i32.const 443))))`,
  },
  {
    id: 'tls-open-node-inject-available',
    imports: ['tls-open'],
    limits: { maxTransportConnections: 1 },
    check: (n) => Number(n) === 0,
    wat: `(module
      (import "kotoba" "tls_open" (func $tls (param i64 i32 i32) (result i64)))
      (memory (export "memory") 1)
      (data (i32.const 0) "example.com")
      (func (export "main") (result i64)
        (call $tls (i64.const 0) (i32.const 0) (i32.const 11))))`,
  },
  {
    id: 'transport-close-node-inject-available',
    imports: ['transport-close'],
    limits: { maxTransportConnections: 1 },
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "transport_close" (func $tc (param i64) (result i32)))
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $tc (i64.const 0)))))`,
  },
  {
    id: 'transport-write-node-inject-available',
    imports: ['transport-write'],
    limits: { maxTransportConnections: 1 },
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "transport_write" (func $tw (param i64 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $tw (i64.const 0) (i32.const 0) (i32.const 0)))))`,
  },
  {
    id: 'transport-read-node-inject-available',
    imports: ['transport-read'],
    limits: { maxTransportConnections: 1 },
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "transport_read" (func $tr (param i64 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $tr (i64.const 0) (i32.const 0) (i32.const 8)))))`,
  },

  {
    id: 'pg-pool-open-node-inject-available',
    imports: ['pg-pool-open'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "pg_pool_open"
        (func $o (param i32 i32 i32 i32 i32 i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "h")
      (data (i32.const 8) "u")
      (data (i32.const 16) "d")
      (data (i32.const 24) "c")
      (func (export "main") (result i64)
        (i64.extend_i32_s
          (call $o
            (i32.const 0) (i32.const 1)
            (i32.const 5432)
            (i32.const 8) (i32.const 1)
            (i32.const 16) (i32.const 1)
            (i32.const 24) (i32.const 1)))))`,
  },
  {
    id: 'pg-pool-acquire-node-inject-available',
    imports: ['pg-pool-acquire'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "pg_pool_acquire" (func $a (param i32) (result i32)))
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $a (i32.const 99)))))`,
  },
  {
    id: 'pg-pool-health-node-inject-available',
    imports: ['pg-pool-health'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "pg_pool_health" (func $h (param i32) (result i32)))
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $h (i32.const 99)))))`,
  },
  {
    id: 'pg-pool-close-node-inject-available',
    imports: ['pg-pool-close'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "pg_pool_close" (func $c (param i32) (result i32)))
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $c (i32.const 99)))))`,
  },
  {
    id: 'pg-open-node-inject-available',
    imports: ['pg-open'],
    check: (n) => Number(n) === 0,
    wat: `(module
      (import "kotoba" "pg_open"
        (func $o (param i32 i32 i32 i32 i32 i32 i32) (result i64)))
      (memory (export "memory") 1)
      (data (i32.const 0) "h")
      (data (i32.const 8) "u")
      (data (i32.const 16) "d")
      (func (export "main") (result i64)
        (call $o
          (i32.const 0) (i32.const 1)
          (i32.const 5432)
          (i32.const 8) (i32.const 1)
          (i32.const 16) (i32.const 1))))`,
  },
  {
    id: 'pg-query-node-inject-available',
    imports: ['pg-query'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "pg_query"
        (func $q (param i64 i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "SELECT 1")
      (func (export "main") (result i64)
        (i64.extend_i32_s
          (call $q
            (i64.const 0)
            (i32.const 0) (i32.const 8)
            (i32.const 64) (i32.const 256)))))`,
  },
  {
    id: 'scram-sha256-node-deny-available',
    imports: ['scram-sha256'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "scram_sha256"
        (func $scram (param i32 i32 i32 i32 i32 i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "db/primary")
      (data (i32.const 32) "saltsalt")
      (data (i32.const 64) "n,,n=u,r=r1,r=r2,c=biws,p=x")
      (func (export "main") (result i64)
        (i64.extend_i32_s
          (call $scram
            (i32.const 0) (i32.const 10)
            (i32.const 32) (i32.const 8)
            (i32.const 4096)
            (i32.const 64) (i32.const 28)
            (i32.const 128) (i32.const 64)))))`,
  },
  {
    id: 'scram-sha256-node-available',
    imports: ['scram-sha256'],
    inject: {
      scramCredentials: { 'db/primary': 's3cret' },
      scramCredentialAllowlist: new Set(['db/primary']),
    },
    check: (n) => Number(n) === 64,
    wat: `(module
      (import "kotoba" "scram_sha256"
        (func $scram (param i32 i32 i32 i32 i32 i32 i32 i32 i32) (result i32)))
      (memory (export "memory") 1)
      (data (i32.const 0) "db/primary")
      (data (i32.const 32) "saltsalt")
      (data (i32.const 64) "n,,n=u,r=r1,r=r2,c=biws,p=x")
      (func (export "main") (result i64)
        (i64.extend_i32_s
          (call $scram
            (i32.const 0) (i32.const 10)
            (i32.const 32) (i32.const 8)
            (i32.const 4096)
            (i32.const 64) (i32.const 28)
            (i32.const 128) (i32.const 64)))))`,
  },

  {
    id: 'pg-prepare-node-inject-available',
    imports: ['pg-prepare'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "pg_prepare" (func $f (param i64 i32 i32 i32 i32 i32 i32 i32 i32) (result i32)))
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $f (i64.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0)))))`,
  },
  {
    id: 'pg-session-reset-node-inject-available',
    imports: ['pg-session-reset'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "pg_session_reset" (func $f (param i64 i32 i32 i32 i32) (result i32)))
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $f (i64.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0)))))`,
  },
  {
    id: 'pg-bind-portal-node-inject-available',
    imports: ['pg-bind-portal'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "pg_bind_portal" (func $f (param i64 i32 i32 i32 i32 i32 i32 i32 i32 i32 i32) (result i32)))
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $f (i64.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0)))))`,
  },
  {
    id: 'pg-fetch-portal-node-inject-available',
    imports: ['pg-fetch-portal'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "pg_fetch_portal" (func $f (param i64 i32 i32 i32 i32 i32 i32 i32) (result i32)))
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $f (i64.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0)))))`,
  },
  {
    id: 'pg-copy-out-node-inject-available',
    imports: ['pg-copy-out'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "pg_copy_out" (func $f (param i64 i32 i32 i32 i32 i32 i32) (result i32)))
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $f (i64.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0)))))`,
  },
  {
    id: 'pg-copy-in-node-inject-available',
    imports: ['pg-copy-in'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "pg_copy_in" (func $f (param i64 i32 i32 i32 i32 i32 i32 i32 i32) (result i32)))
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $f (i64.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0)))))`,
  },
  {
    id: 'pg-execute-batch-node-inject-available',
    imports: ['pg-execute-batch'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "pg_execute_batch" (func $f (param i64 i32 i32 i32 i32 i32 i32 i32) (result i32)))
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $f (i64.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0)))))`,
  },
  {
    id: 'pg-open-scram-node-inject-available',
    imports: ['pg-open-scram'],
    check: (n) => Number(n) === 0,
    wat: `(module
      (import "kotoba" "pg_open_scram" (func $f (param i32 i32 i32 i32 i32 i32 i32 i32 i32 i32 i32) (result i64)))
      (func (export "main") (result i64)
        (call $f (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0) (i32.const 0))))`,
  },
  {
    id: 'pg-close-scram-node-inject-available',
    imports: ['pg-close-scram'],
    check: (n) => Number(n) === -1,
    wat: `(module
      (import "kotoba" "pg_close_scram" (func $f (param i64) (result i32)))
      (func (export "main") (result i64)
        (i64.extend_i32_s (call $f (i64.const 0)))))`,
  },



];

const tmpRoot = await mkdtemp(path.join(tmpdir(), 'kototama-host-parity-live-'));
const buildDir = path.join(tmpRoot, 'build');
await mkdir(buildDir, { recursive: true });

try {
  let actorHostUrl;
  let sourceNote;
  const localHost = [siblingActorHost, siblingActorHostAlt].find((p) => existsSync(p));
  if (localHost) {
    actorHostUrl = pathToFileURL(localHost).href;
    sourceNote = `sibling:${localHost}`;
  } else {
    for (const filePath of SRC_FILES) {
      const url = `https://cdn.jsdelivr.net/gh/kotoba-lang/wasm-webcomponent@${WASM_WEBCOMPONENT_COMMIT}/${filePath}`;
      const src = await (await fetch(url)).text();
      const dest = path.join(tmpRoot, filePath);
      await mkdir(path.dirname(dest), { recursive: true });
      await writeFile(dest, src);
    }
    actorHostUrl = pathToFileURL(path.join(tmpRoot, 'src', 'actor-host.js')).href;
    sourceNote = `cdn:${WASM_WEBCOMPONENT_COMMIT}`;
  }

  const {
    actorHostImports,
    hostCaps,
    inMemoryStore,
  } = await import(actorHostUrl);

  const results = [];
  let failed = 0;

  for (const entry of corpus) {
    try {
      const wasm = watToWasm(entry.wat, buildDir);
      const memoryBox = {};
      const store = inMemoryStore();
      const caps = hostCaps({
        grants: entry.imports,
        limits: {
          allowWriteImports: true,
          allowSecretImports: true,
          maxRandomBytes: 65536,
          maxLogWriteBytes: 65536,
          maxLogReadBytes: 65536,
          maxHttpPosts: 8,
          maxHttpFetches: 8,
          maxLlmInfers: 2,
          ...(entry.limits || {}),
        },
      });
      const importObject = {
        kotoba: actorHostImports(entry.imports, caps, memoryBox, {
          store,
          runtime: 'node',
          ...(entry.inject || {}),
        }),
      };
      const { instance } = await WebAssembly.instantiate(wasm, importObject);
      memoryBox.memory = instance.exports.memory;
      const result = instance.exports.main();
      const ok = entry.check(result);
      results.push({
        ok,
        id: entry.id,
        host: 'node',
        imports: entry.imports,
        result: typeof result === 'bigint' ? result.toString() : result,
        live: true,
      });
      if (ok) console.log(`OK: ${entry.id}`);
      else {
        failed += 1;
        console.error(`FAIL: ${entry.id} result=${result}`);
      }
    } catch (e) {
      failed += 1;
      results.push({
        ok: false,
        id: entry.id,
        host: 'node',
        imports: entry.imports,
        live: true,
        error: e.message,
      });
      console.error(`FAIL: ${entry.id} ${e.message}`);
    }
  }

  const report = {
    ok: failed === 0,
    host: 'node',
    total: corpus.length,
    passed: corpus.length - failed,
    failed: results.filter((r) => !r.ok),
    results,
    case_ids: corpus.map((c) => c.id),
    wasm_webcomponent_source: sourceNote,
    wasm_webcomponent_commit: WASM_WEBCOMPONENT_COMMIT,
    note: 'T8.4 Node/browser live runner via wasm-webcomponent actor-host.js under Node WebAssembly',
  };

  // Machine-readable line for Clojure shell integration.
  console.log(`HOST_PARITY_LIVE_JSON:${JSON.stringify(report)}`);

  if (failed !== 0) {
    console.error(`host-parity-live Node runner FAILED (${failed}/${corpus.length})`);
    process.exit(1);
  }
  console.log(`OK: Node live host runner proved ${corpus.length} host-parity cases`);
} finally {
  await rm(tmpRoot, { recursive: true, force: true });
}
