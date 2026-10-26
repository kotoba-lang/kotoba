import assert from 'node:assert/strict';
import { Worker } from 'node:worker_threads';
import { once } from 'node:events';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createNodeTransportBroker } from '../src/node-transport-broker.js';
import { actorHostImports, hostCaps } from '../src/actor-host.js';

const server = new Worker(`
  const { parentPort } = require('node:worker_threads');
  const net = require('node:net');
  const server = net.createServer(socket => socket.on('data', bytes => socket.write(bytes)));
  server.listen(0, '127.0.0.1', () => parentPort.postMessage(server.address().port));
  parentPort.on('message', () => server.close());
`, { eval: true });

const [port] = await once(server, 'message');
const broker = createNodeTransportBroker({
  endpointAllowlist: [`127.0.0.1:${port}`], resolvedAddressAllowlist: ['127.0.0.1'],
  maxConnections: 1, connectTimeoutMs: 1000, readTimeoutMs: 1000,
  maxReadBytes: 16, maxWriteBytes: 16,
});

try {
  assert.equal(broker.connect('localhost', port), 0n, 'exact host scope is mandatory');
  const handle = broker.connect('127.0.0.1', port);
  assert.ok(handle > 0n);
  assert.equal(broker.connect('127.0.0.1', port), 0n, 'connection quota is affine and finite');
  assert.equal(broker.write(handle, new TextEncoder().encode('kotoba')), 6);
  const echoed = broker.read(handle, 16);
  assert.ok(echoed instanceof Uint8Array, 'read returns bytes before its finite timeout');
  assert.equal(new TextDecoder().decode(echoed), 'kotoba');
  assert.equal(broker.close(handle), 0);
  assert.equal(broker.close(handle), -1, 'closed handles cannot be reused');

  const memory = new WebAssembly.Memory({ initial: 1 });
  new Uint8Array(memory.buffer, 0, 9).set(new TextEncoder().encode('127.0.0.1'));
  const caps = hostCaps({
    grants: ['transport-connect'],
    limits: { maxTransportConnections: 1 },
  });
  const deniedBroker = createNodeTransportBroker();
  try {
    const imports = actorHostImports(['transport-connect'], caps, { memory }, { transport: deniedBroker });
    assert.equal(imports.transport_connect(0, 9, port), 0n, 'default broker policy denies all endpoints');
  } finally { await deniedBroker.closeAll(); }
} finally {
  await broker.closeAll();
  server.postMessage('close');
  await server.terminate();
}

console.log('node transport broker: bounded TCP, quotas, affine handles, and default denial pass');

const fixtureDir = mkdtempSync(join(tmpdir(), 'kotoba-node-tls-'));
try {
  const keyPath = join(fixtureDir, 'key.pem');
  const certPath = join(fixtureDir, 'cert.pem');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256',
    '-keyout', keyPath, '-out', certPath, '-days', '1', '-subj', '/CN=localhost',
    '-addext', 'subjectAltName=DNS:localhost'], { stdio: 'ignore' });
  const key = readFileSync(keyPath, 'utf8');
  const cert = readFileSync(certPath, 'utf8');
  const tlsServer = new Worker(`
    const { parentPort, workerData } = require('node:worker_threads');
    const tls = require('node:tls');
    const server = tls.createServer(workerData, socket => socket.on('data', bytes => socket.write(bytes)));
    server.listen(0, '127.0.0.1', () => parentPort.postMessage(server.address().port));
    parentPort.on('message', () => server.close());
  `, { eval: true, workerData: { key, cert } });
  const [tlsPort] = await once(tlsServer, 'message');
  const tlsBroker = createNodeTransportBroker({
    endpointAllowlist: [`localhost:${tlsPort}`], resolvedAddressAllowlist: ['127.0.0.1'],
    maxConnections: 1, connectTimeoutMs: 1000, readTimeoutMs: 1000,
    trustedCaPem: cert,
  });
  try {
    const tcpHandle = tlsBroker.connect('localhost', tlsPort);
    assert.ok(tcpHandle > 0n);
    assert.equal(tlsBroker.tlsOpen(tcpHandle, 'example.test'), 0n, 'TLS SNI must equal the scoped endpoint host');
  } finally { await tlsBroker.closeAll(); }

  const verifiedBroker = createNodeTransportBroker({
    endpointAllowlist: [`localhost:${tlsPort}`], resolvedAddressAllowlist: ['127.0.0.1'],
    maxConnections: 1, connectTimeoutMs: 1000, readTimeoutMs: 1000, trustedCaPem: cert,
  });
  try {
    const tcpHandle = verifiedBroker.connect('localhost', tlsPort);
    const tlsHandle = verifiedBroker.tlsOpen(tcpHandle, 'localhost');
    assert.ok(tlsHandle > 0n, 'certificate and hostname verification complete');
    assert.equal(verifiedBroker.tlsServerEndPoint(tlsHandle, 64)?.length, 32, 'RFC5929 digest is bounded');
    assert.equal(verifiedBroker.write(tlsHandle, new TextEncoder().encode('tls')), 3);
    assert.equal(new TextDecoder().decode(verifiedBroker.read(tlsHandle, 16)), 'tls');
  } finally {
    await verifiedBroker.closeAll();
    tlsServer.postMessage('close'); await tlsServer.terminate();
  }
  console.log('node transport broker: verified TLS, exact SNI, RFC5929 digest, and TLS I/O pass');
} finally { rmSync(fixtureDir, { recursive: true, force: true }); }

const cancelFixtureDir = mkdtempSync(join(tmpdir(), 'kotoba-node-cancel-'));
try {
  const keyPath = join(cancelFixtureDir, 'key.pem');
  const certPath = join(cancelFixtureDir, 'cert.pem');
  execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256',
    '-keyout', keyPath, '-out', certPath, '-days', '1', '-subj', '/CN=localhost',
    '-addext', 'subjectAltName=DNS:localhost'], { stdio: 'ignore' });
  const key = readFileSync(keyPath, 'utf8');
  const cert = readFileSync(certPath, 'utf8');
  const cancelServer = new Worker(`
    const { parentPort, workerData } = require('node:worker_threads');
    const net = require('node:net'); const tls = require('node:tls');
    const context = tls.createSecureContext(workerData);
    const server = net.createServer(socket => socket.once('data', first => {
      socket.pause();
      if (first[0] === 22) {
        socket.unshift(first);
        const secure = new tls.TLSSocket(socket, { isServer: true, secureContext: context });
        secure.on('error', () => {}); secure.on('data', () => {}); secure.resume();
      } else {
        let all = first;
        const complete = () => { if (all.length >= 16) {
          parentPort.postMessage({ cancel: all.subarray(0, 16) }); socket.end(); return true;
        }};
        if (!complete()) socket.on('data', chunk => { all = Buffer.concat([all, chunk]); complete(); });
        socket.resume();
      }
    }));
    server.listen(0, '127.0.0.1', () => parentPort.postMessage({ port: server.address().port }));
    parentPort.on('message', () => server.close());
  `, { eval: true, workerData: { key, cert } });
  const [{ port }] = await once(cancelServer, 'message');
  const cancelMessages = [];
  cancelServer.on('message', message => { if (message.cancel) cancelMessages.push(message.cancel); });
  const cancelBroker = createNodeTransportBroker({
    endpointAllowlist: [`localhost:${port}`], resolvedAddressAllowlist: ['127.0.0.1'],
    maxConnections: 1, maxCancelHandles: 1, maxCancelRequests: 1,
    connectTimeoutMs: 1000, readTimeoutMs: 1000, trustedCaPem: cert,
  });
  try {
    const tcp = cancelBroker.connect('localhost', port);
    const channel = cancelBroker.tlsOpen(tcp, 'localhost');
    assert.ok(channel > 0n);
    const cancelHandle = cancelBroker.registerCancel(channel, 1234, -559038737);
    assert.ok(cancelHandle > 0);
    assert.equal(cancelBroker.cancel(cancelHandle), 0);
    for (let i = 0; cancelMessages.length < 1 && i < 20; i += 1) {
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    assert.equal(cancelMessages.length, 1, 'pinned peer received one fixed CancelRequest');
    const cancel = cancelMessages[0];
    const view = new DataView(cancel.buffer, cancel.byteOffset, cancel.byteLength);
    assert.deepEqual([view.getInt32(0), view.getInt32(4), view.getInt32(8), view.getInt32(12)],
      [16, 80877102, 1234, -559038737]);
    assert.equal(cancelBroker.cancel(cancelHandle), -1, 'one-shot cancellation authority cannot be reused');
  } finally {
    await cancelBroker.closeAll(); cancelServer.postMessage('close'); await cancelServer.terminate();
  }
  console.log('node transport broker: pinned-peer one-shot PostgreSQL CancelRequest pass');
} finally { rmSync(cancelFixtureDir, { recursive: true, force: true }); }
