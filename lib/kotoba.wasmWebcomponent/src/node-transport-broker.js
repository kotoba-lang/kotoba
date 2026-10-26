import { Worker } from 'node:worker_threads';
import net from 'node:net';

function canonicalHost(value) {
  if (typeof value !== 'string' || value !== value.trim() || !value || value.includes('\0')) return null;
  const host = value.endsWith('.') ? value.slice(0, -1) : value;
  return net.isIP(host) ? host.toLowerCase() : /^[a-z0-9.-]+$/i.test(host) ? host.toLowerCase() : null;
}

export function createNodeTransportBroker(options = {}) {
  const endpoints = new Set(options.endpointAllowlist || []);
  const resolvedAddresses = [...new Set(options.resolvedAddressAllowlist || [])];
  const maxConnections = options.maxConnections ?? 0;
  const connectTimeoutMs = options.connectTimeoutMs ?? 5000;
  const readTimeoutMs = options.readTimeoutMs ?? 5000;
  const maxReadBytes = options.maxReadBytes ?? 1048576;
  const maxWriteBytes = options.maxWriteBytes ?? 1048576;
  const maxCancelHandles = options.maxCancelHandles ?? 0;
  const maxCancelRequests = options.maxCancelRequests ?? 0;
  const trustedCaPem = options.trustedCaPem;
  const worker = new Worker(new URL('./node-transport-worker.js', import.meta.url));
  let connections = 0, readBytes = 0, writeBytes = 0, cancelHandles = 0, cancelRequests = 0, closed = false;

  const request = (message, input = new Uint8Array(), capacity = 0) => {
    if (closed) return { result: -1, bytes: new Uint8Array() };
    const sab = new SharedArrayBuffer(16 + Math.max(input.length, capacity));
    if (input.length) new Uint8Array(sab, 16, input.length).set(input);
    const control = new Int32Array(sab, 0, 4);
    worker.postMessage({ ...message, sab, timeoutMs: message.timeoutMs ?? readTimeoutMs });
    const waited = Atomics.wait(control, 0, 0, (message.timeoutMs ?? readTimeoutMs) + 50);
    if (waited === 'timed-out') { closed = true; void worker.terminate(); return { result: -1, bytes: new Uint8Array() }; }
    const length = Atomics.load(control, 2);
    return { result: Atomics.load(control, 1), bytes: new Uint8Array(sab, 16, length).slice() };
  };

  return {
    connect(hostValue, port) {
      const host = canonicalHost(hostValue);
      const endpoint = `${net.isIP(host) === 6 ? `[${host}]` : host}:${port}`;
      if (!host || !Number.isInteger(port) || port < 1 || port > 65535 || !endpoints.has(endpoint) ||
          resolvedAddresses.length === 0 || connections >= maxConnections) return 0n;
      const { result } = request({ op: 'connect', host, port, resolvedAddresses,
        readTimeoutMs, timeoutMs: connectTimeoutMs });
      if (result > 0) connections += 1;
      return BigInt(Math.max(0, result));
    },
    tlsOpen(handle, serverNameValue) {
      const serverName = canonicalHost(serverNameValue);
      if (!serverName || handle <= 0n) return 0n;
      const { result } = request({ op: 'tls', handle, serverName, trustedCaPem,
        readTimeoutMs, timeoutMs: connectTimeoutMs });
      return BigInt(Math.max(0, result));
    },
    tlsServerEndPoint(handle, capacity) {
      if (capacity < 32 || capacity > 64) return null;
      const reply = request({ op: 'tls-end-point', handle }, new Uint8Array(), capacity);
      return reply.result > 0 ? reply.bytes : null;
    },
    write(handle, bytes) {
      if (!(bytes instanceof Uint8Array) || writeBytes + bytes.length > maxWriteBytes) return -1;
      const { result } = request({ op: 'write', handle, length: bytes.length }, bytes);
      if (result >= 0) writeBytes += result;
      return result;
    },
    read(handle, capacity) {
      const allowed = Math.min(capacity, maxReadBytes - readBytes);
      if (!Number.isInteger(allowed) || allowed <= 0) return null;
      const reply = request({ op: 'read', handle, capacity: allowed }, new Uint8Array(), allowed);
      if (reply.result < 0) return null;
      readBytes += reply.bytes.length;
      return reply.bytes;
    },
    registerCancel(handle, pid, secret) {
      if (cancelHandles >= maxCancelHandles || !Number.isInteger(pid) || !Number.isInteger(secret)) return 0;
      const result = request({ op: 'cancel-register', handle, pid, secret }).result;
      if (result > 0) cancelHandles += 1;
      return Math.max(0, result);
    },
    cancel(handle) {
      if (cancelRequests >= maxCancelRequests) return -1;
      const result = request({ op: 'cancel', handle }).result;
      if (result === 0) cancelRequests += 1;
      return result;
    },
    close(handle) { return request({ op: 'close', handle }).result; },
    closeAll() { if (!closed) { closed = true; return worker.terminate(); } return Promise.resolve(); },
  };
}
