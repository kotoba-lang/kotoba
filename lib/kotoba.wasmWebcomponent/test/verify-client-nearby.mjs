// AWAI-3059: nearby-device operations. A nearby endpoint reaches a device before its identity is
// known, so it declares an action and bearers instead of a peer-id, address or origin. It runs
// through the same host peer adapter path as libp2p (budgets, deadline, abort signal). Uses a
// minimal fake DOM so the real createClientConsentHost / createClientOperationBroker run in Node.
// Every case fails on the previous file, which has no nearby transport.
import assert from 'node:assert/strict';
import { DISCLOSURE } from './client-runtime-fixtures.mjs';

class FakeMouseEvent { constructor(type, trusted) { this.type = type; this.isTrusted = trusted; } }
let now = 0;
class FakeElement {
  constructor(tag) { this.tagName = tag; this.listeners = new Map(); this.isConnected = true; this.open = false; this.textContent = ''; }
  append() {}
  setAttribute() {}
  focus() {}
  remove() { this.isConnected = false; }
  addEventListener(type, fn) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn]); }
  dispatch(type, event) { event.currentTarget = this; for (const fn of this.listeners.get(type) ?? []) fn(event); }
  showModal() { if (this.open) throw new Error('already open'); this.open = true; }
  close() { this.open = false; }
}
const created = [];
const doc = { body: new FakeElement('body'), defaultView: { MouseEvent: FakeMouseEvent, performance: { now: () => now } }, createElement(tag) { const el = new FakeElement(tag); created.push(el); return el; } };
globalThis.document = doc;
let fetchCalls = 0;
globalThis.fetch = async () => { fetchCalls++; throw new Error('nearby operations must not fetch'); };

const { clientRuntimeProblems, clientNearbyEndpointProblems, clientRuntimeConnectSrc, clientEndpointAllowsRequest,
  prepareClientOperationRequest, createClientConsentHost, createClientOperationBroker } = await import('../src/kotoba-client-runtime.js');

const endpoint = (action, bearers, extra = {}) => ({
  transport: 'nearby', action, bearers, 'max-request-bytes': 4096, 'max-response-bytes': 4096, 'timeout-ms': 1000, ...extra,
});
const op = (operation, ep, extra = {}) => ({
  capability: 'nearby/pair', service: 'awai-pair', operation, consent: 'each-operation', disclosure: DISCLOSURE, 'data-categories': ['pairing-token'],
  endpoint: ep, ...extra,
});
const advertise = op('advertise', endpoint('advertise', ['nsd', 'ble']));
const connect = op('connect', endpoint('connect', ['nsd']));
const send = op('send', endpoint('send', ['nsd'], { 'max-request-bytes': 128 }));
const http = {
  capability: 'net/http-get', service: 'svc', operation: 'read', consent: 'each-operation', disclosure: DISCLOSURE, 'data-categories': ['x'],
  endpoint: { origin: 'https://svc.example', method: 'GET', path: '/items' },
};
const runtime = (operations) => ({
  schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile: 'trusted-page-v1', entry: 'index.html',
  'local-state': { adapter: 'indexeddb', schema: 's', version: 1 }, operations,
});
const caps = ['nearby/pair', 'net/http-get'];
const problems = (operations) => clientRuntimeProblems(runtime(operations), caps, 'https://app.example').map((p) => p.error);

// 1. Declaration: a known action, a non-empty unique list of known bearers, bounded budgets and a deadline up to 120 s.
{
  assert.deepEqual(problems([advertise, connect, send, http]), [], 'valid nearby declarations');
  assert.deepEqual(problems([op('browse', endpoint('browse', ['wifi-direct', 'wifi-aware'], { 'timeout-ms': 120000 }))]), []);
  for (const [label, ep] of [
    ['unknown action', endpoint('listen', ['nsd'])],
    ['empty bearers', endpoint('connect', [])],
    ['duplicate bearer', endpoint('connect', ['nsd', 'nsd'])],
    ['Nearby Connections is not adopted', endpoint('connect', ['nearby'])],
    ['bearers must be a list', endpoint('connect', 'nsd')],
    ['deadline over 120 s', endpoint('advertise', ['nsd'], { 'timeout-ms': 120001 })],
    ['request budget over 1 MiB', endpoint('send', ['nsd'], { 'max-request-bytes': 1048577 })],
    ['no origin on a nearby endpoint', endpoint('connect', ['nsd'], { origin: 'https://lan.example' })],
    ['no fixed address on a nearby endpoint', endpoint('connect', ['nsd'], { addresses: ['/ip4/10.0.0.5/tcp/4242'] })],
  ]) {
    assert.ok(problems([op('x', ep)]).includes('invalid-operation'), label);
    assert.deepEqual(clientNearbyEndpointProblems(ep), ['invalid-nearby-endpoint'], label);
  }
  assert.deepEqual(clientNearbyEndpointProblems(connect.endpoint), []);
  assert.ok(problems([{ ...connect, 'redirect-origins': ['https://svc.example'] }]).includes('browser-operation-has-http-options'));
}

// 2. Nearby operations add nothing to connect-src and are never an HTTP endpoint.
{
  assert.equal(clientRuntimeConnectSrc(runtime([advertise, connect, http]), caps, [], 'https://app.example'), 'connect-src https://svc.example');
  assert.equal(clientRuntimeConnectSrc(runtime([advertise]), caps, [], 'https://app.example'), "connect-src 'none'");
  assert.equal(clientEndpointAllowsRequest(connect.endpoint, 'https://svc.example/items'), false);
  await assert.rejects(prepareClientOperationRequest(connect, { input: 'https://svc.example/items' }), /HTTP endpoint declaration required/);
}

function setup(peerAdapters) {
  created.length = 0;
  const consentHost = createClientConsentHost({ document: doc });
  const dialog = created.find((el) => el.tagName === 'dialog');
  const scope = created.find((el) => el.tagName === 'pre');
  const [deny, allow] = created.filter((el) => el.tagName === 'button');
  const ops = [advertise, connect, send];
  const broker = createClientOperationBroker({
    runtime: runtime(ops), requestedCapabilities: ['nearby/pair'], approvedOperations: ops,
    hostSupportedOperations: ops.map((o) => [o.capability, o.service, o.operation]), peerAdapters, consentHost,
  });
  const trustedAllow = () => {
    now += 600;
    allow.dispatch('pointerdown', new FakeMouseEvent('pointerdown', true));
    allow.dispatch('click', new FakeMouseEvent('click', true));
  };
  return { dialog, scope, deny, broker, trustedAllow };
}
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const sel = (operation) => ({ capability: 'nearby/pair', service: 'awai-pair', operation });

// 3. A missing host adapter fails before consent; the dialog never opens.
{
  const { dialog, broker } = setup({ 'awai-pair': { advertise: () => ({ ok: true }) } });
  await assert.rejects(broker.invoke(sel('connect'), { bearer: 'nsd', peer: 'abcd1234efgh' }), /peer operation is not host-supported/);
  assert.equal(dialog.open, false);
}

// 4. Payload checks run before consent.
{
  const calls = [];
  const adapter = (x) => { calls.push(x); return { ok: true }; };
  const { dialog, broker } = setup({ 'awai-pair': { advertise: adapter, connect: adapter, send: adapter } });
  await assert.rejects(broker.invoke(sel('connect'), { bearer: 'ble', peer: 'abcd1234efgh' }), /bearer is not declared/);
  await assert.rejects(broker.invoke(sel('connect'), { bearer: 'nsd' }), /requires a discovered peer token/);
  await assert.rejects(broker.invoke(sel('connect'), { bearer: 'nsd', peer: '10.0.0.5' }), /requires a discovered peer token/, 'an address is not a peer token');
  await assert.rejects(broker.invoke(sel('connect'), { bearer: 'nsd', peer: 'ABCD1234' }), /requires a discovered peer token/);
  await assert.rejects(broker.invoke(sel('connect'), { bearer: 'nsd', peer: 'abcd1234efgh', data: 'x' }), /undeclared fields/, 'only send carries data');
  await assert.rejects(broker.invoke(sel('advertise'), { bearer: 'nsd', peer: 'abcd1234efgh' }), /undeclared fields/);
  await assert.rejects(broker.invoke(sel('advertise'), { bearer: 'nsd', address: '10.0.0.5' }), /undeclared fields/);
  await assert.rejects(broker.invoke(sel('advertise'), {}), /bearer is not declared/);
  await assert.rejects(broker.invoke(sel('advertise'), { bearer: 'nsd', run: () => 1 }), /bounded plain data/);
  await assert.rejects(broker.invoke(sel('send'), { bearer: 'nsd', peer: 'abcd1234efgh', data: 'x'.repeat(200) }), /exceeds budget/);
  assert.equal(dialog.open, false, 'no consent shown for a refused payload');
  assert.equal(calls.length, 0);
}

// 5. Deny runs nothing; Allow runs the captured adapter once with the copied payload and an abort signal;
//    the consent shows the nearby details; each invocation asks again.
{
  const calls = [];
  const adapters = { 'awai-pair': {
    advertise: (x) => { calls.push(x); return { advertising: true }; },
    connect: (x) => { calls.push(x); return { connected: true }; },
    send: (x) => { calls.push(x); return { sent: x.payload.data.length }; },
  } };
  const { dialog, scope, deny, broker, trustedAllow } = setup(adapters);
  adapters['awai-pair'].connect = () => { throw new Error('replaced adapter must not run'); };

  const denied = broker.invoke(sel('connect'), { bearer: 'nsd', peer: 'abcd1234efgh' });
  await tick();
  assert.equal(dialog.open, true);
  assert.match(scope.textContent, /Endpoint: nearby device \(discovered locally\)/);
  assert.match(scope.textContent, /Nearby device: connect over nsd/);
  assert.match(scope.textContent, /Peer: abcd1234efgh/);
  assert.match(scope.textContent, /Deadline: 1000 ms/);
  assert.match(scope.textContent, /Data categories: pairing-token/);
  assert.doesNotMatch(scope.textContent, /PeerID:|https:/, 'no libp2p identity or fake origin is displayed');
  deny.dispatch('click', new FakeMouseEvent('click', true));
  await assert.rejects(denied, /not approved/);
  assert.equal(calls.length, 0, 'denial runs nothing');

  const payload = { bearer: 'nsd', peer: 'abcd1234efgh' };
  const approved = broker.invoke(sel('connect'), payload);
  payload.peer = 'zzzz9999zzzz';          // mutating the caller's object after invoke changes nothing
  await tick();
  trustedAllow();
  assert.deepEqual(await approved, { connected: true });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].payload.peer, 'abcd1234efgh');
  assert.ok(calls[0].signal instanceof AbortSignal, 'the adapter receives an abort signal');

  const sending = broker.invoke(sel('send'), { bearer: 'nsd', peer: 'abcd1234efgh', data: 'hello' });
  await tick();
  assert.equal(dialog.open, true, 'a later invocation asks again');
  trustedAllow();
  assert.deepEqual(await sending, { sent: 5 });

  const again = broker.invoke(sel('advertise'), { bearer: 'ble' });
  await tick();
  assert.match(scope.textContent, /Nearby device: advertise over ble/);
  assert.match(scope.textContent, /Peer: \(none/);
  trustedAllow();
  assert.deepEqual(await again, { advertising: true });
}

// 6. The deadline aborts the adapter's signal and rejects; a response over budget is refused.
{
  let seen;
  const fast = op('advertise', endpoint('advertise', ['nsd'], { 'timeout-ms': 20, 'max-response-bytes': 16 }));
  const slowRuntime = runtime([fast]);
  created.length = 0;
  const consentHost = createClientConsentHost({ document: doc });
  const [, allow] = created.filter((el) => el.tagName === 'button');
  let mode = 'hang';
  const broker = createClientOperationBroker({
    runtime: slowRuntime, requestedCapabilities: ['nearby/pair'], approvedOperations: [fast],
    hostSupportedOperations: [['nearby/pair', 'awai-pair', 'advertise']], consentHost,
    peerAdapters: { 'awai-pair': { advertise: ({ signal }) => { seen = signal; return mode === 'hang' ? new Promise(() => {}) : { big: 'x'.repeat(64) }; } } },
  });
  const press = () => { now += 600; allow.dispatch('pointerdown', new FakeMouseEvent('pointerdown', true)); allow.dispatch('click', new FakeMouseEvent('click', true)); };
  const hung = broker.invoke(sel('advertise'), { bearer: 'nsd' });
  await tick(); press();
  await assert.rejects(hung, /cancelled or timed out/);
  assert.equal(seen.aborted, true, 'the deadline aborts the adapter signal (stop advertising)');
  mode = 'big';
  const big = broker.invoke(sel('advertise'), { bearer: 'nsd' });
  await tick(); press();
  await assert.rejects(big, /exceeds budget/);
}

assert.equal(fetchCalls, 0, 'no nearby case reached fetch');
console.log('PASS: nearby declarations, connect-src exclusion, pre-consent payload checks, consent details, deny/allow, fresh consent, deadline abort and response budget');
