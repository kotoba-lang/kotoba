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
import { DB_LINKS, instantiateLinkedKotobaComponent } from '../src/component-linker.js';
import { createNodeTransportBroker } from '../src/node-transport-broker.js';

const compilerRepo = resolve(fileURLToPath(new URL('.', import.meta.url)), '../../kotoba');
const fixtureDir = mkdtempSync(join(tmpdir(), 'kotoba-db-component-'));
try {
  const keyPath = join(fixtureDir, 'key.pem');
  const certPath = join(fixtureDir, 'cert.pem');
  const providerPath = join(fixtureDir, 'db_transport.wasm');
  const consumerPath = join(fixtureDir, 'db_consumer.wasm');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256',
    '-keyout', keyPath, '-out', certPath, '-days', '1', '-subj', '/CN=localhost',
    '-addext', 'subjectAltName=DNS:localhost'], { stdio: 'ignore' });
  const expression = `(require '[clojure.edn :as edn] '[kotoba.runtime :as runtime])
    (doseq [[source policy-path output] [["providers/db_transport.kotoba" "providers/transport_policy.edn" "${providerPath}"]
                                         ["providers/db_consumer.kotoba" "providers/db_component_policy.edn" "${consumerPath}"]]]
      (let [forms (runtime/read-file source :kotoba) policy (edn/read-string (slurp policy-path))
            result (runtime/wasm-binary forms policy)]
        (assert (:kotoba.wasm/ok? result))
        (java.nio.file.Files/write (java.nio.file.Paths/get output (make-array String 0))
          ^bytes (:kotoba.wasm/binary result) (make-array java.nio.file.OpenOption 0))))`;
  execFileSync('clojure', ['-M:dev', '-i', 'tools/cljk_loader.cljk', '-e', expression], { cwd: compilerRepo, stdio: 'ignore' });
  const key = readFileSync(keyPath, 'utf8');
  const cert = readFileSync(certPath, 'utf8');
  const server = new Worker(`
    const { parentPort, workerData } = require('node:worker_threads');
    const tls = require('node:tls');
    const server = tls.createServer(workerData, socket => {
      let input = Buffer.alloc(0);
      socket.on('data', chunk => {
        input = Buffer.concat([input, chunk]);
        if (input.length >= 4) {
          const length = input.readUInt32BE(0);
          if (input.length >= length + 4) {
            parentPort.postMessage({ payload: input.subarray(4, 4 + length) });
            socket.end(Buffer.concat([Buffer.from([0, 0, 0, 4]), Buffer.from('pong')]));
          }
        }
      });
    });
    server.listen(0, '127.0.0.1', () => parentPort.postMessage({ port: server.address().port }));
    parentPort.on('message', () => server.close());
  `, { eval: true, workerData: { key, cert } });
  const [{ port }] = await once(server, 'message');
  const payloads = [];
  server.on('message', message => { if (message.payload) payloads.push(new Uint8Array(message.payload)); });
  const broker = createNodeTransportBroker({
    endpointAllowlist: [`localhost:${port}`], resolvedAddressAllowlist: ['127.0.0.1'],
    maxConnections: 1, connectTimeoutMs: 1500, readTimeoutMs: 1500,
    maxReadBytes: 4096, maxWriteBytes: 4096, trustedCaPem: cert,
  });
  try {
    const lower = ['transport-connect', 'tls-open', 'transport-write', 'transport-read', 'transport-close'];
    const providerCaps = hostCaps({ grants: lower, limits: { maxTransportConnections: 1, allowWriteImports: true } });
    const provider = await instantiateKotobaComponent(readFileSync(providerPath), providerCaps, { transport: broker });
    const consumerCaps = hostCaps({ grants: ['db-exchange'], limits: { allowWriteImports: true } });
    const consumer = await instantiateLinkedKotobaComponent(
      readFileSync(consumerPath), consumerCaps, provider.instance, DB_LINKS);
    assert.deepEqual(consumer.imports, ['db-exchange']);
    assert.equal(consumer.instance.exports.run(port), 8,
      'compiled consumer exchanged one bounded frame through the compiled provider');
    while (payloads.length < 1) await once(server, 'message');
    assert.equal(new TextDecoder().decode(payloads[0]), 'ping');
  } finally {
    await broker.closeAll(); server.postMessage('close'); await server.terminate();
  }
  console.log('compiled .kotoba DB provider + independent consumer: Node TLS frame E2E pass');
} finally { rmSync(fixtureDir, { recursive: true, force: true }); }
