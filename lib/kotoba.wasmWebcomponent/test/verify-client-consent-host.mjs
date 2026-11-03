// Consent host regression tests (KOTOBA-158): a late `close` event from a previous approval must not
// deny the next pending operation, while a genuine external close still denies it. KOTOBA-159
// finding 3: Allow counts only for a fresh trusted press that starts at least 600 ms after the
// dialog opens.
// Uses a minimal fake DOM so the real createClientConsentHost / createClientOperationBroker run in Node.
import assert from 'node:assert/strict';

class FakeMouseEvent { constructor(type, trusted) { this.type = type; this.isTrusted = trusted; } }
class FakeKeyEvent { constructor(type, key, trusted) { this.type = type; this.key = key; this.isTrusted = trusted; } }
let now = 0;                                // the fake clock, in ms; advance() moves it
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
const doc = { body: new FakeElement('body'), defaultView: { MouseEvent: FakeMouseEvent, performance: { now: () => now } }, createElement(tag) { const el = new FakeElement(tag); created.push(el); return el; } };
globalThis.document = doc;
let fetchCalls = 0;
globalThis.fetch = async () => { fetchCalls++; return { status: 200, ok: true, url: 'https://svc.example/x', type: 'basic' }; };

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
  // A real approval: the dialog has been showing for the arm delay, then a fresh press and click.
  const trustedAllow = () => {
    now += 600;
    allow.dispatch('pointerdown', new FakeMouseEvent('pointerdown', true));
    allow.dispatch('click', new FakeMouseEvent('click', true));
  };
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

// 4. KOTOBA-159 finding 3: an early, stale or synthetic press does not approve.
{
  const { dialog, allow, broker, trustedAllow } = setup();
  const pending = call(broker);
  await tick();
  assert.equal(allow.disabled, true, 'Allow starts disabled');
  const press = (trusted = true) => allow.dispatch('pointerdown', new FakeMouseEvent('pointerdown', trusted));
  const click = () => allow.dispatch('click', new FakeMouseEvent('click', true));
  press(); click();                         // same tick as the dialog opened (double-click lure)
  assert.equal(await settled(pending), 'pending', 'a click before the arm delay does not approve');
  now += 599; press(); click();
  assert.equal(await settled(pending), 'pending', '599 ms is still too early');
  press(); now += 1; click();               // press began early, release after the delay
  assert.equal(await settled(pending), 'pending', 'a press that started before the delay does not approve');
  click();                                  // a click with no press of its own
  assert.equal(await settled(pending), 'pending', 'a click without a fresh press does not approve');
  press(false); click();                    // synthetic press
  assert.equal(await settled(pending), 'pending', 'an untrusted press does not approve');
  allow.dispatch('keydown', new FakeKeyEvent('keydown', 'Tab', true)); click();
  assert.equal(await settled(pending), 'pending', 'a non-activation key does not approve');
  allow.dispatch('keydown', new FakeKeyEvent('keydown', 'Enter', true)); click();
  assert.equal((await pending).status, 200, 'a fresh trusted Enter after the delay approves');
  dialog.deliverCloseEvents();

  // The delay restarts for every request: approval #1's armed state does not carry over.
  const next = call(broker);
  await tick();
  press(); click();
  assert.equal(await settled(next), 'pending', 'the next request is not armed yet');
  trustedAllow();
  assert.equal((await next).status, 200);
}

// 5. Closing a host-owned session cancels its pending consent and sends no request.
{
  const { dialog, broker, trustedAllow } = setup();
  const controller = new AbortController();
  const before = fetchCalls;
  const pending = broker.invoke(selector, { input: 'https://svc.example/x' }, { signal: controller.signal });
  await tick();
  assert.equal(dialog.open, true);
  controller.abort();
  assert.equal(dialog.open, false, 'abort closes the pending dialog');
  await assert.rejects(pending, /cancelled/);
  assert.equal(fetchCalls, before, 'abort before approval sends nothing');
  const next = call(broker);
  await tick();
  dialog.deliverCloseEvents();
  assert.equal(await settled(next), 'pending', 'cancelled request cannot deny a subsequent request');
  trustedAllow();
  assert.equal((await next).status, 200);
  const already = new AbortController(); already.abort();
  await assert.rejects(broker.invoke(selector, { input: 'https://svc.example/x' }, { signal: already.signal }), /cancelled/);
  assert.equal(fetchCalls, before + 1, 'pre-aborted request sends nothing');
}

// Cancellation after the click but before the async continuation still refuses dispatch.
{
  const { dialog, broker, trustedAllow } = setup();
  const controller = new AbortController();
  const unrelated = new AbortController();
  const before = fetchCalls;
  const pending = broker.invoke(selector, { input: 'https://svc.example/x' }, { signal: controller.signal });
  await tick();
  unrelated.abort();
  assert.equal(dialog.open, true, 'an unrelated cancellation leaves consent pending');
  trustedAllow(); controller.abort();
  await assert.rejects(pending, /cancelled/);
  assert.equal(fetchCalls, before, 'no fetch after cancellation at the approval boundary');
}

// 6. A host cancellation also reaches an HTTP fetch already started after approval.
{
  const originalFetch = globalThis.fetch;
  let receivedSignal;
  globalThis.fetch = (_request, options) => new Promise((resolve, reject) => {
    receivedSignal = options?.signal;
    receivedSignal.addEventListener('abort', () => reject(new Error('synthetic fetch aborted')), { once: true });
  });
  try {
    const { broker, trustedAllow } = setup();
    const controller = new AbortController();
    const pending = broker.invoke(selector, { input: 'https://svc.example/x' }, { signal: controller.signal });
    await tick(); trustedAllow(); await tick();
    assert.equal(receivedSignal, controller.signal);
    controller.abort();
    await assert.rejects(pending, /synthetic fetch aborted/);
  } finally { globalThis.fetch = originalFetch; }
}

// 7. Closing while a request body is being snapshotted cancels without a prompt or fetch.
{
  created.length = 0;
  const consentHost = createClientConsentHost({ document: doc });
  const dialog = created.find((element) => element.tagName === 'dialog');
  const post = { ...operation, capability: 'test/post', endpoint: { origin: 'https://svc.example', method: 'POST', path: '/x' } };
  const broker = createClientOperationBroker({ runtime: { ...runtime, operations: [post] }, requestedCapabilities: [post.capability], approvedOperations: [post], hostSupportedOperations: [[post.capability, post.service, post.operation]], consentHost });
  const stream = new ReadableStream({ pull() { return new Promise(() => {}); } });
  const request = new Request('https://svc.example/x', { method: 'POST', body: stream, duplex: 'half' });
  const controller = new AbortController();
  const before = fetchCalls;
  const pending = broker.invoke({ capability: post.capability, service: post.service, operation: post.operation }, { input: request }, { signal: controller.signal });
  await tick(); controller.abort();
  let timer;
  try {
    await Promise.race([assert.rejects(pending, /cancelled/), new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('snapshot did not cancel')), 500); })]);
  } finally { clearTimeout(timer); consentHost.destroy(); }
  assert.equal(dialog.open, false);
  assert.equal(fetchCalls, before);
}

console.log('verify-client-consent-host: ok');
