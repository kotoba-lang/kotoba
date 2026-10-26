import { parentPort } from 'node:worker_threads';
import { lookup } from 'node:dns/promises';
import net from 'node:net';
import tls from 'node:tls';
import { createHash, X509Certificate } from 'node:crypto';

const handles = new Map();
let nextHandle = 1;

function finish(sab, result, bytes) {
  const control = new Int32Array(sab, 0, 4);
  if (bytes) new Uint8Array(sab, 16, bytes.length).set(bytes);
  Atomics.store(control, 2, bytes?.length || 0);
  Atomics.store(control, 1, result);
  Atomics.store(control, 0, 1);
  Atomics.notify(control, 0);
}

function once(socket, successEvent, timeoutMs) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => done(new Error('transport timeout')), timeoutMs);
    const done = (error) => {
      clearTimeout(timer);
      socket.off(successEvent, ok);
      socket.off('error', fail);
      socket.off('timeout', timedOut);
      error ? reject(error) : resolve();
    };
    const ok = () => done();
    const fail = (error) => done(error);
    const timedOut = () => done(new Error('transport timeout'));
    socket.once(successEvent, ok);
    socket.once('error', fail);
    socket.once('timeout', timedOut);
  });
}

async function command(message) {
  const { op, sab, timeoutMs } = message;
  if (op === 'connect') {
    const addresses = await lookup(message.host, { all: true, verbatim: true });
    const selected = addresses.find(({ address }) => message.resolvedAddresses.includes(address));
    if (!selected) return finish(sab, 0);
    const socket = net.createConnection({ host: selected.address, port: message.port, family: selected.family });
    socket.setTimeout(message.readTimeoutMs);
    try {
      await once(socket, 'connect', timeoutMs);
      const handle = nextHandle++;
      handles.set(handle, { kind: 'tcp', socket, host: message.host, port: message.port,
        resolvedAddress: selected.address, family: selected.family });
      return finish(sab, handle);
    } catch (_) {
      socket.destroy();
      return finish(sab, 0);
    }
  }
  const handle = Number(message.handle);
  const entry = handles.get(handle);
  if (op === 'tls') {
    handles.delete(handle);
    if (!entry || entry.kind !== 'tcp' || entry.host !== message.serverName) {
      entry?.socket.destroy();
      return finish(sab, 0);
    }
    const socket = tls.connect({ socket: entry.socket, servername: message.serverName,
      ca: message.trustedCaPem || undefined, rejectUnauthorized: true, minVersion: 'TLSv1.2' });
    socket.setTimeout(message.readTimeoutMs);
    try {
      await once(socket, 'secureConnect', timeoutMs);
      const tlsHandle = nextHandle++;
      handles.set(tlsHandle, { ...entry, kind: 'tls', socket });
      return finish(sab, tlsHandle);
    } catch (_) {
      socket.destroy();
      return finish(sab, 0);
    }
  }
  if (!entry) return finish(sab, -1);
  if (op === 'cancel-register') {
    if (entry.kind !== 'tls') return finish(sab, 0);
    const cancelHandle = nextHandle++;
    handles.set(cancelHandle, { kind: 'pg-cancel', host: entry.host, port: entry.port,
      resolvedAddress: entry.resolvedAddress, family: entry.family,
      pid: message.pid, secret: message.secret });
    return finish(sab, cancelHandle);
  }
  if (op === 'cancel') {
    handles.delete(handle);
    if (entry.kind !== 'pg-cancel') return finish(sab, -1);
    const socket = net.createConnection({ host: entry.resolvedAddress, port: entry.port, family: entry.family });
    try {
      await once(socket, 'connect', timeoutMs);
      const request = new Uint8Array(16);
      const view = new DataView(request.buffer);
      view.setInt32(0, 16); view.setInt32(4, 80877102); view.setInt32(8, entry.pid); view.setInt32(12, entry.secret);
      await new Promise((resolve, reject) => socket.end(request, error => error ? reject(error) : resolve()));
      return finish(sab, 0);
    } catch (_) { socket.destroy(); return finish(sab, -1); }
  }
  if (op === 'write') {
    const bytes = new Uint8Array(sab, 16, message.length).slice();
    try {
      if (!entry.socket.write(bytes)) await once(entry.socket, 'drain', timeoutMs);
      return finish(sab, bytes.length);
    } catch (_) { return finish(sab, -1); }
  }
  if (op === 'read') {
    try {
      const immediate = entry.socket.read(message.capacity);
      const bytes = immediate || (entry.socket.readableEnded ? new Uint8Array() : await new Promise((resolve, reject) => {
        const timer = setTimeout(() => done(new Error('transport timeout')), timeoutMs);
        const done = (error, value) => {
          clearTimeout(timer); entry.socket.off('data', data); entry.socket.off('end', end);
          entry.socket.off('error', fail); error ? reject(error) : resolve(value);
        };
        const data = (chunk) => {
          entry.socket.pause();
          if (chunk.length > message.capacity) entry.socket.unshift(chunk.subarray(message.capacity));
          done(null, chunk.subarray(0, message.capacity));
        };
        const end = () => done(null, new Uint8Array());
        const fail = (error) => done(error);
        entry.socket.once('data', data); entry.socket.once('end', end); entry.socket.once('error', fail);
        entry.socket.resume();
      }));
      return finish(sab, bytes.length, new Uint8Array(bytes));
    } catch (_) { return finish(sab, -1); }
  }
  if (op === 'tls-end-point') {
    if (entry.kind !== 'tls') return finish(sab, -1);
    try {
      const peer = entry.socket.getPeerCertificate(true);
      const signature = new X509Certificate(peer.raw).signatureAlgorithm || '';
      const algorithm = /SHA512/i.test(signature) ? 'sha512' : /SHA384/i.test(signature) ? 'sha384' : 'sha256';
      const digest = createHash(algorithm).update(peer.raw).digest();
      return finish(sab, digest.length, digest);
    } catch (_) { return finish(sab, -1); }
  }
  if (op === 'close') {
    handles.delete(handle); entry.socket?.destroy(); return finish(sab, 0);
  }
  finish(sab, -1);
}

parentPort.on('message', (message) => command(message).catch(() => finish(message.sab, -1)));
parentPort.on('close', () => { for (const { socket } of handles.values()) socket.destroy(); handles.clear(); });
