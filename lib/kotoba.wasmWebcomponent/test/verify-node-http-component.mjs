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
import { instantiateLinkedKotobaComponent } from '../src/component-linker.js';
import { createNodeTransportBroker } from '../src/node-transport-broker.js';

const here = fileURLToPath(new URL('.', import.meta.url));
const compilerRepo = resolve(here, '../../kotoba');
const fixtureDir = mkdtempSync(join(tmpdir(), 'kotoba-http-component-'));

try {
  const keyPath = join(fixtureDir, 'key.pem');
  const certPath = join(fixtureDir, 'cert.pem');
  const wasmPath = join(fixtureDir, 'http_transport.wasm');
  const consumerWasmPath = join(fixtureDir, 'http_consumer.wasm');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256',
    '-keyout', keyPath, '-out', certPath, '-days', '1', '-subj', '/CN=localhost',
    '-addext', 'subjectAltName=DNS:localhost'], { stdio: 'ignore' });
  const expression = `(require '[clojure.edn :as edn] '[kotoba.runtime :as runtime])
    (doseq [[source policy-path output] [["providers/http_transport.kotoba" "providers/transport_policy.edn" "${wasmPath}"]
                                         ["providers/http_consumer.kotoba" "providers/http_component_policy.edn" "${consumerWasmPath}"]]]
      (let [forms (runtime/read-file source :kotoba)
            policy (edn/read-string (slurp policy-path))
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
      let request = '';
      socket.on('data', bytes => {
        request += bytes.toString('utf8');
        if (request.includes('\\r\\n\\r\\n')) {
          parentPort.postMessage({ request });
          socket.end('HTTP/1.1 200 OK\\r\\nContent-Length: 6\\r\\nConnection: close\\r\\n\\r\\nkotoba');
        }
      });
    });
    server.listen(0, '127.0.0.1', () => parentPort.postMessage({ port: server.address().port }));
    parentPort.on('message', () => server.close());
  `, { eval: true, workerData: { key, cert } });
  const [{ port }] = await once(server, 'message');
  const requests = [];
  server.on('message', message => { if (message.request) requests.push(message.request); });
  const broker = createNodeTransportBroker({
    endpointAllowlist: [`localhost:${port}`], resolvedAddressAllowlist: ['127.0.0.1'],
    maxConnections: 2, connectTimeoutMs: 1500, readTimeoutMs: 1500,
    maxReadBytes: 4096, maxWriteBytes: 4096, trustedCaPem: cert,
  });
  try {
    const requested = ['transport-connect', 'tls-open', 'transport-write', 'transport-read', 'transport-close'];
    const caps = hostCaps({ grants: requested, limits: {
      maxTransportConnections: 1, allowWriteImports: true,
    }});
    const events = [];
    const transport = Object.fromEntries(['connect', 'tlsOpen', 'write', 'read', 'close'].map(name =>
      [name, (...args) => { const result = broker[name](...args); events.push([name, result]); return result; }]));
    const { instance, imports } = await instantiateKotobaComponent(readFileSync(wasmPath), caps, { transport });
    assert.deepEqual(imports, requested, 'compiled .kotoba imports only the bounded transport ABI');
    const memory = new Uint8Array(instance.exports.memory.buffer);
    const host = new TextEncoder().encode('localhost');
    const path = new TextEncoder().encode('/component');
    memory.set(host, 0); memory.set(path, 32);
    const responseLength = instance.exports['http-get'](0, host.length, port, 32, path.length, 256, 2048);
    assert.ok(responseLength > 0, `compiled provider completed its bounded HTTP exchange (result ${responseLength}; events ${events.map(([n, v]) => `${n}:${v instanceof Uint8Array ? v.length : v}`).join(',')})`);
    const response = new TextDecoder().decode(memory.slice(256, 256 + responseLength));
    assert.match(response, /^HTTP\/1\.1 200 OK\r\n/);
    assert.ok(response.endsWith('\r\n\r\nkotoba'));
    while (requests.length < 1) await once(server, 'message');
    assert.match(requests[0], /^GET \/component HTTP\/1\.1\r\nHost: localhost\r\nConnection: close\r\n\r\n$/);

    const consumerCaps = hostCaps({ grants: ['http-get'], limits: {
      maxHttpGets: 1, allowWriteImports: true,
    }});
    const consumer = await instantiateLinkedKotobaComponent(
      readFileSync(consumerWasmPath), consumerCaps, instance);
    assert.deepEqual(consumer.imports, ['http-get']);
    assert.ok(consumer.instance.exports.run(port) > 0,
      'independent consumer memory links to the compiled provider export');
    assert.equal(consumer.instance.exports.run(port), -1, 'linked high-level call quota is finite');
    while (requests.length < 2) await once(server, 'message');
    assert.match(requests[1], /^GET \/ HTTP\/1\.1\r\nHost: localhost\r\nConnection: close\r\n\r\n$/);
  } finally {
    await broker.closeAll(); server.postMessage('close'); await server.terminate();
  }
  console.log('compiled .kotoba HTTP provider + independent consumer: Node TLS component-link E2E pass');
} finally { rmSync(fixtureDir, { recursive: true, force: true }); }
