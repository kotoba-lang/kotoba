import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { once } from 'node:events';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { Worker } from 'node:worker_threads';
import { fileURLToPath } from 'node:url';
import { hostCaps } from '../src/actor-host.js';
import { instantiateKotobaComponent } from '../src/component-runtime.js';
import { instantiateLinkedKotobaComponents, PG_QUERY_STATE_LINKS,
  PG_EXPLICIT_SCRAM_LINKS, PG_SCRAM_SESSION_LINKS } from '../src/component-linker.js';
import { createNodeCredentialProvider } from '../src/node-credential-provider.js';
import { createNodeTransportBroker } from '../src/node-transport-broker.js';

const compilerRepo = resolve(fileURLToPath(new URL('.', import.meta.url)), '../../kotoba');
const fixtureDir = mkdtempSync(join(tmpdir(), 'kotoba-pg-transaction-'));
try {
  const keyPath = join(fixtureDir, 'key.pem');
  const certPath = join(fixtureDir, 'cert.pem');
  const dbPath = join(fixtureDir, 'db_transport.wasm');
  const scramPath = join(fixtureDir, 'pg_scram.wasm');
  const consumerPath = join(fixtureDir, 'pg_transaction_consumer.wasm');
  const explicitPath = join(fixtureDir, 'pg_explicit_scram_consumer.wasm');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256',
    '-keyout', keyPath, '-out', certPath, '-days', '1', '-subj', '/CN=localhost',
    '-addext', 'subjectAltName=DNS:localhost'], { stdio: 'ignore' });
  const expression = `(require '[clojure.edn :as edn] '[kotoba.runtime :as runtime])
    (doseq [[source policy output] [["providers/db_transport.kotoba" "providers/transport_policy.edn" "${dbPath}"]
                                    ["providers/pg_scram.kotoba" "providers/pg_scram_policy.edn" "${scramPath}"]
                                    ["providers/pg_transaction_consumer.kotoba" "providers/db_component_policy.edn" "${consumerPath}"]
                                    ["providers/pg_explicit_scram_consumer.kotoba" "providers/db_component_policy.edn" "${explicitPath}"]]]
      (let [result (runtime/wasm-binary (runtime/read-file source :kotoba)
                     (edn/read-string (slurp policy)))]
        (assert (:kotoba.wasm/ok? result))
        (java.nio.file.Files/write (java.nio.file.Paths/get output (make-array String 0))
          ^bytes (:kotoba.wasm/binary result) (make-array java.nio.file.OpenOption 0))))`;
  execFileSync('clojure', ['-M:dev', '-i', 'tools/cljk_loader.cljk', '-e', expression], { cwd: compilerRepo, stdio: 'ignore' });
  const key = readFileSync(keyPath, 'utf8');
  const cert = readFileSync(certPath, 'utf8');
  const server = new Worker(`
    const { parentPort, workerData } = require('node:worker_threads');
    const net = require('node:net'); const tls = require('node:tls');
    const context = tls.createSecureContext(workerData);
    const authSasl = Buffer.concat([Buffer.from([82,0,0,0,23,0,0,0,10]), Buffer.from('SCRAM-SHA-256\\0\\0')]);
    const serverFirst = Buffer.from('r=AAECAwQFBgcICQoLDA0ODxARserver,s=W22ZaJ0SNY7soEsUEjb6gQ==,i=4096');
    const authContinue = Buffer.concat([Buffer.from([82,0,0,0,serverFirst.length+8,0,0,0,11]), serverFirst]);
    const serverFinal = Buffer.from('v=QAdQmJ+lRK7pdc/DBEeFAbUmtBhFLhQXsQNpv3KJgJQ=');
    const authFinal = Buffer.concat([Buffer.from([82,0,0,0,serverFinal.length+8,0,0,0,12]), serverFinal]);
    const startupTail = Buffer.from([82,0,0,0,8,0,0,0,0, 75,0,0,0,12,0,0,0,1,0,0,0,2, 90,0,0,0,5,73]);
    const command = (tag, state) => Buffer.concat([Buffer.from([67,0,0,0,tag.length+5]), Buffer.from(tag+'\\0'), Buffer.from([90,0,0,0,5,state.charCodeAt(0)])]);
    const error = Buffer.from([69,0,0,0,12,67,50,50,48,49,50,0,0, 90,0,0,0,5,69]);
    const server = net.createServer(socket => {
      let plain = Buffer.alloc(0);
      socket.on('data', function ssl(chunk) {
        plain = Buffer.concat([plain, chunk]); if (plain.length < 8) return;
        socket.removeListener('data', ssl);
        if (plain.readInt32BE(4) !== 80877103) return socket.destroy();
        socket.write(Buffer.from('S'));
        const secure = new tls.TLSSocket(socket, { isServer: true, secureContext: context });
        let input = Buffer.alloc(0), stage = 0;
        secure.on('error', () => {});
        secure.on('data', chunk2 => {
          input = Buffer.concat([input, chunk2]);
          while (true) {
            const needed = stage === 0 ? (input.length >= 4 ? input.readInt32BE(0) : Infinity)
              : (input.length >= 5 ? input.readInt32BE(1)+1 : Infinity);
            if (input.length < needed) break;
            const frame = input.subarray(0, needed); input = input.subarray(needed);
            if (stage === 0) { secure.write(authSasl); stage = 1; }
            else if (stage === 1) { parentPort.postMessage({ first: frame }); secure.write(authContinue); stage = 2; }
            else if (stage === 2) { parentPort.postMessage({ final: frame }); secure.write(Buffer.concat([authFinal,startupTail])); stage = 3; }
            else {
              const query = frame.subarray(5, frame.length-1).toString('utf8').toLowerCase();
              parentPort.postMessage({ query });
              if (query === 'begin') secure.write(command('BEGIN','T'));
              else if (query === 'select 1/0') secure.write(error);
              else if (query === 'rollback') secure.write(command('ROLLBACK','I'));
              else if (query === 'select 1') secure.write(command('SELECT 1','I'));
              else socket.destroy();
            }
          }
        }); secure.resume();
      });
    });
    server.listen(0,'127.0.0.1',()=>parentPort.postMessage({port:server.address().port}));
    parentPort.on('message',()=>server.close());
  `, { eval: true, workerData: { key, cert } });
  const [{ port }] = await once(server, 'message');
  const observed = [];
  server.on('message', message => observed.push(message));
  const broker = createNodeTransportBroker({
    endpointAllowlist: [`localhost:${port}`], resolvedAddressAllowlist: ['127.0.0.1'],
    maxConnections: 2, connectTimeoutMs: 1500, readTimeoutMs: 1500,
    maxReadBytes: 32768, maxWriteBytes: 32768, trustedCaPem: cert,
  });
  const low = ['transport-connect','tls-open','tls-server-end-point','transport-write',
    'transport-read','transport-close','scram-sha256','pg-cancel-register','pg-cancel','random-bytes'];
  const lowCaps = hostCaps({ grants: low, limits: {
    maxTransportConnections: 2, maxScramProofs: 2, maxPgCancelHandles: 1,
    maxPgCancelRequests: 1, maxRandomBytes: 18, allowSecretImports: true,
    allowWriteImports: true, scramCredentialAllowlist: ['db/primary'],
  }});
  const credentials = createNodeCredentialProvider({ credentialAllowlist: ['db/primary'], maxProofs: 2,
    credentials: () => new Map([['db/primary','pencil']]) });
  try {
    const db = await instantiateKotobaComponent(readFileSync(dbPath),
      hostCaps({ grants: low.slice(0,6), limits: { maxTransportConnections: 2, allowWriteImports: true } }),
      { transport: broker });
    const scram = await instantiateKotobaComponent(readFileSync(scramPath), lowCaps, {
      transport: broker, credentials,
      randomBytes: length => Uint8Array.from({ length }, (_, index) => index),
    });
    const high = ['pg-query-state','pg-open-scram-random','pg-close-scram'];
    const consumer = await instantiateLinkedKotobaComponents(readFileSync(consumerPath),
      hostCaps({ grants: high, limits: { allowSecretImports: true, allowWriteImports: true } }),
      [{ instance: db.instance, specs: PG_QUERY_STATE_LINKS },
       { instance: scram.instance, specs: PG_SCRAM_SESSION_LINKS }]);
    assert.equal(consumer.instance.exports.run(port), 1,
      'compiled transaction consumer observed T -> E(22012) -> I');
    for (let i=0; observed.filter(x=>x.query).length<3 && i<50; i+=1) await new Promise(r=>setTimeout(r,10));
    assert.deepEqual(observed.filter(x=>x.query).map(x=>x.query), ['begin','select 1/0','rollback']);
    const explicit = await instantiateLinkedKotobaComponents(readFileSync(explicitPath),
      hostCaps({ grants: ['pg-query-state','pg-open-scram','pg-close-scram'], limits: { allowSecretImports: true, allowWriteImports: true } }),
      [{ instance: db.instance, specs: PG_QUERY_STATE_LINKS },
       { instance: scram.instance, specs: PG_EXPLICIT_SCRAM_LINKS }]);
    assert.equal(explicit.instance.exports.run(port), 1, 'caller-supplied bounded nonce is component-linked without credential export');
    for (let i=0; observed.filter(x=>x.query).length<4 && i<50; i+=1) await new Promise(r=>setTimeout(r,10));
    assert.equal(observed.filter(x=>x.query).at(-1).query, 'select 1');
  } finally {
    await broker.closeAll(); server.postMessage('close'); await server.terminate();
  }
  console.log('compiled PostgreSQL SCRAM consumers: random and explicit nonce sessions pass');
} finally { rmSync(fixtureDir, { recursive: true, force: true }); }
