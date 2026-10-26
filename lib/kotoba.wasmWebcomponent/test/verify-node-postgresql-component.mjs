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
import { instantiateLinkedKotobaComponent, PG_SESSION_LINKS, PG_SIMPLE_QUERY_LINKS } from '../src/component-linker.js';
import { createNodeTransportBroker } from '../src/node-transport-broker.js';

const compilerRepo = resolve(fileURLToPath(new URL('.', import.meta.url)), '../../kotoba');
const fixtureDir = mkdtempSync(join(tmpdir(), 'kotoba-postgresql-component-'));
try {
  const keyPath = join(fixtureDir, 'key.pem');
  const certPath = join(fixtureDir, 'cert.pem');
  const providerPath = join(fixtureDir, 'db_transport.wasm');
  const consumerPath = join(fixtureDir, 'pg_session_consumer.wasm');
  const simplePath = join(fixtureDir, 'pg_consumer.wasm');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256',
    '-keyout', keyPath, '-out', certPath, '-days', '1', '-subj', '/CN=localhost',
    '-addext', 'subjectAltName=DNS:localhost'], { stdio: 'ignore' });
  const expression = `(require '[clojure.edn :as edn] '[kotoba.runtime :as runtime])
    (doseq [[source policy-path output] [["providers/db_transport.kotoba" "providers/transport_policy.edn" "${providerPath}"]
                                         ["providers/pg_session_consumer.kotoba" "providers/db_component_policy.edn" "${consumerPath}"]
                                         ["providers/pg_consumer.kotoba" "providers/db_component_policy.edn" "${simplePath}"]]]
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
    const net = require('node:net'); const tls = require('node:tls');
    const context = tls.createSecureContext(workerData);
    const server = net.createServer(socket => {
      let plain = Buffer.alloc(0);
      socket.on('data', function sslRequest(chunk) {
        plain = Buffer.concat([plain, chunk]);
        if (plain.length < 8) return;
        socket.removeListener('data', sslRequest);
        if (plain.readInt32BE(0) !== 8 || plain.readInt32BE(4) !== 80877103) return socket.destroy();
        socket.write(Buffer.from('S'));
        const secure = new tls.TLSSocket(socket, { isServer: true, secureContext: context });
        let input = Buffer.alloc(0), startupDone = false;
        secure.on('error', () => {});
        secure.on('data', chunk2 => {
          input = Buffer.concat([input, chunk2]);
          if (!startupDone && input[0] === 81 && input.length >= 5 && input.length >= input.readInt32BE(1)+1) {
            const length=input.readInt32BE(1)+1;parentPort.postMessage({ directQuery: input.subarray(0,length) });input=input.subarray(length);startupDone=true;
            secure.write(Buffer.from([82,0,0,0,8,0,0,0,0,90,0,0,0,5,73]));return;
          }
          if (!startupDone && input.length >= 4 && input.length >= input.readInt32BE(0)) {
            const length = input.readInt32BE(0);
            parentPort.postMessage({ startup: input.subarray(0, length) });
            input = input.subarray(length); startupDone = true;
            secure.write(Buffer.from([82,0,0,0,8,0,0,0,0, 90,0,0,0,5,73]));
          }
          if (startupDone && input.length >= 5 && input.length >= input.readInt32BE(1) + 1) {
            const length = input.readInt32BE(1) + 1;
            parentPort.postMessage({ query: input.subarray(0, length) });
            input = input.subarray(length);
            secure.write(Buffer.from([67,0,0,0,13,83,69,76,69,67,84,32,49,0, 90,0,0,0,5,73]));
          }
        });
        secure.resume();
      });
    });
    server.listen(0, '127.0.0.1', () => parentPort.postMessage({ port: server.address().port }));
    parentPort.on('message', () => server.close());
  `, { eval: true, workerData: { key, cert } });
  const [{ port }] = await once(server, 'message');
  const observed = [];
  server.on('message', message => observed.push(message));
  const broker = createNodeTransportBroker({
    endpointAllowlist: [`localhost:${port}`], resolvedAddressAllowlist: ['127.0.0.1'],
    maxConnections: 2, connectTimeoutMs: 1500, readTimeoutMs: 1500,
    maxReadBytes: 8192, maxWriteBytes: 8192, trustedCaPem: cert,
  });
  try {
    const lower = ['transport-connect', 'tls-open', 'transport-write', 'transport-read', 'transport-close'];
    const providerCaps = hostCaps({ grants: lower, limits: { maxTransportConnections: 2, allowWriteImports: true } });
    const provider = await instantiateKotobaComponent(readFileSync(providerPath), providerCaps, { transport: broker });
    const high = ['db-close', 'pg-open', 'pg-query'];
    const consumerCaps = hostCaps({ grants: high, limits: { allowWriteImports: true } });
    const consumer = await instantiateLinkedKotobaComponent(
      readFileSync(consumerPath), consumerCaps, provider.instance, PG_SESSION_LINKS);
    assert.deepEqual(consumer.imports, high);
    assert.ok(consumer.instance.exports.run(port) > 0,
      'compiled PostgreSQL consumer completed startup, query and close');
    for (let i = 0; observed.filter(x => x.query).length < 1 && i < 50; i += 1) {
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    const startup = observed.find(x => x.startup)?.startup;
    const query = observed.find(x => x.query)?.query;
    assert.ok(startup && query, 'fixture observed startup and simple-query frames');
    assert.equal(new DataView(startup.buffer, startup.byteOffset, startup.byteLength).getInt32(4), 196608);
    assert.equal(new TextDecoder().decode(query), 'Q\0\0\0\rselect 1\0');
    const simple = await instantiateLinkedKotobaComponent(readFileSync(simplePath),
      hostCaps({ grants: ['pg-simple-query'], limits: { allowWriteImports: true } }), provider.instance, PG_SIMPLE_QUERY_LINKS);
    const simpleResult=simple.instance.exports.run(port);
    for(let i=0;!observed.some(x=>x.directQuery)&&i<50;i++)await new Promise(resolve=>setTimeout(resolve,10));
    assert.ok(simpleResult>0,`legacy one-shot simple query remains explicitly component-linked (result ${simpleResult})`);
    assert.equal(new TextDecoder().decode(observed.find(x=>x.directQuery).directQuery),'Q\0\0\0\rselect 1\0');
  } finally {
    await broker.closeAll(); server.postMessage('close'); await server.terminate();
  }
  console.log('compiled PostgreSQL .kotoba provider + session and one-shot consumers: Node TLS/query E2E pass');
} finally { rmSync(fixtureDir, { recursive: true, force: true }); }
