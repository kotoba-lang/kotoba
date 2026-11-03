// Local-only TLS integration probe. Generate a short-lived localhost certificate
// outside the checkout with DNS:localhost as subjectAltName. Put key.pem and
// cert.pem in PROBE_TLS_DIR and set NODE_EXTRA_CA_CERTS to that cert.pem.
// Never disable TLS verification. The server receives only a synthetic GET.
import assert from 'node:assert/strict';
import dns from 'node:dns';
import fs from 'node:fs';
import https from 'node:https';

dns.setDefaultResultOrder('ipv4first');
const dir = process.env.PROBE_TLS_DIR;
if (!dir) throw new Error('set PROBE_TLS_DIR to a synthetic certificate directory');
let count = 0, receivedResolve, closedResolve;
const received = new Promise((resolve) => { receivedResolve = resolve; });
const closed = new Promise((resolve) => { closedResolve = resolve; });
const server = https.createServer({ key: fs.readFileSync(`${dir}/key.pem`), cert: fs.readFileSync(`${dir}/cert.pem`) }, (request) => {
  count += 1;
  receivedResolve();
  request.on('close', closedResolve);
});
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const origin = `https://localhost:${server.address().port}`;
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
const op = { capability: 'test/read', service: 'synthetic', operation: 'read', consent: 'each-operation', 'data-categories': ['synthetic'], endpoint: { origin, method: 'GET', path: '/wait' } };
const runtime = { schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile: 'trusted-page-v1', entry: 'index.html', 'local-state': { adapter: 'indexeddb', schema: 's', version: 1 }, operations: [op] };
const host = createClientConsentHost();
const buttons = made.filter((element) => element.tagName === 'button');
const broker = createClientOperationBroker({ runtime, requestedCapabilities: [op.capability], approvedOperations: [op], hostSupportedOperations: [[op.capability, op.service, op.operation]], consentHost: host });
const selector = { capability: op.capability, service: op.service, operation: op.operation };
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
async function bounded(promise, message) {
  let timer;
  try {
    return await Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(message)), 5000); })]);
  } finally { clearTimeout(timer); }
}
try {
  const denied = broker.invoke(selector, { input: `${origin}/wait` });
  await tick();
  buttons[0].dispatch('click', new Mouse('click'));
  await assert.rejects(denied, /not approved/);
  assert.equal(count, 0);

  const controller = new AbortController();
  const pending = broker.invoke(selector, { input: `${origin}/wait` }, { signal: controller.signal });
  await tick(); now += 600;
  buttons[1].dispatch('pointerdown', new Mouse('pointerdown'));
  buttons[1].dispatch('click', new Mouse('click'));
  await bounded(received, 'server did not receive request');
  assert.equal(count, 1);
  controller.abort();
  await bounded(assert.rejects(pending), 'fetch did not abort');
  await bounded(closed, 'connection did not close');
  console.log('PASS: denial 0 requests; approved local TLS request reached server; abort rejected fetch and closed connection');
} finally {
  host.destroy();
  server.closeAllConnections();
  await new Promise((resolve) => server.close(resolve));
}
