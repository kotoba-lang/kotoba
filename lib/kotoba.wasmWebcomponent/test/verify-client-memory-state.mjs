// JUN-751: declare real volatile state without pretending to use persistent storage.
import assert from 'node:assert/strict';
import { clientRuntimeProblems, clientRuntimeConnectSrc, effectiveClientOperations } from '../src/kotoba-client-runtime.js';

const runtime = {
  schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile: 'trusted-page-v1', entry: 'index.html',
  'local-state': { adapter: 'memory', schema: 'kotoba-topology-emphasis', version: 1 }, workers: [], operations: [],
};
assert.deepEqual(clientRuntimeProblems(runtime), []);
assert.equal(clientRuntimeConnectSrc(runtime), "connect-src 'none'");
assert.deepEqual(effectiveClientOperations(runtime), []);
for (const adapter of ['indexeddb', 'opfs', 'localstorage']) {
  assert.deepEqual(clientRuntimeProblems({ ...runtime, 'local-state': { ...runtime['local-state'], adapter } }), []);
}
for (const state of [
  { adapter: 'remote', schema: 'x', version: 1 },
  { adapter: 'memory', schema: 'x', version: 0 },
  { adapter: 'memory', schema: 'x', version: 1, persistent: true },
]) assert.ok(clientRuntimeProblems({ ...runtime, 'local-state': state }).some(problem => problem.field === 'local-state'));

const operation = {
  capability: 'net/http-get', service: 'fixture', operation: 'read', consent: 'each-operation',
  'data-categories': [], endpoint: { origin: 'https://service.example', method: 'GET', path: '/items' },
};
const declared = { ...runtime, operations: [operation] };
assert.ok(clientRuntimeProblems(declared).some(problem => problem.error === 'capability-not-requested'));
assert.deepEqual(effectiveClientOperations(declared, { requestedCapabilities: ['net/http-get'] }), [], 'memory does not grant eligibility');
assert.ok(clientRuntimeProblems(declared, ['net/http-get'], 'https://service.example').some(problem => problem.error === 'service-origin-is-app-origin'));
assert.ok(clientRuntimeProblems({ ...runtime, operations: [{ ...operation, consent: 'remember' }] }, ['net/http-get']).some(problem => problem.error === 'invalid-operation'));
console.log('PASS: memory declaration, persistent adapter compatibility, malformed-state refusals and unchanged authority defaults');
