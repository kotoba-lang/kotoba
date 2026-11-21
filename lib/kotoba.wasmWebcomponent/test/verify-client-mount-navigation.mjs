// Synthetic DOM and MessageChannel test; a real-browser fixture is also provided.
// KOTOBA-159 R4: the mount accepts only a canonical broker, so every case runs the real broker and the
// real consent host; "pending work" is a consent dialog awaiting the user.
import assert from 'node:assert/strict';
import { DISCLOSURE } from './client-runtime-fixtures.mjs';

class Frame extends EventTarget {
  constructor() { super(); this.tagName = 'iframe'; this.contentWindow = { postMessage: (_data, _origin, ports) => { this.port = ports[0]; } }; }
  remove() { this.removed = true; }
}
class Element {
  constructor(tag) { this.tagName = tag; this.listeners = new Map(); this.isConnected = true; this.open = false; this.textContent = ''; }
  append() {} setAttribute() {} focus() {} remove() { this.isConnected = false; }
  addEventListener(type, fn) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn]); }
  dispatch(type, event) { event.currentTarget = this; for (const fn of this.listeners.get(type) ?? []) fn(event); }
  showModal() { this.open = true; } close() { this.open = false; }
}
class Mouse { constructor(type) { this.type = type; this.isTrusted = true; } }
class Container {
  constructor() { this.isConnected = true; this.ownerDocument = globalThis.document; }
  getRootNode() { return globalThis.document; }
  append(frame) { this.frame = frame; frame.isConnected = true; frame.parentNode = this; queueMicrotask(() => frame.dispatchEvent(new Event('load'))); }
}
let observer; let now = 0;
const made = [];
globalThis.MutationObserver = class {
  constructor(callback) { this.callback = callback; observer = this; }
  observe() {}
  disconnect() { this.disconnected = true; }
};
globalThis.HTMLElement = Container;
globalThis.document = {
  body: new Element('body'), defaultView: { MouseEvent: Mouse, performance: { now: () => now } },
  createElement(tag) { const el = tag === 'iframe' ? new Frame() : new Element(tag); made.push(el); return el; },
};
const { verifyClientArtifact, mountRestrictedClientApp, createClientConsentHost, createClientOperationBroker } = await import('../src/kotoba-client-runtime.js');
const bytes = new TextEncoder().encode('<p>synthetic guest</p>');
const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), (byte) => byte.toString(16).padStart(2, '0')).join('');
const artifact = await verifyClientArtifact(bytes, { revision: '1'.repeat(40), sha256: digest, 'max-bytes': 1024 });
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

const op = { capability: 'test/read', service: 'svc', operation: 'read', consent: 'each-operation', disclosure: DISCLOSURE,
  'data-categories': ['x'], endpoint: { origin: 'https://svc.example', method: 'GET', path: '/x' } };
const selector = { capability: op.capability, service: op.service, operation: op.operation };
const runtime = { schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile: 'restricted-wasm-v1', entry: 'index.html',
  'local-state': { adapter: 'memory', schema: 's', version: 1 }, operations: [op] };
function canonicalBroker(fetchStub = async () => { throw new Error('unused'); }) {
  const before = made.length;
  const consentHost = createClientConsentHost();
  const dialog = made.slice(before).find((el) => el.tagName === 'dialog');
  const [, allow] = made.slice(before).filter((el) => el.tagName === 'button');
  const saved = globalThis.fetch; globalThis.fetch = fetchStub;
  const broker = createClientOperationBroker({ runtime, requestedCapabilities: [op.capability], approvedOperations: [op],
    hostSupportedOperations: [[op.capability, op.service, op.operation]], consentHost });
  globalThis.fetch = saved;
  const approve = () => { now += 600; allow.dispatch('pointerdown', new Mouse('pointerdown')); allow.dispatch('click', new Mouse('click')); };
  return { broker, dialog, approve, consentHost };
}
const request = (id) => ({ protocol: 'kotoba.client.operation.v1', id, selector, payload: { input: 'https://svc.example/x' } });

// R4 negative control: an object with invoke is not a broker.
{
  const container = new Container();
  await assert.rejects(() => mountRestrictedClientApp({ artifact, container, broker: { invoke: async () => ({}) } }), /trusted host broker required/);
  await assert.rejects(() => mountRestrictedClientApp({ artifact, container, broker: Object.freeze({ ...canonicalBroker().broker }) }), /trusted host broker required/, 'a copy of a canonical broker is not canonical');
}

// A second load invalidates the session: the pending consent is cancelled.
{
  const { broker, dialog } = canonicalBroker();
  const container = new Container();
  const mount = await mountRestrictedClientApp({ artifact, container, broker });
  await tick();
  assert.ok(container.frame.port, 'initial load must deliver the channel');
  container.frame.port.postMessage(request('one'));
  await tick(); await tick();
  assert.equal(dialog.open, true, 'consent is pending');
  container.frame.dispatchEvent(new Event('load'));
  await tick();
  assert.equal(dialog.open, false, 'second load must abort pending consent');
  assert.equal(container.frame.removed, true, 'second load removes the old session');
  mount.close();
  container.frame.port.close();
  assert.equal(observer.disconnected, true);
}

// Detaching the frame aborts pending consent.
{
  const { broker, dialog } = canonicalBroker();
  const container = new Container();
  const mount = await mountRestrictedClientApp({ artifact, container, broker });
  await tick();
  container.frame.port.postMessage(request('two'));
  await tick(); await tick();
  assert.equal(dialog.open, true);
  container.frame.isConnected = false;
  observer.callback([{ removedNodes: [container.frame] }]);
  await tick();
  assert.equal(dialog.open, false, 'detaching must abort pending consent');
  assert.equal(observer.disconnected, true);
  mount.close();
  container.frame.port.close();
}
{
  const { broker } = canonicalBroker();
  const disconnected = new Container(); disconnected.isConnected = false;
  await assert.rejects(() => mountRestrictedClientApp({ artifact, container: disconnected, broker }), /connected host container/);
}

// A response can already have arrived while its body remains open. Closing the
// guest must cancel that pending body read as well as suppressing its reply.
{
  let pulled, cancelled, responseController;
  const reading = new Promise((resolve) => { pulled = resolve; });
  const cancellation = new Promise((resolve) => { cancelled = resolve; });
  const responseStream = new ReadableStream({
    start(controller) { responseController = controller; },
    pull() { pulled(); return new Promise(() => {}); },
    cancel() { cancelled(); },
  }, { highWaterMark: 0 });
  const { broker, approve } = canonicalBroker(async () => {
    const response = new Response(responseStream);
    Object.defineProperty(response, 'url', { value: 'https://svc.example/x' });
    return response;
  });
  const container = new Container();
  const mount = await mountRestrictedClientApp({ artifact, container, broker });
  await tick();
  container.frame.port.postMessage(request('three'));
  await tick(); await tick();
  approve();
  await Promise.race([reading, new Promise((_, reject) => setTimeout(() => reject(new Error('body not read')), 1000))]);
  mount.close();
  try {
    await Promise.race([cancellation, new Promise((_, reject) => setTimeout(() => reject(new Error('closed session did not cancel response body')), 500))]);
  } finally {
    try { responseController.close(); } catch {};
    container.frame.port.close();
  }
}
console.log('verify-client-mount-navigation: ok');
