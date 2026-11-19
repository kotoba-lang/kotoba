// AWAI-3336: a hand-off to an app the user picks in the OS (share sheet) is declared without a service origin.
// Validation, connect-src, consent display, deny and approve paths run against the real runtime with a minimal fake DOM.
import assert from 'node:assert/strict';

class FakeMouseEvent { constructor(type, trusted) { this.type = type; this.isTrusted = trusted; } }
let now = 0;
class FakeElement {
  constructor(tag) { this.tagName = tag; this.listeners = new Map(); this.isConnected = true; this.open = false; this.textContent = ''; }
  append() {} setAttribute() {} focus() {}
  remove() { this.isConnected = false; }
  addEventListener(type, fn) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn]); }
  dispatch(type, event) { event.currentTarget = this; for (const fn of this.listeners.get(type) ?? []) fn(event); }
  showModal() { this.open = true; }
  close() { this.open = false; }
}
const created = [];
const doc = { body: new FakeElement('body'), defaultView: { MouseEvent: FakeMouseEvent, performance: { now: () => now } }, createElement(tag) { const el = new FakeElement(tag); created.push(el); return el; } };
globalThis.document = doc;
let fetchCalls = 0;
globalThis.fetch = async () => { fetchCalls++; throw new Error('no fetch expected'); };

const { clientRuntimeProblems, clientRuntimeConnectSrc, prepareClientOperationRequest, clientEndpointAllowsRequest,
  createClientConsentHost, createClientOperationBroker } = await import('../src/kotoba-client-runtime.js');

const share = {
  capability: 'app.share', service: 'user-chosen-lawyer', operation: 'send-memo', consent: 'each-operation',
  'data-categories': ['legal.consultation', 'person.contact'],
  endpoint: { 'browser-action': 'share/text', recipient: 'user-selected-app' },
};
const runtime = (operations) => ({ schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile: 'trusted-page-v1', entry: 'index.html',
  'local-state': { adapter: 'memory', schema: 's', version: 1 }, operations });
const selector = { capability: share.capability, service: share.service, operation: share.operation };
const push = {
  capability: 'notifications/push', service: 'browser-push-service',
  operation: 'create-push-subscription', consent: 'each-operation',
  'data-categories': ['push-subscription-endpoint'],
  endpoint: { 'browser-action': 'create-push-subscription', recipient: 'browser-selected-push-provider' },
};

// Declaration shape.
{
  assert.deepEqual(clientRuntimeProblems(runtime([share]), ['app.share'], 'https://app.example'), []);
  assert.equal(clientRuntimeConnectSrc(runtime([share]), ['app.share'], [], 'https://app.example'), "connect-src 'none'", 'never enters connect-src');
  const bad = [
    { 'browser-action': 'share/text', recipient: 'lawyer@example.jp' },            // the app may not name the receiver
    { 'browser-action': 'share/text', recipient: 'user-selected-app', origin: 'https://svc.example' },
    { 'browser-action': 'share/text' },                                            // no origin and no recipient
    { 'browser-action': '', recipient: 'user-selected-app' },
    { recipient: 'user-selected-app', method: 'POST', path: '/x' },
    'user-selected-app',
  ];
  for (const endpoint of bad) {
    assert.ok(clientRuntimeProblems(runtime([{ ...share, endpoint }]), ['app.share'], 'https://app.example').length > 0, JSON.stringify(endpoint));
  }
  for (const extra of [{ artifact: { revision: 'a'.repeat(40), sha256: 'b'.repeat(64), 'max-bytes': 1 } }, { 'redirect-origins': ['https://x.example'] }]) {
    assert.ok(clientRuntimeProblems(runtime([{ ...share, ...extra }]), ['app.share'], 'https://app.example').length > 0, 'no HTTP options');
  }
  assert.ok(clientRuntimeProblems(runtime([{ ...share, consent: 'once' }]), ['app.share'], 'https://app.example').length > 0, 'each-operation only');
  await assert.rejects(prepareClientOperationRequest(share, { input: 'https://svc.example/x' }), /HTTP endpoint/);
  assert.equal(clientEndpointAllowsRequest(share.endpoint, 'https://svc.example/x', 'GET'), false);
  assert.deepEqual(clientRuntimeProblems(runtime([push]), ['notifications/push']), []);
  assert.equal(clientRuntimeConnectSrc(runtime([push]), ['notifications/push']), "connect-src 'none'");
  assert.ok(clientRuntimeProblems(runtime([{ ...push, endpoint: { ...push.endpoint, 'browser-action': 'share/text' } }]),
    ['notifications/push']).length > 0);
}

function setup({ declared = [share], approved = [share], supported = [['app.share', share.service, share.operation]], adapters } = {}) {
  created.length = 0;
  const consentHost = createClientConsentHost({ document: doc });
  const dialog = created.find((el) => el.tagName === 'dialog');
  const scope = created.find((el) => el.tagName === 'pre');
  const [deny, allow] = created.filter((el) => el.tagName === 'button');
  const handed = [];
  const browserAdapters = adapters ?? { [share.service]: { [share.operation]: ({ payload }) => { handed.push(payload); return { opened: true }; } } };
  const broker = createClientOperationBroker({ runtime: runtime(declared), requestedCapabilities: declared.length ? ['app.share'] : [],
    approvedOperations: approved, hostSupportedOperations: supported, browserAdapters, consentHost });
  const trustedAllow = () => { now += 600; allow.dispatch('pointerdown', new FakeMouseEvent('pointerdown', true)); allow.dispatch('click', new FakeMouseEvent('click', true)); };
  return { dialog, scope, deny, allow, broker, handed, trustedAllow };
}
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const memo = { title: 'Consultation memo', text: 'I lent money.' };

// Negative control: an undeclared operation is refused before any dialog or hand-off.
{
  const { dialog, broker, handed } = setup({ declared: [], approved: [], supported: [] });
  await assert.rejects(broker.invoke(selector, memo), /not eligible/);
  assert.equal(dialog.open, false); assert.equal(handed.length, 0);
}
// Negative control: declared but no host adapter fails before consent.
{
  const { dialog, broker } = setup({ adapters: {} });
  await assert.rejects(broker.invoke(selector, memo), /not host-supported/);
  assert.equal(dialog.open, false);
}
// Consent shows the user-chosen receiver and the data categories; denying hands nothing over.
{
  const { dialog, scope, deny, broker, handed } = setup();
  const pending = broker.invoke(selector, memo);
  await tick();
  assert.equal(dialog.open, true);
  assert.match(scope.textContent, /Endpoint: an app you choose on this device \(not chosen by this app\)/);
  assert.match(scope.textContent, /Receiver: the app you pick next/);
  assert.match(scope.textContent, /Action: share\/text/);
  assert.match(scope.textContent, /Data categories: legal\.consultation, person\.contact/);
  assert.doesNotMatch(scope.textContent, /undefined/);
  deny.dispatch('click', new FakeMouseEvent('click', true));
  await assert.rejects(pending, /not approved/);
  assert.equal(handed.length, 0, 'denial hands nothing to the picker');
}
// Approval hands exactly the approved copy over once; a later change by the caller does not reach the adapter.
{
  const { broker, handed, trustedAllow } = setup();
  const payload = { title: 'Consultation memo', text: 'original' };
  const pending = broker.invoke(selector, payload);
  await tick();
  payload.text = 'changed after the dialog opened';
  trustedAllow();
  assert.deepEqual(await pending, { opened: true });
  assert.deepEqual(handed, [{ title: 'Consultation memo', text: 'original' }]);
  // Each hand-off asks again.
  const second = broker.invoke(selector, memo);
  await tick();
  assert.equal(handed.length, 1, 'no hand-off before the second approval');
  trustedAllow();
  await second;
  assert.equal(handed.length, 2);
}
// Non-plain payloads are refused before consent.
{
  const { dialog, broker } = setup();
  await assert.rejects(broker.invoke(selector, { text: () => 'x' }), /plain data/);
  assert.equal(dialog.open, false);
}
assert.equal(fetchCalls, 0, 'no network request in any path');
console.log('verify-client-user-selected-app: ok');
