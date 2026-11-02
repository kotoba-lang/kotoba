// Synthetic DOM and MessageChannel test; a real-browser fixture is also provided.
import assert from 'node:assert/strict';

class Frame extends EventTarget {
  constructor() { super(); this.contentWindow = { postMessage: (_data, _origin, ports) => { this.port = ports[0]; } }; }
  remove() { this.removed = true; }
}
class Container {
  append(frame) { this.frame = frame; queueMicrotask(() => frame.dispatchEvent(new Event('load'))); }
}
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
console.log('verify-client-mount-navigation: ok');
