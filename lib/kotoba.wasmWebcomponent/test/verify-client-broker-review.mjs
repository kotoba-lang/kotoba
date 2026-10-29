// Broker regression tests (KOTOBA-159 review findings 2, 4, 5, 6). Each case fails on the
// file before the fixes: undisplayed Fetch options and method-override headers reached the
// network, prefix routes admitted `..;` segments, browser-action origins entered connect-src,
// and connect-src read the descriptor again after validating it.
import assert from 'node:assert/strict';

const { prepareClientOperationRequest, clientRuntimeConnectSrc, clientEndpointAllowsRequest } =
  await import('../src/kotoba-client-runtime.js');

const get = {
  capability: 'net/http-get', service: 'svc', operation: 'read', consent: 'each-operation', 'data-categories': ['x'],
  endpoint: { origin: 'https://svc.example', method: 'GET', path: '/items' },
};

// Finding 2: only headers and body come from init; the sent Request is rebuilt.
{
  const snapshot = await prepareClientOperationRequest(get, {
    input: 'https://svc.example/items',
    init: { method: 'GET', headers: { accept: 'application/json' }, keepalive: true, cache: 'reload', priority: 'high', integrity: 'sha256-x' },
  });
  const sent = snapshot.input;
  assert.equal(sent.method, 'GET');
  assert.equal(sent.headers.get('accept'), 'application/json', 'declared headers are kept');
  assert.equal(sent.keepalive, false, 'keepalive is not taken from init');
  assert.equal(sent.cache, 'no-store');
  assert.equal(sent.mode, 'cors');
  assert.equal(sent.integrity, '', 'integrity is not taken from init');
  assert.equal(sent.credentials, 'omit');

  // A caller-built Request does not carry its own options over either.
  const crafted = new Request('https://svc.example/items', { keepalive: true, cache: 'reload', integrity: 'sha256-y' });
  const fromRequest = (await prepareClientOperationRequest(get, { input: crafted, init: { method: 'GET' } })).input;
  assert.equal(fromRequest.keepalive, false);
  assert.equal(fromRequest.integrity, '');
  assert.equal(fromRequest.cache, 'no-store');

  for (const name of ['X-HTTP-Method-Override', 'x-http-method', 'X-Method-Override']) {
    await assert.rejects(
      prepareClientOperationRequest(get, { input: 'https://svc.example/items', init: { method: 'GET', headers: { [name]: 'DELETE' } } }),
      /method override/, name);
  }
}

// Finding 4: a prefix route refuses `;` (Tomcat-style dot-segment parameters).
{
  const prefix = { origin: 'https://svc.example', routes: [{ method: 'GET', 'path-prefix': '/public/', 'query-params': [] }] };
  assert.equal(clientEndpointAllowsRequest(prefix, 'https://svc.example/public/a.txt'), true, 'ordinary prefix path');
  assert.equal(clientEndpointAllowsRequest(prefix, 'https://svc.example/public/.well-known/x'), true, 'dot-leading names stay allowed');
  assert.equal(clientEndpointAllowsRequest(prefix, 'https://svc.example/public/..;/admin/users'), false);
  assert.equal(clientEndpointAllowsRequest(prefix, 'https://svc.example/public/.;/admin'), false);
  // `/public/a;x=../../admin` is not a case: the URL parser already resolves it to `/public/admin`.
  assert.equal(clientEndpointAllowsRequest(prefix, 'https://svc.example/private/a.txt'), false, 'negative control: outside the prefix');
}

const runtime = (operations) => ({
  schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile: 'restricted-wasm-v1', entry: 'index.html',
  'local-state': { adapter: 'indexeddb', schema: 's', version: 1 }, operations,
});
const push = {
  capability: 'push/subscribe', service: 'push', operation: 'subscribe', consent: 'each-operation', 'data-categories': ['push'],
  endpoint: { origin: 'https://push.example', 'browser-action': 'push/subscribe' },
};

// Finding 5: connect-src lists HTTP endpoints only.
{
  assert.equal(clientRuntimeConnectSrc(runtime([push]), ['push/subscribe'], [], 'https://app.example'), "connect-src 'none'");
  assert.equal(clientRuntimeConnectSrc(runtime([get, push]), ['net/http-get', 'push/subscribe'], [], 'https://app.example'),
    'connect-src https://svc.example');
}

// Finding 6: connect-src is computed from the copy that was validated.
{
  let reads = 0;
  const evil = { ...get, endpoint: { origin: 'https://evil.example', method: 'GET', path: '/items' } };
  const shifty = runtime([]);
  Object.defineProperty(shifty, 'operations', { enumerable: true, get() { reads += 1; return reads <= 2 ? [get] : [evil]; } });
  const csp = clientRuntimeConnectSrc(shifty, ['net/http-get'], [], 'https://app.example');
  assert.equal(csp, 'connect-src https://svc.example');
  assert.equal(reads, 1, 'the descriptor is read once');
}

console.log('verify-client-broker-review: ok');
