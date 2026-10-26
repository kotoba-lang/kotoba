import assert from 'node:assert/strict';
import { actorHostImports, hostCaps } from '../src/actor-host.js';
import { createNodeCredentialProvider } from '../src/node-credential-provider.js';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { instantiateKotobaComponent } from '../src/component-runtime.js';
import { createNodeTransportBroker } from '../src/node-transport-broker.js';

const memory = new WebAssembly.Memory({ initial: 1 });
const bytes = new Uint8Array(memory.buffer);
const ref = new TextEncoder().encode('db/primary');
const salt = Uint8Array.from([0x5b, 0x6d, 0x99, 0x68, 0x9d, 0x12, 0x35, 0x8e,
  0xec, 0xa0, 0x4b, 0x14, 0x12, 0x36, 0xfa, 0x81]);
const auth = new TextEncoder().encode('n=user,r=fyko+d2lbbFgONRv9qkxdawL,r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,s=W22ZaJ0SNY7soEsUEjb6gQ==,i=4096,c=biws,r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j');
bytes.set(ref, 0); bytes.set(salt, 32); bytes.set(auth, 64);
const provider = createNodeCredentialProvider({
  credentialAllowlist: ['db/primary'], maxProofs: 1,
  credentials: () => new Map([['db/primary', 'pencil']]),
});
const caps = hostCaps({ grants: ['scram-sha256'], limits: {
  maxScramProofs: 1, allowSecretImports: true, allowWriteImports: true,
  scramCredentialAllowlist: ['db/primary'],
}});
const imports = actorHostImports(['scram-sha256'], caps, { memory }, { credentials: provider });
assert.equal(imports.scram_sha256(0, ref.length, 32, salt.length, 4096, 64, auth.length, 512, 64), 64);
assert.equal(Buffer.from(bytes.slice(512, 576)).toString('hex'),
  '9213ee9db10dd5b4ba651d747907231006195be4fd692071ef2fd43184e35dd9' +
  '3d4674feeaf15fce9e19687fa5a0d5e57c4d2526b5fc84858f7882036071693d');
assert.equal(imports.scram_sha256(0, ref.length, 32, salt.length, 4096, 64, auth.length, 512, 64), -1,
  'proof quota is enforced at call time');
assert.equal(new TextDecoder().decode(bytes.slice(0, ref.length)), 'db/primary',
  'guest memory contains only the credential reference, never the password');
console.log('Node purpose-bound SCRAM-SHA-256: non-exporting credential and vector pass');

const fixtureDir = mkdtempSync(join(tmpdir(), 'kotoba-pg-scram-'));
try {
  const wasmPath = join(fixtureDir, 'pg_scram.wasm');
  const compilerRepo = resolve(fileURLToPath(new URL('.', import.meta.url)), '../../kotoba');
  const expression = `(require '[clojure.edn :as edn] '[kotoba.runtime :as runtime])
    (let [forms (runtime/read-file "providers/pg_scram.kotoba" :kotoba)
          policy (edn/read-string (slurp "providers/pg_scram_policy.edn"))
          result (runtime/wasm-binary forms policy)]
      (assert (:kotoba.wasm/ok? result))
      (java.nio.file.Files/write (java.nio.file.Paths/get "${wasmPath}" (make-array String 0))
        ^bytes (:kotoba.wasm/binary result) (make-array java.nio.file.OpenOption 0)))`;
  execFileSync('clojure', ['-M:dev', '-i', 'tools/cljk_loader.cljk', '-e', expression], { cwd: compilerRepo, stdio: 'ignore' });
  const allImports = ['transport-connect', 'tls-open', 'tls-server-end-point',
    'transport-write', 'transport-read', 'transport-close', 'scram-sha256',
    'pg-cancel-register', 'pg-cancel', 'random-bytes'];
  const componentCaps = hostCaps({ grants: allImports, limits: {
    maxTransportConnections: 1, maxScramProofs: 1, maxPgCancelHandles: 1,
    maxPgCancelRequests: 1, maxRandomBytes: 18,
    allowSecretImports: true, allowWriteImports: true,
    scramCredentialAllowlist: ['db/primary'],
  }});
  const componentCredentials = createNodeCredentialProvider({
    credentialAllowlist: ['db/primary'], maxProofs: 1,
    credentials: () => new Map([['db/primary', 'pencil']]),
  });
  const componentTransport = createNodeTransportBroker();
  try {
    const component = await instantiateKotobaComponent(readFileSync(wasmPath), componentCaps,
      { transport: componentTransport, credentials: componentCredentials });
    const componentBytes = new Uint8Array(component.instance.exports.memory.buffer);
    componentBytes.set(ref, 0); componentBytes.set(salt, 32); componentBytes.set(auth, 64);
    assert.equal(component.instance.exports['pg-scram-proof'](
      0, ref.length, 32, salt.length, 4096, 64, auth.length, 512, 64), 64);
    assert.equal(Buffer.from(componentBytes.slice(512, 576)).toString('hex'),
      '9213ee9db10dd5b4ba651d747907231006195be4fd692071ef2fd43184e35dd9' +
      '3d4674feeaf15fce9e19687fa5a0d5e57c4d2526b5fc84858f7882036071693d');
  } finally { await componentTransport.closeAll(); }
  console.log('compiled pg_scram.kotoba: purpose-bound Node credential import pass');
} finally { rmSync(fixtureDir, { recursive: true, force: true }); }
