import { hostCaps, validateImportSurface } from './actor-host.js';

export const HTTP_LINKS = [
  { id: 'http-open', field: 'http_open', exportName: 'http-open', copyIn: [[0, 1]], copyOut: [] },
  { id: 'http-write', field: 'http_write', exportName: 'http-write', copyIn: [[1, 2]], copyOut: [] },
  { id: 'http-read', field: 'http_read', exportName: 'http-read', copyIn: [], copyOut: [[1, 2]] },
  { id: 'http-close', field: 'http_close', exportName: 'http-close', copyIn: [], copyOut: [] },
  { id: 'http-get', field: 'http_get', exportName: 'http-get', copyIn: [[0, 1], [3, 4]], copyOut: [[5, 6]] },
];

export const DB_LINKS = [
  { id: 'db-open', field: 'db_open', exportName: 'db-open', copyIn: [[0, 1]], copyOut: [] },
  { id: 'db-write', field: 'db_write', exportName: 'db-write', copyIn: [[1, 2]], copyOut: [] },
  { id: 'db-read', field: 'db_read', exportName: 'db-read', copyIn: [], copyOut: [[1, 2]] },
  { id: 'db-close', field: 'db_close', exportName: 'db-close', copyIn: [], copyOut: [] },
  { id: 'db-exchange', field: 'db_exchange', exportName: 'db-exchange', copyIn: [[0, 1], [3, 4]], copyOut: [[5, 6]] },
];

export const PG_SESSION_LINKS = [
  DB_LINKS[3],
  { id: 'pg-open', field: 'pg_open', exportName: 'pg-open',
    copyIn: [[0, 1], [3, 4], [5, 6]], copyOut: [] },
  { id: 'pg-query', field: 'pg_query', exportName: 'pg-query',
    copyIn: [[1, 2]], copyOut: [[3, 4]] },
];

export const PG_SIMPLE_QUERY_LINKS = [
  { id: 'pg-simple-query', field: 'pg_simple_query', exportName: 'pg-simple-query',
    copyIn: [[0, 1], [3, 4]], copyOut: [[5, 6]] },
];

export const PG_QUERY_STATE_LINKS = [
  { id: 'pg-query-state', field: 'pg_query_state', exportName: 'pg-query-state',
    copyIn: [[1, 2]], copyOut: [[3, 4], [5, 6, 7]] },
];

export const PG_PREPARED_LINKS = [
  { id: 'pg-prepare', field: 'pg_prepare', exportName: 'pg-prepare',
    copyIn: [[1, 2], [3, 4]], copyOut: [[5, 6], [7, 8, 7]] },
  { id: 'pg-execute-params2', field: 'pg_execute_params2', exportName: 'pg-execute-params2',
    copyIn: [[1, 2], [3, 4], [5, 6]], copyOut: [[7, 8], [9, 10, 7]] },
  { id: 'pg-close-statement', field: 'pg_close_statement', exportName: 'pg-close-statement',
    copyIn: [[1, 2]], copyOut: [[3, 4], [5, 6, 7]] },
];

export const PG_TYPED_PREPARED_LINKS = [
  { id: 'pg-prepare-typed', field: 'pg_prepare_typed', exportName: 'pg-prepare-typed',
    copyIn: [[1, 2], [3, 4], [5, 6]], copyOut: [[8, 9], [10, 11, 7]] },
  { id: 'pg-execute-params', field: 'pg_execute_params', exportName: 'pg-execute-params',
    copyIn: [[1, 2], [3, 4]], copyOut: [[5, 6], [7, 8, 7]] },
];

export const PG_PORTAL_LINKS = [
  { id: 'pg-bind-portal', field: 'pg_bind_portal', exportName: 'pg-bind-portal',
    copyIn: [[1, 2], [3, 4], [5, 6]], copyOut: [[7, 8], [9, 10, 7]] },
  { id: 'pg-fetch-portal', field: 'pg_fetch_portal', exportName: 'pg-fetch-portal',
    copyIn: [[1, 2]], copyOut: [[4, 5], [6, 7, 7]] },
  { id: 'pg-close-portal', field: 'pg_close_portal', exportName: 'pg-close-portal',
    copyIn: [[1, 2]], copyOut: [[3, 4], [5, 6, 7]] },
];

export const PG_COPY_LINKS = [
  { id: 'pg-copy-out', field: 'pg_copy_out', exportName: 'pg-copy-out',
    copyIn: [[1, 2]], copyOut: [[3, 4], [5, 6, 7]] },
  { id: 'pg-copy-in', field: 'pg_copy_in', exportName: 'pg-copy-in',
    copyIn: [[1, 2], [3, 4]], copyOut: [[5, 6], [7, 8, 7]] },
];

export const PG_BATCH_LINKS = [
  { id: 'pg-execute-batch', field: 'pg_execute_batch', exportName: 'pg-execute-batch',
    copyIn: [[1, 2]], copyOut: [[4, 5], [6, 7, 7]] },
];

export const PG_SESSION_RESET_LINKS = [
  { id: 'pg-session-reset', field: 'pg_session_reset', exportName: 'pg-session-reset',
    copyIn: [], copyOut: [[1, 2], [3, 4, 7]] },
];

export const PG_POOL_LINKS = [
  { id: 'pg-pool-open', field: 'pg_pool_open', exportName: 'pg-pool-open',
    copyIn: [[0, 1], [3, 4], [5, 6], [7, 8]], copyOut: [] },
  { id: 'pg-pool-acquire', field: 'pg_pool_acquire', exportName: 'pg-pool-acquire', copyIn: [], copyOut: [] },
  { id: 'pg-pool-query', field: 'pg_pool_query', exportName: 'pg-pool-query',
    copyIn: [[1, 2]], copyOut: [[3, 4], [5, 6, 7]] },
  { id: 'pg-pool-release', field: 'pg_pool_release', exportName: 'pg-pool-release', copyIn: [], copyOut: [] },
  { id: 'pg-pool-stats', field: 'pg_pool_stats', exportName: 'pg-pool-stats', copyIn: [], copyOut: [[1, 2, 32]] },
  { id: 'pg-pool-health', field: 'pg_pool_health', exportName: 'pg-pool-health', copyIn: [], copyOut: [] },
  { id: 'pg-pool-drain', field: 'pg_pool_drain', exportName: 'pg-pool-drain', copyIn: [], copyOut: [] },
  { id: 'pg-pool-close', field: 'pg_pool_close', exportName: 'pg-pool-close', copyIn: [], copyOut: [] },
];

export const PG_SCRAM_SESSION_LINKS = [
  { id: 'pg-open-scram-random', field: 'pg_open_scram_random', exportName: 'pg-open-scram-random',
    copyIn: [[0, 1], [3, 4], [5, 6], [7, 8]], copyOut: [] },
  { id: 'pg-close-scram', field: 'pg_close_scram', exportName: 'pg-close-scram',
    copyIn: [], copyOut: [] },
];

export const PG_EXPLICIT_SCRAM_LINKS = [
  { id: 'pg-open-scram', field: 'pg_open_scram', exportName: 'pg-open-scram',
    copyIn: [[0, 1], [3, 4], [5, 6], [7, 8], [9, 10]], copyOut: [] },
  PG_SCRAM_SESSION_LINKS[1],
];

export const PG_CANCELLABLE_SCRAM_LINKS = [
  { id: 'pg-open-scram-cancellable-random', field: 'pg_open_scram_cancellable_random',
    exportName: 'pg-open-scram-cancellable-random',
    copyIn: [[0, 1], [3, 4], [5, 6], [7, 8]], copyOut: [[9, 10, 4]] },
  { id: 'pg-cancel-authority-use', field: 'pg_cancel_authority_use', exportName: 'pg-cancel-authority-use',
    copyIn: [], copyOut: [] },
  PG_SCRAM_SESSION_LINKS[1],
];

function copy(memoryFrom, from, memoryTo, to, length) {
  if (!Number.isInteger(length) || length < 0) throw new Error('negative or non-integer component buffer length');
  const source = new Uint8Array(memoryFrom.buffer, from, length).slice();
  new Uint8Array(memoryTo.buffer, to, length).set(source);
}

export function createComponentLinks(providerInstance, consumerMemoryBox, specs = HTTP_LINKS) {
  if (!(providerInstance?.exports?.memory instanceof WebAssembly.Memory)) {
    throw new Error('component provider does not export linear memory');
  }
  const previousPages = providerInstance.exports.memory.grow(1);
  const scratchBase = previousPages * 65536;
  let active = false;
  const fields = {};
  for (const spec of specs) {
    const providerExport = providerInstance.exports[spec.exportName];
    if (typeof providerExport !== 'function' || fields[spec.field]) {
      throw new Error(`invalid or duplicate component binding: ${spec.field}`);
    }
    fields[spec.field] = (...args) => {
      if (active) throw new Error('reentrant component bridge call denied');
      if (!(consumerMemoryBox.memory instanceof WebAssembly.Memory)) throw new Error('consumer memory unavailable');
      active = true;
      try {
        const pairs = [...new Map([...spec.copyIn, ...spec.copyOut].map(pair => [pair.slice(0, 2).join(':'), pair])).values()];
        let cursor = scratchBase;
        const layout = new Map();
        for (const pair of pairs) {
          const length = Number(args[pair[1]]);
          if (!Number.isInteger(length) || length < 0 || cursor + length > scratchBase + 65536) {
            throw new Error('component bridge scratch limit exceeded');
          }
          layout.set(pair.slice(0, 2).join(':'), cursor); cursor += length;
        }
        const providerArgs = [...args];
        for (const pair of pairs) providerArgs[pair[0]] = layout.get(pair.slice(0, 2).join(':'));
        for (const pair of spec.copyIn) {
          copy(consumerMemoryBox.memory, Number(args[pair[0]]), providerInstance.exports.memory,
            layout.get(pair.slice(0, 2).join(':')), Number(args[pair[1]]));
        }
        const result = providerExport(...providerArgs);
        if (Number(result) > 0) for (const pair of spec.copyOut) {
          const length = pair.length === 3 ? pair[2] : Number(result);
          if (length > Number(args[pair[1]])) throw new Error('provider exceeded consumer output capacity');
          copy(providerInstance.exports.memory, layout.get(pair.slice(0, 2).join(':')),
            consumerMemoryBox.memory, Number(args[pair[0]]), length);
        }
        return result;
      } finally { active = false; }
    };
  }
  return fields;
}

export async function instantiateLinkedKotobaComponents(bytes, capsValue, providers) {
  const module = bytes instanceof WebAssembly.Module ? bytes : await WebAssembly.compile(bytes);
  const imports = WebAssembly.Module.imports(module);
  const specs = providers.flatMap(provider => provider.specs);
  const byField = new Map(specs.map(spec => [spec.field, spec]));
  const unsupported = imports.filter(item => item.module !== 'kotoba' || item.kind !== 'function' || !byField.has(item.name));
  if (unsupported.length) throw new Error(`unsupported linked component imports: ${JSON.stringify(unsupported)}`);
  const requested = imports.map(item => byField.get(item.name).id);
  const caps = hostCaps(capsValue);
  const validation = validateImportSurface(requested, caps);
  if (!validation.ok) throw new Error(`linked component surface rejected: ${JSON.stringify(validation.errors)}`);
  const memoryBox = {};
  const linked = {};
  for (const provider of providers) {
    const fields = createComponentLinks(provider.instance, memoryBox,
      provider.specs.filter(spec => requested.includes(spec.id)));
    for (const [field, implementation] of Object.entries(fields)) {
      if (linked[field]) throw new Error(`duplicate component provider field: ${field}`);
      linked[field] = implementation;
    }
  }
  let httpGets = 0;
  if (linked.http_get) {
    const implementation = linked.http_get;
    linked.http_get = (...args) => {
      if (httpGets >= caps.limits.maxHttpGets) return -1;
      const result = implementation(...args);
      httpGets += 1;
      return result;
    };
  }
  const instance = await WebAssembly.instantiate(module, { kotoba: linked });
  if (!(instance.exports.memory instanceof WebAssembly.Memory)) throw new Error('consumer does not export linear memory');
  memoryBox.memory = instance.exports.memory;
  return { module, instance, imports: requested };
}

export function instantiateLinkedKotobaComponent(bytes, capsValue, providerInstance, specs = HTTP_LINKS) {
  return instantiateLinkedKotobaComponents(bytes, capsValue, [{ instance: providerInstance, specs }]);
}
