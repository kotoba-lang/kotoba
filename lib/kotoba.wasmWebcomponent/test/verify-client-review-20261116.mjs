// KOTOBA-159 second independent review (2026-11-16), findings R1 and R2. Each case fails on the
// runtime at kotoba-lang/kotoba 2a40111e (sha256 5a950051...) and passes after the fix.
//   R1  fetch(request, {signal}) re-creates the Request, and a non-empty init resets its referrer
//       and referrerPolicy (Fetch, Request constructor, step "If init is not empty"). The broker's
//       explicit `referrerPolicy: 'no-referrer'` was lost on every approved HTTP call, so the
//       service received a Referer naming the host page. Chromium 156 shows the same behaviour.
//   R2  a response that is refused after the fetch (undeclared final origin, unverifiable
//       redirect, failed artifact download) was left unread, so its connection and buffered data
//       stayed open until garbage collection.
// Fake DOM and stubbed fetch; no network and no TLS certificate.
import assert from 'node:assert/strict';

class Mouse {
  constructor(type) { this.type = type; this.isTrusted = true; }
}
class Element {
  constructor(tag) { this.tagName = tag; this.listeners = new Map(); this.isConnected = true; this.open = false; this.textContent = ''; }
  append() {}
  setAttribute() {}
  focus() {}
  remove() { this.isConnected = false; }
  addEventListener(type, fn) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn]); }
  showModal() { this.open = true; }
  close() { this.open = false; }
  dispatch(type, event) { event.currentTarget = this; for (const fn of this.listeners.get(type) ?? []) fn(event); }
}
let now = 0;
const made = [];
globalThis.document = {
  body: new Element('body'),
  defaultView: { MouseEvent: Mouse, performance: { now: () => now } },
  createElement(tag) { const el = new Element(tag); made.push(el); return el; },
};
const { createClientConsentHost, createClientOperationBroker } = await import('../src/kotoba-client-runtime.js');
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

const ORIGIN = 'https://svc.example';
const get = {
  capability: 'net/http-get', service: 'svc', operation: 'read', consent: 'each-operation', 'data-categories': ['x'],
  endpoint: { origin: ORIGIN, method: 'GET', path: '/items' },
};
const artifact = {
  capability: 'net/http-get', service: 'svc', operation: 'download', consent: 'each-operation', 'data-categories': ['x'],
  endpoint: { origin: ORIGIN, method: 'GET', path: '/blob' },
  artifact: { revision: '0'.repeat(40), sha256: '0'.repeat(64), 'max-bytes': 1024 },
};
const descriptor = (operations) => ({
  schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile: 'restricted-wasm-v1', entry: 'index.html',
  'local-state': { adapter: 'memory', schema: 's', version: 1 }, operations,
});

// One consent host and broker per case; the real host approves with a trusted, armed press.
async function harness(operation, fetchStub) {
  const realFetch = globalThis.fetch;
  globalThis.fetch = fetchStub;
  const before = made.length;
  const host = createClientConsentHost();
  const [, allow] = made.slice(before).filter((element) => element.tagName === 'button');
  const broker = createClientOperationBroker({
    runtime: descriptor([operation]), requestedCapabilities: [operation.capability], approvedOperations: [operation],
    hostSupportedOperations: [[operation.capability, operation.service, operation.operation]], consentHost: host,
  });
  globalThis.fetch = realFetch; // the broker captured the stub at creation
  const selector = { capability: operation.capability, service: operation.service, operation: operation.operation };
  return {
    host,
    async invoke(path, signal) {
      const call = broker.invoke(selector, { input: `${ORIGIN}${path}`, init: { method: 'GET' } }, signal ? { signal } : undefined);
      await tick(); now += 600;
      allow.dispatch('pointerdown', new Mouse('pointerdown'));
      allow.dispatch('click', new Mouse('click'));
      return call;
    },
  };
}

const response = (fields) => ({ ok: true, status: 200, type: 'cors', url: `${ORIGIN}/items`, body: null, ...fields });
function spyStream() {
  const spy = { cancelled: false };
  spy.body = new ReadableStream({ start(controller) { controller.enqueue(new Uint8Array(4)); }, cancel() { spy.cancelled = true; } });
  return spy;
}

// R1: the request that reaches fetch still has the snapshot's referrer policy, with or without a signal.
for (const withSignal of [false, true]) {
  const calls = [];
  const { host, invoke } = await harness(get, (...args) => { calls.push(args); return Promise.resolve(response()); });
  const controller = new AbortController();
  await invoke('/items', withSignal ? controller.signal : undefined);
  assert.equal(calls.length, 1);
  const [input, init] = calls[0];
  // What fetch does with its arguments: a non-empty init builds a new Request from the first one.
  const sent = init && Object.keys(init).length > 0 ? new Request(input, init) : input;
  assert.equal(sent.referrerPolicy, 'no-referrer', `referrer policy survives (signal: ${withSignal})`);
  assert.equal(sent.credentials, 'omit');
  assert.equal(sent.cache, 'no-store');
  assert.equal(sent.redirect, 'error');
  assert.equal(sent.method, 'GET');
  if (withSignal) {
    assert.equal(sent.signal.aborted, false);
    controller.abort();
    assert.equal(sent.signal.aborted, true, 'aborting the operation signal aborts the request that is sent');
  }
  host.destroy();
}

// R2: a refused response is discarded, not left open.
{
  const cases = [
    ['undeclared final origin', get, { url: 'https://elsewhere.example/items' }, /redirect origin is not declared/],
    ['unverifiable redirect', get, { status: 302, type: 'basic' }, /redirect could not be verified/],
    ['failed artifact download', artifact, { ok: false, status: 404, url: `${ORIGIN}/blob` }, /artifact download failed/],
  ];
  for (const [name, operation, fields, message] of cases) {
    const spy = spyStream();
    const { host, invoke } = await harness(operation, () => Promise.resolve(response({ ...fields, body: spy.body })));
    await assert.rejects(invoke(operation.endpoint.path), message, name);
    await tick();
    assert.equal(spy.cancelled, true, `${name}: body is cancelled`);
    host.destroy();
  }
  // Negative control: an accepted response is returned untouched and still readable.
  const spy = spyStream();
  const { host, invoke } = await harness(get, () => Promise.resolve(response({ body: spy.body })));
  const accepted = await invoke('/items');
  await tick();
  assert.equal(spy.cancelled, false, 'accepted response is not cancelled');
  assert.equal(accepted.body, spy.body);
  host.destroy();
}

console.log('PASS: R1 referrer policy and abort survive to fetch; R2 refused responses are cancelled; accepted response untouched');
