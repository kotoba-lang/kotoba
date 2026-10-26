import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { once } from 'node:events';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Worker } from 'node:worker_threads';
import { hostCaps } from '../src/actor-host.js';
import { instantiateLinkedKotobaComponents, PG_POOL_LINKS } from '../src/component-linker.js';
import { instantiateKotobaComponent } from '../src/component-runtime.js';
import { createNodeCredentialProvider } from '../src/node-credential-provider.js';
import { createNodePostgresqlPoolProvider } from '../src/node-postgresql-pool-provider.js';
import { createNodeTransportBroker } from '../src/node-transport-broker.js';

const compilerRepo = resolve(fileURLToPath(new URL('.', import.meta.url)), '../../kotoba');
const dir = mkdtempSync(join(tmpdir(), 'kotoba-pg-pool-'));
try {
  const consumerPath = join(dir, 'consumer.wasm');
  const dbPath = join(dir, 'db.wasm'), scramPath = join(dir, 'scram.wasm');
  const expression = `(require '[clojure.edn :as edn] '[kotoba.runtime :as runtime])
    (doseq [[s p o] [["providers/pg_pool_multi_consumer.kotoba" "providers/db_component_policy.edn" "${consumerPath}"]
                     ["providers/db_transport.kotoba" "providers/transport_policy.edn" "${dbPath}"]
                     ["providers/pg_scram.kotoba" "providers/pg_scram_policy.edn" "${scramPath}"]]]
      (let [r (runtime/wasm-binary (runtime/read-file s :kotoba) (edn/read-string (slurp p)))]
        (assert (:kotoba.wasm/ok? r))
        (java.nio.file.Files/write (java.nio.file.Paths/get o (make-array String 0))
          ^bytes (:kotoba.wasm/binary r) (make-array java.nio.file.OpenOption 0))))`;
  execFileSync('clojure', ['-M:dev', '-i', 'tools/cljk_loader.cljk', '-e', expression], { cwd: compilerRepo, stdio: 'ignore' });

  let nextChannel = 40, opens = 0, closes = 0, resets = 0, queries = 0;
  const scramInstance = { exports: { memory: new WebAssembly.Memory({ initial: 1 }),
    'pg-open-scram-random': () => { opens++; return nextChannel++; },
    'pg-close-scram': () => { closes++; return 0; } } };
  const queryInstance = { exports: { memory: new WebAssembly.Memory({ initial: 1 }),
    'pg-session-reset': () => { resets++; return 1; },
    'pg-query-state': (_channel, _query, _queryLen, out, _cap, meta) => {
      queries++; const memory = queryInstance.exports.memory;
      new Uint8Array(memory.buffer, out, 6).set([67, 0, 0, 0, 4, 0]);
      new Uint8Array(memory.buffer, meta, 7).set([0, 73, 0, 0, 0, 0, 0]); return 6;
    } } };
  const provider = createNodePostgresqlPoolProvider({ scramInstance, queryInstance, maxConnectionsPerPool: 2, maxLeases: 2 });
  const grants = PG_POOL_LINKS.map(link => link.id);
  const consumer = await instantiateLinkedKotobaComponents(readFileSync(consumerPath),
    hostCaps({ grants, limits: { allowSecretImports: true, allowWriteImports: true } }),
    [{ instance: provider.instance, specs: PG_POOL_LINKS }]);
  assert.equal(consumer.instance.exports.run(5432), 1, 'compiled consumer observes saturation, fresh leases, busy close and clean close');
  assert.deepEqual(provider.snapshot(), { pools: 0, leases: 0 });
  assert.equal(opens, 2); assert.equal(closes, 2); assert.equal(resets, 3);

  const pool = consumer.instance.exports['open-pool'](5432);
  const lease = consumer.instance.exports.acquire(pool);
  assert.ok(pool > 0 && lease > 0);
  assert.equal(consumer.instance.exports.stats(pool), 32, 'stats are fixed-width and bounded');
  assert.equal(consumer.instance.exports.health(pool), 0, 'leased connections are not health-probed');
  assert.equal(consumer.instance.exports.release(lease), 0);
  assert.equal(consumer.instance.exports.health(pool), 1, 'idle connection is health-probed');
  const forcedLease = consumer.instance.exports.acquire(pool);
  assert.ok(forcedLease > lease, 'lease tokens are monotonic and never revived');
  assert.equal(consumer.instance.exports.drain(pool), 1, 'drain reports one forcibly closed lease');
  assert.equal(consumer.instance.exports.release(forcedLease), -1, 'drained lease is stale');
  assert.deepEqual(provider.snapshot(), { pools: 0, leases: 0 });
  assert.equal(queries, 1);
  provider.closeAll();

  const keyPath = join(dir, 'key.pem'), certPath = join(dir, 'cert.pem');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-keyout', keyPath,
    '-out', certPath, '-days', '1', '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'], { stdio: 'ignore' });
  const key = readFileSync(keyPath, 'utf8'), cert = readFileSync(certPath, 'utf8');
  const server = new Worker(`
    const {parentPort,workerData}=require('node:worker_threads');
    const net=require('node:net'),tls=require('node:tls'),context=tls.createSecureContext(workerData);
    const sasl=Buffer.concat([Buffer.from([82,0,0,0,23,0,0,0,10]),Buffer.from('SCRAM-SHA-256\\0\\0')]);
    const sf=Buffer.from('r=AAECAwQFBgcICQoLDA0ODxARserver,s=W22ZaJ0SNY7soEsUEjb6gQ==,i=4096');
    const cont=Buffer.concat([Buffer.from([82,0,0,0,sf.length+8,0,0,0,11]),sf]);
    const fin=Buffer.from('v=QAdQmJ+lRK7pdc/DBEeFAbUmtBhFLhQXsQNpv3KJgJQ=');
    const final=Buffer.concat([Buffer.from([82,0,0,0,fin.length+8,0,0,0,12]),fin]);
    const tail=Buffer.from([82,0,0,0,8,0,0,0,0,75,0,0,0,12,0,0,0,1,0,0,0,2,90,0,0,0,5,73]);
    const ready=Buffer.from([90,0,0,0,5,73]);
    const command=tag=>Buffer.concat([Buffer.from([67,0,0,0,tag.length+5]),Buffer.from(tag+'\\0')]);
    let connections=0; const queries=[];
    const server=net.createServer(socket=>{connections++;let plain=Buffer.alloc(0);socket.on('data',function ssl(c){plain=Buffer.concat([plain,c]);if(plain.length<8)return;socket.removeListener('data',ssl);socket.write(Buffer.from('S'));
      const secure=new tls.TLSSocket(socket,{isServer:true,secureContext:context});let input=Buffer.alloc(0),stage=0;
      secure.on('error',()=>{});secure.on('data',c2=>{input=Buffer.concat([input,c2]);while(true){const needed=stage===0?(input.length>=4?input.readInt32BE(0):Infinity):(input.length>=5?input.readInt32BE(1)+1:Infinity);if(input.length<needed)break;const frame=input.subarray(0,needed);input=input.subarray(needed);
        if(stage===0){secure.write(sasl);stage=1}else if(stage===1){secure.write(cont);stage=2}else if(stage===2){secure.write(Buffer.concat([final,tail]));stage=3}else if(frame[0]===81){const sql=frame.subarray(5,frame.length-1).toString();queries.push(sql);parentPort.postMessage({sql});secure.write(Buffer.concat([command(sql),ready]))}}});secure.resume()})});
    server.listen(0,'127.0.0.1',()=>parentPort.postMessage({port:server.address().port}));
    parentPort.on('message',()=>{parentPort.postMessage({connections,queries});server.close()});
  `, { eval: true, workerData: { key, cert } });
  const [{ port }] = await once(server, 'message'); const wireQueries = [];
  server.on('message', message => { if (message.sql) wireQueries.push(message.sql); });
  const broker = createNodeTransportBroker({ endpointAllowlist: [`localhost:${port}`], resolvedAddressAllowlist: ['127.0.0.1'],
    maxConnections: 2, connectTimeoutMs: 1500, readTimeoutMs: 1500, maxReadBytes: 65536, maxWriteBytes: 65536, trustedCaPem: cert });
  try {
    const transportGrants = ['transport-connect', 'tls-open', 'tls-server-end-point', 'transport-write', 'transport-read', 'transport-close'];
    const db = await instantiateKotobaComponent(readFileSync(dbPath), hostCaps({ grants: transportGrants,
      limits: { maxTransportConnections: 2, allowWriteImports: true } }), { transport: broker });
    const scramGrants = [...transportGrants, 'scram-sha256', 'random-bytes', 'pg-cancel-register', 'pg-cancel'];
    const scram = await instantiateKotobaComponent(readFileSync(scramPath), hostCaps({ grants: scramGrants,
      limits: { maxTransportConnections: 2, maxScramProofs: 2, maxRandomBytes: 36, maxPgCancelHandles: 2,
        maxPgCancelRequests: 2, allowSecretImports: true, allowWriteImports: true, scramCredentialAllowlist: ['db/primary'] } }),
      { transport: broker, credentials: createNodeCredentialProvider({ credentialAllowlist: ['db/primary'], maxProofs: 2,
        credentials: { 'db/primary': 'pencil' } }), randomBytes: n => Uint8Array.from({ length: n }, (_, i) => i) });
    const realProvider = createNodePostgresqlPoolProvider({ scramInstance: scram.instance, queryInstance: db.instance,
      maxConnectionsPerPool: 2, maxLeases: 2 });
    const realConsumer = await instantiateLinkedKotobaComponents(readFileSync(consumerPath),
      hostCaps({ grants, limits: { allowSecretImports: true, allowWriteImports: true } }),
      [{ instance: realProvider.instance, specs: PG_POOL_LINKS }]);
    assert.equal(realConsumer.instance.exports.run(port), 1, 'pool composes over real verified TLS/SCRAM Kotoba providers');
    for (let i = 0; wireQueries.length < 6 && i < 50; i++) await new Promise(resolve => setTimeout(resolve, 10));
    assert.deepEqual(wireQueries, ['ROLLBACK', 'DISCARD ALL', 'ROLLBACK', 'DISCARD ALL', 'ROLLBACK', 'DISCARD ALL']);
    realProvider.closeAll();
  } finally {
    await broker.closeAll(); server.postMessage('close'); await server.terminate();
  }
  console.log('compiled PostgreSQL pool consumer: affine leases, bounds, reset, health, drain, close and TLS/SCRAM composition pass');
} finally {
  rmSync(dir, { recursive: true, force: true });
}
