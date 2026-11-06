import { clientRuntimeProblems } from '../../../../kotoba.wasmWebcomponent/src/kotoba-client-runtime.js';
const op = (operation, endpoint, cats) => ({ capability: 'update/' + operation, consent: 'each-operation', 'data-categories': cats, endpoint, operation, service: 'update-origin-placeholder' });
const base = (ops) => ({ schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile: 'trusted-page-v1', entry: 'index.html',
  'local-state': { adapter: 'localstorage', schema: 'itonami.update.state', version: 1 }, operations: ops });
const caps = ['update/check-updates', 'update/download-update'];
const ph = 'https://update-origin.invalid';
const good = base([
  op('check-updates', { origin: ph, method: 'POST', path: '/placeholder/check' }, ['installed-version-ids', 'channel']),
  op('download-update', { origin: ph, method: 'GET', path: '/placeholder/image' }, ['image-cid', 'channel'])]);
const out = {
  placeholderDescriptor: clientRuntimeProblems(good, caps, 'https://app.invalid'),
  localOnlyDescriptor: clientRuntimeProblems(base([]), [], 'https://app.invalid'),
  endpointUserSelectedString: clientRuntimeProblems(base([op('check-updates', 'user-selected', ['channel'])]), ['update/check-updates'], 'https://app.invalid'),
  weakConsent: clientRuntimeProblems(base([{ ...good.operations[0], consent: 'once' }]), caps, 'https://app.invalid'),
  httpOrigin: clientRuntimeProblems(base([op('check-updates', { origin: 'http://x.invalid', method: 'GET', path: '/a' }, ['channel'])]), ['update/check-updates'], 'https://app.invalid'),
};
console.log(JSON.stringify(out, null, 1));
