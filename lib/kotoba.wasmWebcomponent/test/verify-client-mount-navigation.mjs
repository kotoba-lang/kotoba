// Synthetic DOM and MessageChannel test; a real-browser fixture is also provided.
import assert from 'node:assert/strict';

class Frame extends EventTarget {
  constructor() { super(); this.contentWindow = { postMessage: (_data, _origin, ports) => { this.port = ports[0]; } }; }
  remove() { this.removed = true; }
}
class Container {
  constructor() { this.isConnected = true; this.ownerDocument = globalThis.document; }
  getRootNode() { return globalThis.document; }
  append(frame) { this.frame = frame; frame.isConnected = true; frame.parentNode = this; queueMicrotask(() => frame.dispatchEvent(new Event('load'))); }
}
let observer;
globalThis.MutationObserver = class {
  constructor(callback) { this.callback = callback; observer = this; }
  observe() {}
  disconnect() { this.disconnected = true; }
};
globalThis.HTMLElement = Container;
globalThis.document = { createElement(tag) { assert.equal(tag, 'iframe'); return new Frame(); } };
const { verifyClientArtifact, mountRestrictedClientApp } = await import('../src/kotoba-client-runtime.js');
const bytes = new TextEncoder().encode('<p>synthetic guest</p>');
const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), (byte) => byte.toString(16).padStart(2, '0')).join('');
const artifact = await verifyClientArtifact(bytes, { revision: '1'.repeat(40), sha256: digest, 'max-bytes': 1024 });
const container = new Container();
let invokedResolve;
const invoked = new Promise((resolve) => { invokedResolve = resolve; });
let activeSignal;
const broker = { invoke(_selector, _payload, { signal }) {
  activeSignal = signal;
  invokedResolve();
  return new Promise((_, reject) => signal.addEventListener('abort', () => reject(new Error('cancelled')), { once: true }));
} };
const mount = await mountRestrictedClientApp({ artifact, container, broker });
await new Promise((resolve) => setTimeout(resolve, 0));
assert.ok(container.frame.port, 'initial load must deliver the channel');
container.frame.port.postMessage({ protocol: 'kotoba.client.operation.v1', id: 'one', selector: {}, payload: {} });
await Promise.race([invoked, new Promise((_, reject) => setTimeout(() => reject(new Error('broker not invoked')), 1000))]);
assert.equal(activeSignal.aborted, false);
container.frame.dispatchEvent(new Event('load'));
assert.equal(activeSignal.aborted, true, 'second load must abort pending work');
assert.equal(container.frame.removed, true, 'second load removes the old session');
mount.close();
container.frame.port.close();
assert.equal(observer.disconnected, true);
const detachedContainer = new Container();
const detachedMount = await mountRestrictedClientApp({ artifact, container: detachedContainer, broker });
await new Promise((resolve) => setTimeout(resolve, 0));
detachedContainer.frame.port.postMessage({ protocol: 'kotoba.client.operation.v1', id: 'two', selector: {}, payload: {} });
await new Promise((resolve) => setTimeout(resolve, 10));
assert.equal(activeSignal.aborted, false);
detachedContainer.frame.isConnected = false;
observer.callback([{ removedNodes: [detachedContainer.frame] }]);
assert.equal(activeSignal.aborted, true, 'detaching must abort pending work');
assert.equal(observer.disconnected, true);
detachedMount.close();
detachedContainer.frame.port.close();
const disconnected = new Container(); disconnected.isConnected = false;
await assert.rejects(() => mountRestrictedClientApp({ artifact, container: disconnected, broker }), /connected host container/);
// A response can already have arrived while its body remains open. Closing the
// guest must cancel that pending body read as well as suppressing its reply.
let pulled, cancelled, responseController;
const reading = new Promise((resolve) => { pulled = resolve; });
const cancellation = new Promise((resolve) => { cancelled = resolve; });
const responseStream = new ReadableStream({
  start(controller) { responseController = controller; },
  pull() { pulled(); return new Promise(() => {}); },
  cancel() { cancelled(); },
}, { highWaterMark: 0 });
const responseContainer = new Container();
const responseMount = await mountRestrictedClientApp({ artifact, container: responseContainer,
  broker: { invoke: async () => new Response(responseStream) } });
await new Promise((resolve) => setTimeout(resolve, 0));
responseContainer.frame.port.postMessage({ protocol: 'kotoba.client.operation.v1', id: 'three', selector: {}, payload: {} });
await Promise.race([reading, new Promise((_, reject) => setTimeout(() => reject(new Error('body not read')), 1000))]);
responseMount.close();
try {
  await Promise.race([cancellation, new Promise((_, reject) => setTimeout(() => reject(new Error('closed session did not cancel response body')), 500))]);
} finally {
  try { responseController.close(); } catch {};
  responseContainer.frame.port.close();
}
console.log('verify-client-mount-navigation: ok');
