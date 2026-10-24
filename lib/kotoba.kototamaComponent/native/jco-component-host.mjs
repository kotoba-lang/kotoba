#!/usr/bin/env node
// Independent JavaScript Component Model qualification host.
// It implements the same closed JSON-line protocol as the Wasmtime micro-TCB,
// but execution is through pinned @bytecodealliance/jco-generated bindings.

import { readFileSync, readSync, writeSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';

let buffered = '';
function readLine() {
  for (;;) {
    const newline = buffered.indexOf('\n');
    if (newline >= 0) {
      const line = buffered.slice(0, newline);
      buffered = buffered.slice(newline + 1);
      return line;
    }
    const bytes = Buffer.alloc(4096);
    const n = readSync(0, bytes, 0, bytes.length, null);
    if (n === 0) throw new Error('provider closed protocol before responding');
    buffered += bytes.subarray(0, n).toString('utf8');
  }
}

function send(value) {
  writeSync(1, `${JSON.stringify(value)}\n`);
}

const supported = Object.freeze({
  'aiueos-identity-sign': {
    operation: 'identity/sign', specifier: 'aiueos:capability/identity', exportName: 'sign',
  },
  'aiueos-identity-verify': {
    operation: 'identity/verify', specifier: 'aiueos:capability/identity', exportName: 'verify',
  },
  'aiueos-hash-sha256': {
    operation: 'hash/sha256', specifier: 'aiueos:capability/hash', exportName: 'sha256',
  },
  'aiueos-http-post': {
    operation: 'http/post', specifier: 'aiueos:capability/http', exportName: 'post',
  },
  'aiueos-log-read': {
    operation: 'log/read', specifier: 'aiueos:capability/log', exportName: 'read',
  },
  'aiueos-clock-now': {
    operation: 'clock/now',
    specifier: 'kotoba:application/clock',
    exportName: 'now',
    resourceClass: 'NowCapability',
    issueName: 'issueNow',
    executeName: 'executeNow',
  },
  'aiueos-log-append': {
    operation: 'log/append',
    specifier: 'kotoba:application/log',
    exportName: 'append',
    resourceClass: 'AppendCapability',
    issueName: 'issueAppend',
    executeName: 'executeAppend',
  },
  'aiueos-http-get-stream': {
    operation: 'http/get-stream',
    specifier: 'aiueos:capability/http',
    exportName: 'getStream',
  },
  'aiueos-object-get-stream': {
    operation: 'object/get-stream',
    specifier: 'aiueos:capability/object-store',
    exportName: 'getStream',
  },
  'aiueos-object-put-block': {
    operation: 'object/put-block',
    specifier: 'aiueos:capability/object-store',
    exportName: 'putBlock',
  },
  'aiueos-object-compare-and-set-ref': {
    operation: 'object/compare-and-set-ref',
    specifier: 'aiueos:capability/object-store',
    exportName: 'compareAndSetRef',
  },
});

function validateAbility(name, ability) {
  const binding = supported[name];
  if (!binding) throw new Error(`unrecognized aiueos Component import: ${name}`);
  if (!ability || ability.operation !== binding.operation ||
      !ability.target || !ability['audit-id'] ||
      !Number.isSafeInteger(ability['max-bytes']) || ability['max-bytes'] <= 0 ||
      !Number.isSafeInteger(ability['max-items']) || ability['max-items'] <= 0 ||
      !Number.isSafeInteger(ability['deadline-ms']) || ability['deadline-ms'] <= 0) {
    throw new Error(`import ${name} is bound to an invalid ability`);
  }
  return binding;
}

function providerSource(name, ability, binding, linear) {
  const exportName = binding.exportName;
  if (linear) return `
import { readSync, writeSync } from 'node:fs';
let buffered = '';
function line() {
  for (;;) {
    const n = buffered.indexOf('\\n');
    if (n >= 0) { const out = buffered.slice(0, n); buffered = buffered.slice(n + 1); return out; }
    const b = Buffer.alloc(4096);
    const count = readSync(0, b, 0, b.length, null);
    if (count === 0) throw new Error('provider closed protocol before responding');
    buffered += b.subarray(0, count).toString('utf8');
  }
}

export class ${binding.resourceClass} {}
export function ${binding.issueName}() { return new ${binding.resourceClass}(); }
export function ${binding.executeName}(cap, value) {
  if (!(cap instanceof ${binding.resourceClass})) throw new Error('invalid linear capability resource');
  writeSync(1, JSON.stringify({
    type: 'provider-call', import: ${JSON.stringify(name)},
    ability: ${JSON.stringify(ability)}, payload: { value: Number(value) }
  }) + '\\n');
  const response = JSON.parse(line());
  if (response.type !== 'provider-result' || response.import !== ${JSON.stringify(name)} ||
      !Number.isSafeInteger(response.value)) throw new Error('invalid provider-result response');
  return BigInt(response.value);
}
`;
  return `
import { readSync, writeSync } from 'node:fs';
let buffered = '';
function line() {
  for (;;) {
    const n = buffered.indexOf('\\n');
    if (n >= 0) { const out = buffered.slice(0, n); buffered = buffered.slice(n + 1); return out; }
    const b = Buffer.alloc(4096);
    const count = readSync(0, b, 0, b.length, null);
    if (count === 0) throw new Error('provider closed protocol before responding');
    buffered += b.subarray(0, count).toString('utf8');
  }
}
export function ${exportName}(value) {
  writeSync(1, JSON.stringify({
    type: 'provider-call',
    import: ${JSON.stringify(name)},
    ability: ${JSON.stringify(ability)},
    payload: { value: Number(value) }
  }) + '\\n');
  const response = JSON.parse(line());
  if (response.type !== 'provider-result' || response.import !== ${JSON.stringify(name)} ||
      !Number.isSafeInteger(response.value)) throw new Error('invalid provider-result response');
  return BigInt(response.value);
}
`;
}

function typedCapabilitySource(ability, grantRequest) {
  return `
export class Grant {
  constructor(operation) { this.operation = operation; }
}
export class BytesStream {
  constructor(bytes) { this.bytes = bytes; this.offset = 0; this.cancelled = false; }
  read(maxBytes) {
    if (this.cancelled || !Number.isSafeInteger(maxBytes) || maxBytes <= 0) throw 'provider-failed';
    const end = Math.min(this.offset + maxBytes, this.bytes.byteLength);
    const bytes = this.bytes.slice(this.offset, end);
    this.offset = end;
    return { bytes, done: this.offset === this.bytes.byteLength };
  }
  cancel() { this.cancelled = true; }
}
export class BytesTask {
  constructor(bytes) { this.bytes = bytes; this.cancelled = false; this.polled = false; }
  poll() {
    if (this.cancelled || this.polled) throw 'provider-failed';
    this.polled = true;
    return { tag: 'ready', val: new BytesStream(this.bytes) };
  }
  cancel() { this.cancelled = true; }
}
export function acquire(request) {
  if (request !== ${JSON.stringify(grantRequest)}) throw 'provider-failed';
  return new Grant(${JSON.stringify(ability.operation)});
}
`;
}

function typedClockSource(name, ability, lease) {
  return `
import { readSync, writeSync } from 'node:fs';
import { Grant } from './provider-capability.js';
let buffered = '';
let calls = 0;
function line() {
  for (;;) {
    const n = buffered.indexOf('\\n');
    if (n >= 0) { const out = buffered.slice(0, n); buffered = buffered.slice(n + 1); return out; }
    const b = Buffer.alloc(4096);
    const count = readSync(0, b, 0, b.length, null);
    if (count === 0) throw new Error('provider closed protocol before responding');
    buffered += b.subarray(0, count).toString('utf8');
  }
}
export function now(grant) {
  if (!(grant instanceof Grant) || grant.operation !== ${JSON.stringify(ability.operation)})
    throw 'provider-failed';
  calls += 1;
  if (calls > ${JSON.stringify(ability['max-items'])}) throw 'quota';
  writeSync(1, JSON.stringify({
    type: 'provider-call', import: ${JSON.stringify(name)},
    ability: ${JSON.stringify(ability)}, payload: null
  }) + '\\n');
  const response = JSON.parse(line());
  const proof = response['lease-proof'];
  if (response.type !== 'provider-result' || response.import !== ${JSON.stringify(name)} ||
      response['audit-id'] !== ${JSON.stringify(ability['audit-id'])} ||
      typeof response['audit-receipt'] !== 'string' || response['audit-receipt'].length === 0 ||
      !proof || proof.epoch !== ${JSON.stringify(lease.epoch)} ||
      proof['expires-at'] !== ${JSON.stringify(lease['expires-at'])} ||
      proof['observed-at'] < ${JSON.stringify(lease['not-before'])} ||
      proof['observed-at'] > ${JSON.stringify(lease['expires-at'])} ||
      !Number.isSafeInteger(response.payload)) throw 'provider-failed';
  return BigInt(response.payload);
}
`;
}

function typedLogSource(name, ability, lease) {
  return `
import { readSync, writeSync } from 'node:fs';
import { Grant } from './provider-capability.js';
let buffered = '';
let calls = 0;
function line() {
  for (;;) {
    const n = buffered.indexOf('\\n');
    if (n >= 0) { const out = buffered.slice(0, n); buffered = buffered.slice(n + 1); return out; }
    const b = Buffer.alloc(4096);
    const count = readSync(0, b, 0, b.length, null);
    if (count === 0) throw new Error('provider closed protocol before responding');
    buffered += b.subarray(0, count).toString('utf8');
  }
}
export function append(grant, request) {
  if (!(grant instanceof Grant) || grant.operation !== ${JSON.stringify(ability.operation)})
    throw 'provider-failed';
  if (!request || !(request.bytes instanceof Uint8Array)) throw 'provider-failed';
  calls += 1;
  if (calls > ${JSON.stringify(ability['max-items'])}) throw 'quota';
  if (request.bytes.byteLength > ${JSON.stringify(ability['max-bytes'])}) throw 'quota';
  writeSync(1, JSON.stringify({
    type: 'provider-call', import: ${JSON.stringify(name)},
    ability: ${JSON.stringify(ability)}, payload: { bytes: Array.from(request.bytes) }
  }) + '\\n');
  const response = JSON.parse(line());
  const proof = response['lease-proof'];
  if (response.type !== 'provider-result' || response.import !== ${JSON.stringify(name)} ||
      response['audit-id'] !== ${JSON.stringify(ability['audit-id'])} ||
      typeof response['audit-receipt'] !== 'string' || response['audit-receipt'].length === 0 ||
      !proof || proof.epoch !== ${JSON.stringify(lease.epoch)} ||
      proof['expires-at'] !== ${JSON.stringify(lease['expires-at'])} ||
      proof['observed-at'] < ${JSON.stringify(lease['not-before'])} ||
      proof['observed-at'] > ${JSON.stringify(lease['expires-at'])} ||
      response.payload !== null) throw 'provider-failed';
}
`;
}

function typedStreamSource(name, ability, lease) {
  const objectStore = name === 'aiueos-object-get-stream';
  return `
import { readSync, writeSync } from 'node:fs';
import { Grant, BytesTask } from './provider-capability.js';
let buffered = '';
let calls = 0;
function line() {
  for (;;) {
    const n = buffered.indexOf('\\n');
    if (n >= 0) { const out = buffered.slice(0, n); buffered = buffered.slice(n + 1); return out; }
    const b = Buffer.alloc(4096);
    const count = readSync(0, b, 0, b.length, null);
    if (count === 0) throw new Error('provider closed protocol before responding');
    buffered += b.subarray(0, count).toString('utf8');
  }
}
export function getStream(grant, request) {
  if (!(grant instanceof Grant) || grant.operation !== ${JSON.stringify(ability.operation)})
    throw 'provider-failed';
  if (!request || ${objectStore
    ? "typeof request.key !== 'string'"
    : "typeof request.path !== 'string' || !Array.isArray(request.headers)"})
    throw 'provider-failed';
  calls += 1;
  if (calls > ${JSON.stringify(ability['max-items'])}) throw 'quota';
  writeSync(1, JSON.stringify({
    type: 'provider-call', import: ${JSON.stringify(name)},
    ability: ${JSON.stringify(ability)},
    payload: ${objectStore
      ? "{ key: request.key }"
      : "{ path: request.path, headers: request.headers }"}
  }) + '\\n');
  const response = JSON.parse(line());
  const proof = response['lease-proof'];
  const bytes = response.payload && response.payload.bytes;
  if (response.type !== 'provider-result' || response.import !== ${JSON.stringify(name)} ||
      response['audit-id'] !== ${JSON.stringify(ability['audit-id'])} ||
      typeof response['audit-receipt'] !== 'string' || response['audit-receipt'].length === 0 ||
      !proof || proof.epoch !== ${JSON.stringify(lease.epoch)} ||
      proof['expires-at'] !== ${JSON.stringify(lease['expires-at'])} ||
      proof['observed-at'] < ${JSON.stringify(lease['not-before'])} ||
      proof['observed-at'] > ${JSON.stringify(lease['expires-at'])} ||
      !Array.isArray(bytes) || bytes.length > ${JSON.stringify(ability['max-bytes'])} ||
      bytes.some((value) => !Number.isSafeInteger(value) || value < 0 || value > 255))
    throw 'provider-failed';
  return new BytesTask(Uint8Array.from(bytes));
}
`;
}

function typedObjectWriteSource(name, ability, lease) {
  const cas = name === 'aiueos-object-compare-and-set-ref';
  return `
import { readSync, writeSync } from 'node:fs';
import { Grant } from './provider-capability.js';
let buffered = '';
let calls = 0;
function line() {
  for (;;) {
    const n = buffered.indexOf('\\n');
    if (n >= 0) { const out = buffered.slice(0, n); buffered = buffered.slice(n + 1); return out; }
    const b = Buffer.alloc(4096);
    const count = readSync(0, b, 0, b.length, null);
    if (count === 0) throw new Error('provider closed protocol before responding');
    buffered += b.subarray(0, count).toString('utf8');
  }
}
export function ${cas ? 'compareAndSetRef' : 'putBlock'}(grant, request) {
  if (!(grant instanceof Grant) || grant.operation !== ${JSON.stringify(ability.operation)})
    throw 'provider-failed';
  if (!request || typeof request.key !== 'string' ||
      !(request.bytes instanceof Uint8Array) ||
      request.bytes.byteLength > ${JSON.stringify(ability['max-bytes'])}${cas
        ? " || (request.expectedEtag !== null && typeof request.expectedEtag !== 'string')"
        : ''})
    throw 'provider-failed';
  calls += 1;
  if (calls > ${JSON.stringify(ability['max-items'])}) throw 'quota';
  writeSync(1, JSON.stringify({
    type: 'provider-call', import: ${JSON.stringify(name)},
    ability: ${JSON.stringify(ability)},
    payload: ${cas
      ? "{ key: request.key, 'expected-etag': request.expectedEtag, bytes: Array.from(request.bytes) }"
      : "{ key: request.key, bytes: Array.from(request.bytes) }"}
  }) + '\\n');
  const response = JSON.parse(line());
  const proof = response['lease-proof'];
  if (response.type !== 'provider-result' || response.import !== ${JSON.stringify(name)} ||
      response['audit-id'] !== ${JSON.stringify(ability['audit-id'])} ||
      typeof response['audit-receipt'] !== 'string' || response['audit-receipt'].length === 0 ||
      !proof || proof.epoch !== ${JSON.stringify(lease.epoch)} ||
      proof['expires-at'] !== ${JSON.stringify(lease['expires-at'])} ||
      proof['observed-at'] < ${JSON.stringify(lease['not-before'])} ||
      proof['observed-at'] > ${JSON.stringify(lease['expires-at'])})
    throw 'provider-failed';
  ${cas
    ? "if (!response.payload || typeof response.payload.won !== 'boolean' ||\n      (response.payload.etag !== null && typeof response.payload.etag !== 'string'))\n    throw 'provider-failed';\n  return { won: response.payload.won, etag: response.payload.etag };"
    : "if (response.payload !== null) throw 'provider-failed';"}
}
`;
}

function typedCoreProviderSource(name, ability, lease, binding) {
  const kind = name;
  return `
import { readSync, writeSync } from 'node:fs';
import { Grant } from './provider-capability.js';
let buffered = '';
let calls = 0;
function line() {
  for (;;) {
    const n = buffered.indexOf('\\n');
    if (n >= 0) { const out = buffered.slice(0, n); buffered = buffered.slice(n + 1); return out; }
    const b = Buffer.alloc(4096);
    const count = readSync(0, b, 0, b.length, null);
    if (count === 0) throw new Error('provider closed protocol before responding');
    buffered += b.subarray(0, count).toString('utf8');
  }
}
export function ${binding.exportName}(grant, request) {
  if (!(grant instanceof Grant) || grant.operation !== ${JSON.stringify(ability.operation)})
    throw 'provider-failed';
  calls += 1;
  if (calls > ${JSON.stringify(ability['max-items'])}) throw 'quota';
  const kind = ${JSON.stringify(kind)};
  let payload;
  if (kind === 'aiueos-http-post') {
    if (!request || typeof request.path !== 'string' || !Array.isArray(request.headers) ||
        !(request.body instanceof Uint8Array)) throw 'provider-failed';
    payload = { path: request.path, headers: request.headers, body: Array.from(request.body) };
  } else if (kind === 'aiueos-log-read') {
    if (!request || typeof request.cursor !== 'bigint' || !Number.isSafeInteger(request.maxBytes))
      throw 'provider-failed';
    payload = { cursor: Number(request.cursor), 'max-bytes': request.maxBytes };
  } else {
    if (!request || !(request.bytes instanceof Uint8Array)) throw 'provider-failed';
    payload = { bytes: Array.from(request.bytes) };
  }
  writeSync(1, JSON.stringify({
    type: 'provider-call', import: ${JSON.stringify(name)},
    ability: ${JSON.stringify(ability)}, payload
  }) + '\\n');
  const response = JSON.parse(line());
  const proof = response['lease-proof'];
  if (response.type !== 'provider-result' || response.import !== ${JSON.stringify(name)} ||
      response['audit-id'] !== ${JSON.stringify(ability['audit-id'])} ||
      typeof response['audit-receipt'] !== 'string' || response['audit-receipt'].length === 0 ||
      !proof || proof.epoch !== ${JSON.stringify(lease.epoch)} ||
      proof['expires-at'] !== ${JSON.stringify(lease['expires-at'])} ||
      proof['observed-at'] < ${JSON.stringify(lease['not-before'])} ||
      proof['observed-at'] > ${JSON.stringify(lease['expires-at'])}) throw 'provider-failed';
  if (kind === 'aiueos-identity-verify') {
    if (typeof response.payload !== 'boolean') throw 'provider-failed';
    return response.payload;
  }
  if (kind === 'aiueos-http-post') {
    const out = response.payload;
    if (!out || !Number.isSafeInteger(out.status) || !Array.isArray(out.headers) ||
        !Array.isArray(out.body)) throw 'provider-failed';
    return { status: out.status, headers: out.headers, body: Uint8Array.from(out.body) };
  }
  if (kind === 'aiueos-log-read') {
    const out = response.payload;
    if (!out || !Number.isSafeInteger(out['next-cursor']) || !Array.isArray(out.bytes))
      throw 'provider-failed';
    return { nextCursor: BigInt(out['next-cursor']), bytes: Uint8Array.from(out.bytes) };
  }
  const bytes = response.payload && response.payload.bytes;
  if (!Array.isArray(bytes) || bytes.length > ${JSON.stringify(ability['max-bytes'])})
    throw 'provider-failed';
  return { bytes: Uint8Array.from(bytes) };
}
`;
}

async function run(request) {
  if (request.type !== 'run') throw new Error('first protocol envelope must be a run request');
  if (!Number.isSafeInteger(request.fuel) || request.fuel <= 0 ||
      !Number.isSafeInteger(request['memory-pages']) || request['memory-pages'] <= 0) {
    throw new Error('resource bounds must be positive integers');
  }
  readFileSync(resolve(request.component)); // fail before tool invocation if absent
  const dir = mkdtempSync(join(tmpdir(), 'kototama-jco-'));
  try {
    writeFileSync(join(dir, 'package.json'), '{"type":"module"}\n');
    const mappings = [];
    const seen = new Set();
    const typed = request.lease !== undefined && request.lease !== null;
    for (const item of request.imports || []) {
      if (seen.has(item.name)) throw new Error('duplicate Component import');
      seen.add(item.name);
      const binding = validateAbility(item.name, item.ability);
      if (typed) {
        if (item.name !== 'aiueos-identity-sign' &&
            item.name !== 'aiueos-identity-verify' &&
            item.name !== 'aiueos-hash-sha256' &&
            item.name !== 'aiueos-http-post' &&
            item.name !== 'aiueos-log-read' &&
            item.name !== 'aiueos-clock-now' &&
            item.name !== 'aiueos-log-append' &&
            item.name !== 'aiueos-http-get-stream' &&
            item.name !== 'aiueos-object-get-stream' &&
            item.name !== 'aiueos-object-put-block' &&
            item.name !== 'aiueos-object-compare-and-set-ref')
          throw new Error(`typed jco host does not implement ${item.name}`);
        const capabilityProvider = 'provider-capability.js';
        const typedProvider =
          item.name === 'aiueos-clock-now'
            ? { file: 'provider-clock.js', specifier: 'aiueos:capability/clock',
                request: 'clock-now',
                source: typedClockSource(item.name, item.ability, request.lease) }
          : item.name === 'aiueos-log-append'
            ? { file: 'provider-log.js', specifier: 'aiueos:capability/log',
                request: 'log-append',
                source: typedLogSource(item.name, item.ability, request.lease) }
          : (item.name === 'aiueos-http-get-stream' ||
             item.name === 'aiueos-object-get-stream')
            ? { file: 'provider-stream.js', specifier: binding.specifier,
                request: item.name === 'aiueos-http-get-stream'
                  ? 'http-get-stream' : 'object-get-stream',
                source: typedStreamSource(item.name, item.ability, request.lease) }
          : (item.name === 'aiueos-object-put-block' ||
             item.name === 'aiueos-object-compare-and-set-ref')
            ? { file: 'provider-object-write.js', specifier: binding.specifier,
                request: item.name === 'aiueos-object-put-block'
                  ? 'object-put-block' : 'object-compare-and-set-ref',
                source: typedObjectWriteSource(item.name, item.ability, request.lease) }
            : { file: 'provider-core.js', specifier: binding.specifier,
                request: item.name.replace('aiueos-', '').replaceAll('-', '-'),
                source: typedCoreProviderSource(item.name, item.ability, request.lease, binding) };
        writeFileSync(join(dir, capabilityProvider),
                      typedCapabilitySource(item.ability, typedProvider.request));
        writeFileSync(join(dir, typedProvider.file), typedProvider.source);
        mappings.push(`aiueos:capability/capability=./${capabilityProvider}`);
        mappings.push(`${typedProvider.specifier}=./${typedProvider.file}`);
      } else {
        const provider = `provider-${item.name}.js`;
        writeFileSync(join(dir, provider),
                        providerSource(item.name, item.ability, binding,
                                       request['capability-mode'] === 'linear-resource'));
        mappings.push(`${binding.specifier}=./${provider}`);
      }
    }
    const jco = resolve(new URL('../node_modules/.bin/jco', import.meta.url).pathname);
    const args = ['transpile', resolve(request.component), '-o', dir, '--name', 'component',
                  '--no-typescript', '--quiet'];
    for (const mapping of mappings) args.push('-M', mapping);
    const built = spawnSync(jco, args, { encoding: 'utf8' });
    if (built.status !== 0) throw new Error(`jco transpile failed: ${(built.stderr || built.stdout).trim()}`);
    const component = await import(`${pathToFileURL(join(dir, 'component.js')).href}?run=${Date.now()}`);
    const value = component.main();
    if (typeof value !== 'bigint') throw new Error('Component main must return s64');
    return Number(value);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

try {
  const request = JSON.parse(readLine());
  send({ type: 'result', value: await run(request) });
} catch (error) {
  send({ type: 'error', message: error instanceof Error ? error.message : String(error) });
}
