import { test } from 'node:test';
import assert from 'node:assert/strict';
import { secretItem, validateSecretItem } from './secret-item.mjs';
const input = { id: 'a'.repeat(32), title: 'Provider', key: 'API_KEY', value: 'synthetic-secret' };
test('credentials preserve opaque identity and all restricted values', () => {
  assert.deepEqual(secretItem(input), { format: 'kagitaba-secret-v1', ...input });
});
test('reject extra fields, malformed identity, unbounded values and secret-bearing diagnostics', () => {
  for (const changes of [{ owner: 'injected' }, { id: '../name' }, { key: 'PATH=x' }, { value: '' }, { value: 'x'.repeat(16385) }, { format: 'future' }]) {
    assert.throws(() => validateSecretItem({ ...secretItem(input), ...changes }), { message: 'Invalid restricted secret item.' });
  }
});
