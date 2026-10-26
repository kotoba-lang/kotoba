import { actorHostImports } from './actor-host.js';

const FIELD_TO_ID = new Map([
  ['transport_connect', 'transport-connect'], ['tls_open', 'tls-open'],
  ['tls_server_end_point', 'tls-server-end-point'],
  ['transport_write', 'transport-write'], ['transport_read', 'transport-read'],
  ['transport_close', 'transport-close'],
  ['scram_sha256', 'scram-sha256'], ['random_bytes', 'random-bytes'],
  ['pg_cancel_register', 'pg-cancel-register'], ['pg_cancel', 'pg-cancel'],
]);

export async function instantiateKotobaComponent(bytes, caps, options = {}) {
  const module = bytes instanceof WebAssembly.Module ? bytes : await WebAssembly.compile(bytes);
  const imports = WebAssembly.Module.imports(module);
  const unsupported = imports.filter(({ module: namespace, name, kind }) =>
    namespace !== 'kotoba' || kind !== 'function' || !FIELD_TO_ID.has(name));
  if (unsupported.length) {
    throw new Error(`unsupported Kotoba component imports: ${JSON.stringify(unsupported)}`);
  }
  const requested = imports.map(({ name }) => FIELD_TO_ID.get(name));
  if (new Set(requested).size !== requested.length) {
    throw new Error('duplicate Kotoba component import');
  }
  const memoryBox = {};
  const hostFunctions = actorHostImports(requested, caps, memoryBox, options);
  const missing = imports.filter(({ name }) => typeof hostFunctions[name] !== 'function');
  if (missing.length) {
    throw new Error(`unlinked Kotoba component imports: ${JSON.stringify(missing)}`);
  }
  const instance = await WebAssembly.instantiate(module, { kotoba: hostFunctions });
  if (!(instance.exports.memory instanceof WebAssembly.Memory)) {
    throw new Error('Kotoba component does not export linear memory');
  }
  memoryBox.memory = instance.exports.memory;
  return { module, instance, imports: requested };
}
