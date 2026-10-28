// Consent host regression tests (KOTOBA-158): a late `close` event from a previous approval must not
// deny the next pending operation, while a genuine external close still denies it.
// Uses a minimal fake DOM so the real createClientConsentHost / createClientOperationBroker run in Node.
import assert from 'node:assert/strict';

class FakeMouseEvent { constructor(type, trusted) { this.type = type; this.isTrusted = trusted; } }
class FakeElement {
  constructor(tag) { this.tagName = tag; this.listeners = new Map(); this.isConnected = true; this.open = false; this.lateCloses = 0; this.textContent = ''; }
  append() {}
  setAttribute() {}
  focus() {}
  remove() { this.isConnected = false; }
  addEventListener(type, fn) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn]); }
  dispatch(type, event) { event.currentTarget = this; for (const fn of this.listeners.get(type) ?? []) fn(event); }
  showModal() { if (this.open) throw new Error('already open'); this.open = true; }
  // Like a browser: close() flips `open` now but queues the `close` event for later delivery.
  close() { if (!this.open) return; this.open = false; this.lateCloses += 1; }
  deliverCloseEvents() { while (this.lateCloses > 0) { this.lateCloses -= 1; this.dispatch('close', { type: 'close' }); } }
}
const created = [];
const doc = { body: new FakeElement('body'), defaultView: { MouseEvent: FakeMouseEvent }, createElement(tag) { const el = new FakeElement(tag); created.push(el); return el; } };
globalThis.document = doc;
globalThis.fetch = async () => ({ status: 200, ok: true, url: 'https://svc.example/x', type: 'basic' });

const { createClientConsentHost, createClientOperationBroker } = await import('../src/kotoba-client-runtime.js');

const operation = {
  capability: 'net/http-get', service: 'svc', operation: 'op', consent: 'each-operation', 'data-categories': ['x'],
  endpoint: { origin: 'https://svc.example', method: 'GET', path: '/x' },
};
const runtime = { schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile: 'trusted-page-v1', entry: 'index.html', 'local-state': { adapter: 'indexeddb', schema: 's', version: 1 }, operations: [operation] };
const selector = { capability: operation.capability, service: operation.service, operation: operation.operation };
const call = (broker) => broker.invoke(selector, { input: 'https://svc.example/x', init: { method: 'GET' } });

function setup() {
  created.length = 0;
  const consentHost = createClientConsentHost({ document: doc });
  const dialog = created.find((el) => el.tagName === 'dialog');
  const [deny, allow] = created.filter((el) => el.tagName === 'button');
  const broker = createClientOperationBroker({ runtime, requestedCapabilities: ['net/http-get'], approvedOperations: [operation], hostSupportedOperations: [['net/http-get', 'svc', 'op']], consentHost });
  const trustedAllow = () => allow.dispatch('click', new FakeMouseEvent('click', true));
  return { dialog, deny, allow, broker, trustedAllow };
}
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const settled = async (promise) => { let state = 'pending'; promise.then(() => { state = 'resolved'; }, () => { state = 'rejected'; }); await tick(); await tick(); return state; };

// 1. Regression: late close of approval #1 must not deny the pending operation #2.
{
  const { dialog, broker, trustedAllow } = setup();
  const first = call(broker);
  await tick();
  assert.equal(dialog.open, true);
  trustedAllow();
  assert.equal((await first).status, 200);
  const second = call(broker);            // opens the dialog again before close #1 is delivered
  await tick();
  assert.equal(dialog.open, true, 'second consent is showing');
  dialog.deliverCloseEvents();            // the stale close event from approval #1 arrives now
  assert.equal(await settled(second), 'pending', 'late close must not decide the pending operation');
  assert.equal(dialog.open, true);
  trustedAllow();
  assert.equal((await second).status, 200, 'the user can still approve the second operation');
}

// 2. A genuine external close of the pending dialog still denies it.
{
  const { dialog, broker } = setup();
  const pending = call(broker);
  await tick();
  dialog.close();                         // not issued by finish(): e.g. page script or UA
  dialog.deliverCloseEvents();
  await assert.rejects(pending, /not approved/);
}

// 3. Deny, untrusted clicks and cancel keep their semantics.
{
  const { dialog, deny, allow, broker } = setup();
  const denied = call(broker);
  await tick();
  allow.dispatch('click', new FakeMouseEvent('click', false)); // synthetic click: no approval
  assert.equal(await settled(denied), 'pending');
  deny.dispatch('click', new FakeMouseEvent('click', true));
  await assert.rejects(denied, /not approved/);
  dialog.deliverCloseEvents();

  const cancelled = call(broker);
  await tick();
  let prevented = false;
  dialog.dispatch('cancel', { type: 'cancel', preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
  await assert.rejects(cancelled, /not approved/);
}

console.log('verify-client-consent-host: ok');
