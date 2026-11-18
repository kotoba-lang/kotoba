const NAME = /^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$/;
const ENTRY = /^[A-Za-z0-9._~!$&'()+,;=@/-]+$/;
const ORIGIN = /^https:\/\/(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?::(?:[1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?$/;
const RUNTIME_KEYS = ['entry', 'local-state', 'operations', 'profile', 'schema', 'target', 'workers'];
const OPERATION_REQUIRED_KEYS = ['capability', 'consent', 'data-categories', 'endpoint', 'operation', 'service'];
const OPERATION_KEYS = [...OPERATION_REQUIRED_KEYS, 'redirect-origins', 'artifact'];
export const CLIENT_INFERENCE_PROTOCOL = 'kotoba.inference.v1';
const INFERENCE_REQUEST_KEYS = Object.freeze({
  load: ['approvedOperations', 'history', 'modelId'],
  generate: ['prompt'],
  cancel: [],
  reset: [],
});

function record(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function exactKeys(value, keys) {
  return record(value)
    && Object.keys(value).length === keys.length
    && keys.every((key) => Object.hasOwn(value, key));
}

function validName(value) {
  return typeof value === 'string' && NAME.test(value);
}

function validEntry(value) {
  return typeof value === 'string'
    && value.length > 0
    && value.length <= 512
    && ENTRY.test(value)
    && !value.startsWith('/')
    && !value.endsWith('/')
    && !value.includes('//')
    && !/(^|\/)\.{1,2}(\/|$)/.test(value);
}

function validOrigin(value) {
  if (typeof value !== 'string' || !ORIGIN.test(value)) return false;
  try { return new URL(value).origin === value; } catch { return false; }
}

const ENDPOINT_METHODS = new Set(['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE']);
const METHOD_OVERRIDE_HEADERS = ['x-http-method-override', 'x-http-method', 'x-method-override'];
const ENDPOINT_SEGMENT = /^[A-Za-z0-9._~!$&'()*+,;=:@_-]+$/;
const ENDPOINT_PARAMETER = /^:[A-Za-z][A-Za-z0-9_]*$/;
const ENDPOINT_QUERY_PARAMETER = /^[A-Za-z0-9._~_-]{1,128}$/;
const WILDCARD_HTTPS_ORIGIN = /^https:\/\/\*\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;

function validRedirectOrigin(value) {
  return validOrigin(value) || (typeof value === 'string' && WILDCARD_HTTPS_ORIGIN.test(value));
}

function redirectOriginAllows(declaredOrigin, actualOrigin) {
  if (declaredOrigin === actualOrigin) return true;
  if (typeof declaredOrigin !== 'string' || !WILDCARD_HTTPS_ORIGIN.test(declaredOrigin)) return false;
  try {
    const actual = new URL(actualOrigin);
    const suffix = declaredOrigin.slice('https://*.'.length);
    return actual.protocol === 'https:'
      && actual.port === ''
      && actual.hostname !== suffix
      && actual.hostname.endsWith(`.${suffix}`);
  } catch {
    return false;
  }
}

function validEndpointPath(value) {
  if (typeof value !== 'string' || value.length > 2048 || !value.startsWith('/')
      || value.startsWith('//') || value.includes('?') || value.includes('#')
      || value.includes('\\') || value.includes('//')) return false;
  if (value === '/') return true;
  const segments = value.slice(1).split('/');
  return segments.every((segment) => segment.length > 0
    && segment !== '.' && segment !== '..'
    && (ENDPOINT_PARAMETER.test(segment) || ENDPOINT_SEGMENT.test(segment)));
}

// A peer is a cryptographic identity, never a fabricated HTTPS origin.
function literalPeerAddress(address, peer, listener = false) {
  if (typeof address !== 'string' || address.length > 512) return false;
  const match = address.match(/^\/ip4\/(\d{1,3}(?:\.\d{1,3}){3})\/(?:udp\/(\d{1,5})\/(quic-v1|webrtc-direct\/certhash\/u[A-Za-z0-9_-]{46})|tcp\/(\d{1,5}))(.*)$/);
  if (!match || !match[1].split('.').every(n => String(Number(n)) === n && Number(n) <= 255)
      || match[1] === '0.0.0.0' || Number(match[1].split('.')[0]) >= 224
      || Number(match[2] ?? match[4]) < 1 || Number(match[2] ?? match[4]) > 65535) return false;
  const suffix = match[5];
  const id = '[1-9A-HJ-NP-Za-km-z]{32,128}';
  if (listener) return !match[3]?.startsWith('webrtc')
    && (suffix === '' || new RegExp(`^/p2p/(${id})/p2p-circuit$`).test(suffix));
  if (suffix === `/p2p/${peer}`) return true;
  const circuit = suffix.match(new RegExp(`^/p2p/(${id})/p2p-circuit/p2p/(${id})$`));
  return !match[3]?.startsWith('webrtc') && !!circuit && circuit[1] !== peer && circuit[2] === peer;
}
function peerScopeValid(value, receive) {
  const keys = receive ? ['snapshot-cid','max-transfer-bytes','listen-address','receive-ms','allow-read-back'] : ['snapshot-cid','max-transfer-bytes'];
  return exactKeys(value, keys)
    && typeof value['snapshot-cid'] === 'string' && /^b[a-z2-7]{30,127}$/.test(value['snapshot-cid'])
    && Number.isSafeInteger(value['max-transfer-bytes']) && value['max-transfer-bytes'] > 0 && value['max-transfer-bytes'] <= 268435456
    && (!receive || (typeof value['allow-read-back'] === 'boolean' && literalPeerAddress(value['listen-address'], null, true)
      && Number.isSafeInteger(value['receive-ms']) && value['receive-ms'] > 0 && value['receive-ms'] <= 21600000));
}
export function clientPeerEndpointProblems(value) {
  const keys = ['transport','peer-id','addresses','protocol','action','max-request-bytes','max-response-bytes','timeout-ms'];
  const scoped = record(value) && Object.hasOwn(value, 'scope');
  const receive = value?.action === 'receive-snapshot';
  if (!exactKeys(value, scoped ? [...keys, 'scope'] : keys)
      || value.transport !== 'libp2p'
      || typeof value['peer-id'] !== 'string' || !/^[1-9A-HJ-NP-Za-km-z]{32,128}$/.test(value['peer-id'])
      || !Array.isArray(value.addresses) || value.addresses.length < (receive ? 0 : 1) || value.addresses.length > 4
      || new Set(value.addresses).size !== value.addresses.length
      || !value.addresses.every(address => literalPeerAddress(address, value['peer-id']))
      || typeof value.protocol !== 'string' || !/^\/[A-Za-z0-9._/-]{1,110}\/\d+\.\d+\.\d+$/.test(value.protocol)
      || !validName(value.action)
      || (scoped && (!['sync-push','sync-pull','pin-query','receive-snapshot'].includes(value.action)
        || value.protocol !== '/awai/yataverse/1.0.0' || !peerScopeValid(value.scope, receive)))
      || (receive && !scoped)
      || !Number.isSafeInteger(value['max-request-bytes']) || value['max-request-bytes'] < 1 || value['max-request-bytes'] > 1048576
      || !Number.isSafeInteger(value['max-response-bytes']) || value['max-response-bytes'] < 1 || value['max-response-bytes'] > 1048576
      || !Number.isSafeInteger(value['timeout-ms']) || value['timeout-ms'] < 1 || value['timeout-ms'] > 60000) {
    return ['invalid-peer-endpoint'];
  }
  return [];
}

// Nearby-device operations (AWAI-3059) reach a device before its identity is known, so they
// declare an action and the allowed bearers, never a peer-id, address or origin. The host
// adapter owns discovery and sockets. It must map a peer token only to a device it discovered
// for this session, keep connections on link-local, private (RFC 1918 / ULA) or P2P/BLE group
// addresses, and stop when the operation's signal aborts. Trust comes from the app's own
// pairing (a confirmation code and a signed link), never from discovery or consent.
const NEARBY_ACTIONS = new Set(['advertise', 'browse', 'connect', 'send']);
const NEARBY_BEARERS = new Set(['nsd', 'ble', 'wifi-direct', 'wifi-aware']);
const NEARBY_PEER_TOKEN = /^[a-z0-9]{8,64}$/;
export function clientNearbyEndpointProblems(value) {
  if (!exactKeys(value, ['transport', 'action', 'bearers', 'max-request-bytes', 'max-response-bytes', 'timeout-ms'])
      || value.transport !== 'nearby'
      || !NEARBY_ACTIONS.has(value.action)
      || !Array.isArray(value.bearers) || value.bearers.length < 1
      || !value.bearers.every((bearer) => NEARBY_BEARERS.has(bearer))
      || new Set(value.bearers).size !== value.bearers.length
      || !Number.isSafeInteger(value['max-request-bytes']) || value['max-request-bytes'] < 1 || value['max-request-bytes'] > 1048576
      || !Number.isSafeInteger(value['max-response-bytes']) || value['max-response-bytes'] < 1 || value['max-response-bytes'] > 1048576
      || !Number.isSafeInteger(value['timeout-ms']) || value['timeout-ms'] < 1 || value['timeout-ms'] > 120000) {
    return ['invalid-nearby-endpoint'];
  }
  return [];
}
/** A nearby payload names one declared bearer; connect and send name a discovered peer token; only send carries data. */
function nearbyPayloadProblem(endpoint, payload) {
  const targeted = endpoint.action === 'connect' || endpoint.action === 'send';
  const allowed = ['bearer', ...(targeted ? ['peer'] : []), ...(endpoint.action === 'send' ? ['data'] : [])];
  if (!record(payload) || Object.keys(payload).some((key) => !allowed.includes(key))) return 'nearby payload has undeclared fields';
  if (typeof payload.bearer !== 'string' || !endpoint.bearers.includes(payload.bearer)) return 'nearby bearer is not declared';
  if (targeted && !(typeof payload.peer === 'string' && NEARBY_PEER_TOKEN.test(payload.peer))) return 'nearby action requires a discovered peer token';
  return null;
}

function validEndpoint(value) {
  return (record(value) && value.transport === 'libp2p' && clientPeerEndpointProblems(value).length === 0)
    || (record(value) && value.transport === 'nearby' && clientNearbyEndpointProblems(value).length === 0)
    || (exactKeys(value, ['origin', 'browser-action'])
      && validOrigin(value.origin) && validName(value['browser-action']))
    || (exactKeys(value, ['origin', 'method', 'path'])
      && validOrigin(value.origin)
      && typeof value.method === 'string'
      && ENDPOINT_METHODS.has(value.method)
      && validEndpointPath(value.path))
    || (exactKeys(value, ['origin', 'routes'])
      && validOrigin(value.origin)
      && Array.isArray(value.routes)
      && value.routes.length > 0
      && value.routes.length <= 128
      && value.routes.every(validEndpointRoute)
      && new Set(value.routes.map(canonical)).size === value.routes.length);
}

function validEndpointRoute(route) {
  const exactPath = exactKeys(route, ['method', 'path', 'query-params'])
    || exactKeys(route, ['method', 'path', 'query-params', 'query-values']);
  const prefixPath = exactKeys(route, ['method', 'path-prefix', 'query-params'])
    || exactKeys(route, ['method', 'path-prefix', 'query-params', 'query-values']);
  if (!exactPath && !prefixPath) return false;
  if (typeof route.method !== 'string' || !ENDPOINT_METHODS.has(route.method)) return false;
  if (exactPath && !validEndpointPath(route.path)) return false;
  if (prefixPath && !validEndpointPathPrefix(route['path-prefix'])) return false;
  return Array.isArray(route['query-params'])
    && route['query-params'].length <= 64
    && route['query-params'].every((parameter) => typeof parameter === 'string'
      && ENDPOINT_QUERY_PARAMETER.test(parameter))
    && new Set(route['query-params']).size === route['query-params'].length
    && (!Object.hasOwn(route, 'query-values') || (record(route['query-values'])
      && Object.entries(route['query-values']).every(([parameter, value]) => (
        ENDPOINT_QUERY_PARAMETER.test(parameter)
          && route['query-params'].includes(parameter)
          && typeof value === 'string'
          && value.length <= 512
      ))));
}

function validEndpointPathPrefix(value) {
  if (typeof value !== 'string' || value.length > 2048 || !value.startsWith('/')
      || value.startsWith('//') || !value.endsWith('/') || value.includes('?')
      || value.includes('#') || value.includes('\\') || value.includes('//')) return false;
  const segments = value.slice(1, -1).split('/');
  return segments.length > 0 && segments.every((segment) => segment.length > 0
    && segment !== '.' && segment !== '..' && ENDPOINT_SEGMENT.test(segment));
}

function endpointRequest(payload, endpointOrigin) {
  if (!record(payload) || !Object.hasOwn(payload, 'input')) return null;
  const input = payload.input;
  const init = record(payload.init) ? payload.init : {};
  const source = (typeof Request !== 'undefined' && input instanceof Request)
    ? input.url
    : (typeof URL !== 'undefined' && input instanceof URL)
      ? input.href
      : input;
  if (typeof source !== 'string') return null;
  try {
    const url = new URL(source, endpointOrigin);
    const method = String(init.method
      ?? ((typeof Request !== 'undefined' && input instanceof Request) ? input.method : 'GET'))
      .toUpperCase();
    return {
      origin: url.origin,
      path: url.pathname,
      method,
      search: url.search,
      queryParameters: [...new Set(url.searchParams.keys())],
      searchParams: url.searchParams,
      hash: url.hash,
      hasCredentials: Boolean(url.username || url.password),
    };
  } catch {
    return null;
  }
}

function endpointPathMatches(pattern, path) {
  if (!validEndpointPath(pattern) || typeof path !== 'string') return false;
  const expected = pattern === '/' ? [] : pattern.slice(1).split('/');
  const actual = path === '/' ? [] : path.startsWith('/') ? path.slice(1).split('/') : null;
  if (!actual || expected.length !== actual.length) return false;
  return expected.every((segment, index) => ENDPOINT_PARAMETER.test(segment)
    ? /^[A-Za-z0-9][A-Za-z0-9._~:@_-]{0,127}$/.test(actual[index])
    : segment === actual[index]);
}

function endpointRequestMatches(endpoint, payload, endpointOrigin) {
  if (!record(endpoint)) return false;
  if (Array.isArray(endpoint.routes)) {
    const request = endpointRequest(payload, endpointOrigin);
    if (request === null || request.origin !== endpointOrigin || request.hash !== ''
        || !validEndpointPath(request.path)) return false;
    return endpoint.routes.some((route) => route.method === request.method
      && (Object.hasOwn(route, 'path')
        ? endpointPathMatches(route.path, request.path)
        // A prefix route admits paths it did not spell out; refuse `;` there,
        // which servers such as Tomcat treat as a parameter of a dot segment
        // (`/public/..;/admin` resolves to `/admin`).
        : request.path.startsWith(route['path-prefix']) && !request.path.includes(';'))
      && request.queryParameters.every((parameter) => route['query-params'].includes(parameter))
      && (request.search === '' || request.searchParams.size === request.queryParameters.length)
      && Object.entries(route['query-values'] ?? {}).every(([parameter, value]) => (
        request.searchParams.getAll(parameter).length === 1
          && request.searchParams.get(parameter) === value
      )));
  }
  if (!Object.hasOwn(endpoint, 'path')) return true;
  const request = endpointRequest(payload, endpointOrigin);
  return request !== null
    && request.origin === endpointOrigin
    && request.method === endpoint.method
    && request.search === ''
    && request.hash === ''
    && endpointPathMatches(endpoint.path, request.path);
}

function endpointSupportsDeclaredRedirects(endpoint) {
  const routes = Array.isArray(endpoint?.routes)
    ? endpoint.routes
    : [{ method: endpoint?.method, 'query-params': [], 'query-values': {} }];
  return routes.every((route) => (
    ['GET', 'HEAD'].includes(route.method)
    && (route['query-params'] ?? []).every((parameter) => (
      Object.hasOwn(route['query-values'] ?? {}, parameter)
    ))
  ));
}

function snapshotPayloadValue(value) {
  if (value === null || typeof value !== 'object') return value;
  if (typeof globalThis.structuredClone !== 'function') {
    throw new Error('client operation payload cannot be snapshotted safely');
  }
  return globalThis.structuredClone(value);
}

async function snapshotOperationPayload(payload, operation, endpointOrigin, request, signal) {
  if (!record(payload) || !Object.hasOwn(payload, 'input') || typeof Request === 'undefined') {
    throw new Error('client operation request cannot be snapshotted');
  }
  const input = payload.input;
  const source = (input instanceof Request)
    ? input.clone()
    : new URL(
      (typeof URL !== 'undefined' && input instanceof URL) ? input.href : input,
      endpointOrigin,
    ).href;
  // Only headers and body come from the caller's init. Other Fetch options
  // (keepalive, priority, integrity, mode, browsingTopics, ...) are not shown
  // in the consent dialog, so they are not taken.
  const init = {};
  if (record(payload.init)) {
    for (const key of ['headers', 'body']) {
      if (Object.hasOwn(payload.init, key)) init[key] = payload.init[key];
    }
  }
  const redirectOrigins = operation['redirect-origins'] ?? [];
  const redirect = redirectOrigins.length > 0
    && ['GET', 'HEAD'].includes(request.method)
    ? 'follow'
    : 'error';
  const captured = new Request(source, {
    ...init,
    method: request.method,
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
    redirect,
  });
  // A method-override header would let an approved method act as another.
  for (const name of METHOD_OVERRIDE_HEADERS) {
    if (captured.headers.has(name)) throw new Error('client request method override header refused');
  }
  // Request.clone() alone does not freeze a caller-owned ReadableStream.
  // Materialize a bounded body before showing consent; a later stream write
  // cannot change what the user is being asked to send.
  const body = captured.body ? await boundedBytes(captured.body, 16777216, 5000, signal) : null;
  // Rebuild from the URL so no option of a caller-supplied Request carries over.
  const requestSnapshot = new Request(captured.url, {
    method: captured.method,
    headers: captured.headers,
    ...(body === null ? {} : { body }),
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
    redirect,
    mode: 'cors',
    cache: 'no-store',
    // The signal belongs to the Request. Passing it to fetch() as an init would
    // build a new Request and reset its referrer policy (KOTOBA-159 R1).
    ...(signal === undefined ? {} : { signal }),
  });
  const requestUrl = new URL(requestSnapshot.url);
  if (requestUrl.origin !== endpointOrigin) {
    throw new Error('client request changed while its approved scope was being captured');
  }

  const snapshot = {};
  for (const [key, value] of Object.entries(payload)) {
    if (key === 'input' || key === 'init') continue;
    snapshot[key] = snapshotPayloadValue(value);
  }
  snapshot.input = requestSnapshot;
  // Request now owns the method, headers, body, credentials, redirect mode,
  // and other Fetch options. Do not let an adapter reapply mutable init data.
  snapshot.init = Object.freeze({ method: requestSnapshot.method });
  return Object.freeze(snapshot);
}

/** Pure preflight/snapshot, not an approval or a transport capability. */
export async function prepareClientOperationRequest(operation, payload, signal) {
  if (signal !== undefined && !(signal instanceof AbortSignal)) throw new TypeError('invalid operation signal');
  if (signal?.aborted) throw new Error('client operation cancelled');
  if (!validEndpoint(operation?.endpoint) || Object.hasOwn(operation.endpoint, 'browser-action') || Object.hasOwn(operation.endpoint, 'transport')) throw new TypeError('HTTP endpoint declaration required');
  const pinned = freezeClone(operation), origin = pinned.endpoint.origin;
  if (origin === globalThis.location?.origin) throw new Error('app-origin API refused');
  const request = endpointRequest(payload, origin);
  if (!request || request.hasCredentials || !endpointRequestMatches(pinned.endpoint, payload, origin)) throw new Error('request scope is not declared');
  const snapshot = await snapshotOperationPayload(payload, pinned, origin, request, signal);
  if (signal?.aborted) throw new Error('client operation cancelled');
  if (!endpointRequestMatches(pinned.endpoint, snapshot, origin)) throw new Error('request scope changed while snapshotting');
  return snapshot;
}

/** Match an app request against one declared endpoint. */
export function clientEndpointAllowsRequest(endpoint, input, method = 'GET') {
  if (!record(endpoint) || !validEndpoint(endpoint) || Object.hasOwn(endpoint, 'browser-action') || Object.hasOwn(endpoint, 'transport')) return false;
  const payload = { input, init: { method } };
  const request = endpointRequest(payload, endpoint.origin);
  return request !== null
    && request.origin === endpoint.origin
    && !request.hasCredentials
    && endpointRequestMatches(endpoint, payload, endpoint.origin);
}

function operationSelector(operation) {
  return JSON.stringify([operation.capability, operation.service, operation.operation]);
}

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (record(value)) {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

function freezeClone(value) {
  if (Array.isArray(value)) return Object.freeze(value.map(freezeClone));
  if (record(value)) {
    return Object.freeze(Object.fromEntries(
      Object.entries(value).map(([key, child]) => [key, freezeClone(child)])
    ));
  }
  return value;
}

function serviceAdapter(serviceAdapters, service, operation) {
  if (!record(serviceAdapters) || !Object.hasOwn(serviceAdapters, service)) return undefined;
  const operations = serviceAdapters[service];
  if (!record(operations) || !Object.hasOwn(operations, operation)) return undefined;
  return operations[operation];
}

/**
 * Validate a JSON-compatible kotoba.app.client-runtime.v1 descriptor.
 * appOrigins defaults to the current page/Worker origin; static builders can
 * pass every configured app origin. Release/signature and bundle-byte checks
 * remain the verifier adapter's responsibility, matching kotoba.protocol.install.
 */
export function clientRuntimeProblems(runtime, requestedCapabilities = [], appOrigins = globalThis.location?.origin) {
  const problems = [];
  const applicationOrigins = new Set((Array.isArray(appOrigins) ? appOrigins : [appOrigins])
    .filter((origin) => typeof origin === 'string' && origin.length > 0));
  if (!record(runtime)) return [{ field: 'client-runtime', error: 'invalid-shape' }];
  const requiredKeys = ['entry', 'local-state', 'operations', 'profile', 'schema', 'target'];
  if (Object.keys(runtime).some((key) => !RUNTIME_KEYS.includes(key))
      || requiredKeys.some((key) => !Object.hasOwn(runtime, key))) {
    problems.push({ field: 'client-runtime', error: 'invalid-keys' });
  }
  if (runtime.schema !== 'kotoba.app.client-runtime.v1') {
    problems.push({ field: 'schema', error: 'invalid-schema' });
  }
  if (runtime.target !== 'browser') problems.push({ field: 'target', error: 'invalid-target' });
  if (!['trusted-page-v1', 'restricted-wasm-v1'].includes(runtime.profile)) {
    problems.push({ field: 'profile', error: 'invalid-profile' });
  }
  if (!validEntry(runtime.entry)) problems.push({ field: 'entry', error: 'invalid-entry' });

  if (Object.hasOwn(runtime, 'workers')) {
    if (!Array.isArray(runtime.workers)) {
      problems.push({ field: 'workers', error: 'invalid-workers' });
    } else {
      const ids = new Set();
      for (const worker of runtime.workers) {
        if (!exactKeys(worker, ['entry', 'id', 'protocol'])
            || !validName(worker.id) || !validEntry(worker.entry) || !validName(worker.protocol)) {
          problems.push({ field: 'workers', error: 'invalid-worker' });
          continue;
        }
        if (ids.has(worker.id)) problems.push({ field: 'workers', error: 'duplicate-worker-id' });
        ids.add(worker.id);
      }
    }
  }

  const state = runtime['local-state'];
  if (!exactKeys(state, ['adapter', 'schema', 'version'])
      || !['memory', 'indexeddb', 'opfs', 'localstorage'].includes(state.adapter)
      || !validName(state.schema)
      || !Number.isSafeInteger(state.version)
      || state.version < 1) {
    problems.push({ field: 'local-state', error: 'invalid-local-state' });
  }

  if (!Array.isArray(runtime.operations)) {
    problems.push({ field: 'operations', error: 'invalid-operations' });
  } else {
    const requested = new Set(Array.isArray(requestedCapabilities) ? requestedCapabilities : []);
    const seen = new Set();
    for (const operation of runtime.operations) {
      const hasValidOperationKeys = record(operation)
        && OPERATION_REQUIRED_KEYS.every((key) => Object.hasOwn(operation, key))
        && Object.keys(operation).every((key) => OPERATION_KEYS.includes(key));
      if (!hasValidOperationKeys
          || !validName(operation.capability)
          || !validName(operation.service)
          || !validName(operation.operation)
          || !Array.isArray(operation['data-categories'])
          || operation['data-categories'].length > 32
          || !operation['data-categories'].every(validName)
          || new Set(operation['data-categories']).size !== operation['data-categories'].length
          || !validEndpoint(operation.endpoint)
          || (Object.hasOwn(operation, 'artifact') && !validArtifactDeclaration(operation.artifact))
          || (Object.hasOwn(operation, 'redirect-origins')
            && (!Array.isArray(operation['redirect-origins'])
              || operation['redirect-origins'].length > 16
              || !operation['redirect-origins'].every(validRedirectOrigin)
              || new Set(operation['redirect-origins']).size !== operation['redirect-origins'].length))
          || operation.consent !== 'each-operation') {
        problems.push({ field: 'operations', error: 'invalid-operation' });
        continue;
      }
      const selector = operationSelector(operation);
      if (seen.has(selector)) problems.push({ field: 'operations', error: 'duplicate-operation' });
      seen.add(selector);
      if (!requested.has(operation.capability)) {
        problems.push({ field: 'operations', error: 'capability-not-requested', selector });
      }
      if (operation.endpoint !== 'user-selected'
          && record(operation.endpoint)
          && applicationOrigins.has(operation.endpoint.origin)) {
        problems.push({ field: 'operations', error: 'service-origin-is-app-origin', selector });
      }
      for (const redirectOrigin of operation['redirect-origins'] ?? []) {
        if ([...applicationOrigins].some((origin) => redirectOriginAllows(redirectOrigin, origin))) {
          problems.push({ field: 'operations', error: 'redirect-origin-is-app-origin', selector });
        }
      }
      if ((operation['redirect-origins'] ?? []).length > 0
          && !endpointSupportsDeclaredRedirects(operation.endpoint)) {
        problems.push({ field: 'operations', error: 'redirects-require-read-only-fixed-query', selector });
      }
      if ((Object.hasOwn(operation.endpoint, 'browser-action') || operation.endpoint.transport === 'libp2p' || operation.endpoint.transport === 'nearby')
          && (Object.hasOwn(operation, 'artifact') || Object.hasOwn(operation, 'redirect-origins'))) {
        problems.push({ field: 'operations', error: 'browser-operation-has-http-options', selector });
      }
      if (Object.hasOwn(operation, 'artifact') && !endpointSupportsDeclaredRedirects(operation.endpoint)) {
        problems.push({ field: 'operations', error: 'artifact-requires-read-only-fixed-query', selector });
      }
      if (operation.capability === 'net/http-post') {
        problems.push({ field: 'operations', error: 'generic-network-capability', selector });
      }
    }
  }
  return problems;
}

function validInferenceRequestId(value) {
  return typeof value === 'string' && value.length > 0 && value.length <= 128;
}

function inferenceHistoryProblems(history) {
  if (!Array.isArray(history) || history.length > 8) return ['invalid-history'];
  let size = 0;
  for (const message of history) {
    if (!exactKeys(message, ['content', 'role'])
        || !['assistant', 'user'].includes(message.role)
        || typeof message.content !== 'string'
        || message.content.length > 12000) return ['invalid-history-message'];
    size += message.content.length;
    if (size > 12000) return ['history-too-large'];
  }
  return [];
}

/** Validate a host-to-Worker kotoba.inference.v1 request before dispatch. */
export function clientInferenceRequestProblems(message) {
  if (!record(message)) return [{ field: 'message', error: 'invalid-shape' }];
  const problems = [];
  const type = message.type;
  if (message.protocol !== CLIENT_INFERENCE_PROTOCOL) {
    problems.push({ field: 'protocol', error: 'invalid-protocol' });
  }
  if (!Object.hasOwn(INFERENCE_REQUEST_KEYS, type)) {
    problems.push({ field: 'type', error: 'unsupported-type' });
    return problems;
  }
  const typeKeys = INFERENCE_REQUEST_KEYS[type];
  const allowedKeys = ['protocol', 'requestId', 'type', ...typeKeys];
  if (Object.keys(message).some((key) => !allowedKeys.includes(key))) {
    problems.push({ field: 'message', error: 'unknown-fields' });
  }
  if (!validInferenceRequestId(message.requestId)) {
    problems.push({ field: 'requestId', error: 'invalid-request-id' });
  }
  if (type === 'load') {
    if (!validName(message.modelId)) problems.push({ field: 'modelId', error: 'invalid-model-id' });
    if (Object.hasOwn(message, 'history')) {
      problems.push(...inferenceHistoryProblems(message.history).map((error) => ({ field: 'history', error })));
    }
    if (Object.hasOwn(message, 'approvedOperations')
        && (!Array.isArray(message.approvedOperations)
          || message.approvedOperations.length > 64
          || !message.approvedOperations.every(record))) {
      problems.push({ field: 'approvedOperations', error: 'invalid-approved-operations' });
    }
  }
  if (type === 'generate'
      && (typeof message.prompt !== 'string' || message.prompt.length === 0 || message.prompt.length > 8000)) {
    problems.push({ field: 'prompt', error: 'invalid-prompt' });
  }
  return problems;
}

/** Validate a Worker-to-host kotoba.inference.v1 event before UI handling. */
export function clientInferenceEventProblems(message) {
  if (!record(message)) return [{ field: 'message', error: 'invalid-shape' }];
  const problems = [];
  const type = message.type;
  const eventKeys = {
    status: ['message'],
    ready: [],
    delta: ['text'],
    done: [],
    error: ['message'],
  };
  if (message.protocol !== CLIENT_INFERENCE_PROTOCOL) {
    problems.push({ field: 'protocol', error: 'invalid-protocol' });
  }
  if (!Object.hasOwn(eventKeys, type)) {
    problems.push({ field: 'type', error: 'unsupported-type' });
    return problems;
  }
  const eventFields = eventKeys[type];
  const allowedKeys = ['protocol', 'requestId', 'type', ...eventFields];
  if (Object.keys(message).some((key) => !allowedKeys.includes(key))) {
    problems.push({ field: 'message', error: 'unknown-fields' });
  }
  if (!validInferenceRequestId(message.requestId)) {
    problems.push({ field: 'requestId', error: 'invalid-request-id' });
  }
  if (type === 'delta'
      && (typeof message.text !== 'string' || message.text.length === 0 || message.text.length > 65536)) {
    problems.push({ field: 'text', error: 'invalid-delta' });
  }
  if (['status', 'error'].includes(type)
      && (typeof message.message !== 'string' || message.message.length === 0 || message.message.length > 1024)) {
    problems.push({ field: 'message', error: 'invalid-message' });
  }
  return problems;
}

/** Create an immutable, schema-checked kotoba.inference.v1 request. */
export function createClientInferenceRequest(type, requestId, fields = {}) {
  if (!record(fields)) throw new TypeError('inference request fields must be an object');
  const message = Object.freeze({ ...fields, protocol: CLIENT_INFERENCE_PROTOCOL, type, requestId });
  const problems = clientInferenceRequestProblems(message);
  if (problems.length) {
    throw new TypeError(`invalid inference request: ${problems.map(({ field, error }) => `${field}:${error}`).join(', ')}`);
  }
  return message;
}

/** Create an immutable, schema-checked kotoba.inference.v1 event. */
export function createClientInferenceEvent(type, requestId, fields = {}) {
  if (!record(fields)) throw new TypeError('inference event fields must be an object');
  const message = Object.freeze({ ...fields, protocol: CLIENT_INFERENCE_PROTOCOL, type, requestId });
  const problems = clientInferenceEventProblems(message);
  if (problems.length) {
    throw new TypeError(`invalid inference event: ${problems.map(({ field, error }) => `${field}:${error}`).join(', ')}`);
  }
  return message;
}

const OFFLINE_CONTENT_POLICY = Object.freeze([
  "default-src 'self'",
  "base-uri 'self'",
  "form-action 'self'",
  "connect-src 'none'",
  "img-src 'self' data: blob:",
  "media-src 'self' blob:",
  "font-src 'self' data:",
  "frame-src 'none'",
  "object-src 'none'",
  "worker-src 'self' blob:",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval' 'wasm-unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
].join('; '));

/**
 * Add a per-document policy before launching a local-only app session.
 * Static app headers remain authoritative and the extra policy can only
 * restrict their allowed sources; it cannot grant a new network destination.
 */
export function applyOfflineClientPolicy(documentObject = globalThis.document) {
  if (!documentObject?.head || typeof documentObject.createElement !== 'function') {
    throw new Error('offline client policy requires a document head');
  }
  const existing = documentObject.querySelector?.('meta[data-kotoba-offline-policy="v1"]');
  if (existing) return existing;
  const policy = documentObject.createElement('meta');
  policy.httpEquiv = 'Content-Security-Policy';
  policy.content = OFFLINE_CONTENT_POLICY;
  policy.setAttribute('data-kotoba-offline-policy', 'v1');
  documentObject.head.append(policy);
  return policy;
}

/**
 * Render a static-host connect-src directive from declared operation and
 * redirect origins. Additional sources must already be declared by an
 * operation; this helper cannot widen the app's network boundary.
 */
export function clientRuntimeConnectSrc(runtime, requestedCapabilities = [], additionalSources = [], appOrigins = globalThis.location?.origin) {
  // Validate and read one frozen copy, so a getter cannot answer differently.
  const pinned = freezeClone(runtime);
  const problems = clientRuntimeProblems(pinned, requestedCapabilities, appOrigins);
  if (problems.length) {
    throw new Error(`invalid client runtime descriptor: ${problems.map(({field, error}) => `${field}:${error}`).join(', ')}`);
  }
  const origins = new Set();
  for (const operation of pinned.operations) {
    // A browser-action operation causes no fetch from the page.
    if (Object.hasOwn(operation.endpoint, 'browser-action') || operation.endpoint.transport === 'libp2p' || operation.endpoint.transport === 'nearby') continue;
    origins.add(operation.endpoint.origin);
    for (const redirectOrigin of operation['redirect-origins'] ?? []) origins.add(redirectOrigin);
  }
  for (const source of additionalSources) {
    if (!validRedirectOrigin(source) || !origins.has(source)) {
      throw new Error('additional connect-src entries must be declared by a client operation');
    }
  }
  return `connect-src ${origins.size ? [...origins].sort().join(' ') : "'none'"}`;
}

/**
 * Apply the same exact intersection as kotoba.protocol.install:
 * signed operation declaration intersected with local host eligibility and
 * host-supported
 * [capability, service, operation] selectors.
 */
export function effectiveClientOperations(runtime, {
  requestedCapabilities = [],
  approvedOperations = [],
  hostSupportedOperations = [],
} = {}) {
  if (clientRuntimeProblems(runtime, requestedCapabilities).length) return [];
  const approved = new Set(approvedOperations.filter(record).map(canonical));
  const supported = new Set(hostSupportedOperations
    .filter((selector) => Array.isArray(selector) && selector.length === 3
      && selector.every((part) => typeof part === 'string'))
    .map((selector) => JSON.stringify(selector)));
  return runtime.operations.filter((operation) => (
    approved.has(canonical(operation))
    && supported.has(operationSelector(operation))
  ));
}

const consentHosts = new WeakMap();
const verifiedArtifacts = new WeakSet();

function plainData(value, depth = 0, ancestors = new Set()) {
  if (depth > 16) return false;
  if (value === null || typeof value === 'boolean' || typeof value === 'string') return true;
  if (typeof value === 'number') return Number.isFinite(value);
  if (typeof value !== 'object' || ancestors.has(value)) return false;
  if (!Array.isArray(value) && ![Object.prototype, null].includes(Object.getPrototypeOf(value))) return false;
  const descriptors = Object.getOwnPropertyDescriptors(value);
  if (Object.values(descriptors).some((descriptor) => descriptor.get || descriptor.set)) return false;
  const next = new Set(ancestors); next.add(value);
  return Object.values(value).every((child) => plainData(child, depth + 1, next));
}

/** Trusted shell only. Guests must be isolated from this document and handle.
 * A callback, synthetic DOM event, cached boolean or browser permission cannot
 * grant consent. One direct trusted click resolves one displayed invocation.
 * Allow counts only after the dialog has been showing for ALLOW_ARM_MS and only
 * for a press (pointerdown, or Enter/Space keydown) that starts after that: a
 * click aimed at whatever was under the pointer when the dialog opened, or a
 * double click, does not approve (KOTOBA-159 finding 3).
 * No approval token or approval store is exposed to application code.
 */
const ALLOW_ARM_MS = 600;

export function createClientConsentHost({ document: doc = globalThis.document } = {}) {
  if (doc !== globalThis.document || !doc?.body || typeof doc.createElement !== 'function') {
    throw new TypeError('consent requires the trusted host document');
  }
  const dialog = doc.createElement('dialog');
  dialog.className = 'kotoba-client-consent';
  dialog.setAttribute('aria-label', 'External operation approval');
  const title = doc.createElement('h2'); title.textContent = 'Allow this operation once?';
  const scope = doc.createElement('pre'); scope.className = 'kotoba-client-consent-scope';
  const note = doc.createElement('p');
  note.textContent = 'This choice applies only to the displayed operation. Denying sends no request. Browser permissions do not approve subsequent operations.';
  const deny = doc.createElement('button'); deny.type = 'button'; deny.textContent = 'Deny';
  const allow = doc.createElement('button'); allow.type = 'button'; allow.textContent = 'Allow once';
  allow.disabled = true;
  dialog.append(title, scope, note, deny, allow); doc.body.append(dialog);
  let pending = null;
  let pendingAbort = null;
  let destroyed = false;
  // dialog.close() queues an asynchronous `close` event. Count the closes this host issues so
  // that a late event from an already-settled request is not mistaken for a close of the next one.
  let ownCloses = 0;
  // armedAt: when Allow starts to count for the showing request; pressed: a trusted press on
  // Allow began after that. Both reset on every show and every settlement.
  const clock = () => doc.defaultView.performance.now();
  let armedAt = Infinity;
  let pressed = false;
  let armTimer = null;
  function disarm() {
    armedAt = Infinity; pressed = false;
    if (armTimer !== null) { clearTimeout(armTimer); armTimer = null; }
    allow.disabled = true;
  }
  function finish(approved) {
    if (!pending) return;
    const resolve = pending; pending = null;
    if (pendingAbort) { pendingAbort(); pendingAbort = null; }
    disarm();
    if (dialog.open) { ownCloses += 1; dialog.close(); }
    resolve(approved);
  }
  const press = (event) => { pressed = event.isTrusted === true && dialog.open && clock() >= armedAt; };
  allow.addEventListener('pointerdown', press);
  allow.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') press(event); });
  allow.addEventListener('click', (event) => {
    const fresh = pressed; pressed = false;
    if (event.isTrusted === true && event.currentTarget === allow
        && event instanceof doc.defaultView.MouseEvent && dialog.open
        && fresh && clock() >= armedAt) finish(true);
  });
  deny.addEventListener('click', () => finish(false));
  dialog.addEventListener('cancel', (event) => { event.preventDefault(); finish(false); });
  dialog.addEventListener('close', () => { if (ownCloses > 0) { ownCloses -= 1; return; } finish(false); });
  const handle = Object.freeze({ destroy() { destroyed = true; finish(false); dialog.remove(); } });
  consentHosts.set(handle, async (details, signal) => {
    if (signal?.aborted) return false;
    if (destroyed || pending || !dialog.isConnected) throw new Error('trusted consent UI is unavailable or busy');
    scope.textContent = [
      `Service: ${details.service}`, `Operation: ${details.operation}`,
      `Capability: ${details.capability}`, `Endpoint: ${details.endpointOrigin}`,
      ...(details.nearbyEndpoint ? [
        `Nearby device: ${details.nearbyEndpoint.action} over ${details.nearbyBearer}`,
        `Peer: ${details.nearbyPeer ?? '(none: not a specific device)'}`,
        `Request budget: ${details.nearbyEndpoint['max-request-bytes']} bytes`,
        `Response budget: ${details.nearbyEndpoint['max-response-bytes']} bytes`,
        `Deadline: ${details.nearbyEndpoint['timeout-ms']} ms`,
      ] : []),
      `Action: ${details.nearbyEndpoint?.action ?? details.peerEndpoint?.action ?? details.browserAction ?? `${details.endpointMethod} ${details.endpointPath}${details.endpointSearch}`}`,
      ...(details.peerEndpoint ? [
        `PeerID: ${details.peerEndpoint['peer-id']}`,
        `Addresses: ${details.peerEndpoint.addresses.join(', ')}`,
        `Protocol: ${details.peerEndpoint.protocol}`,
        `Request budget: ${details.peerEndpoint['max-request-bytes']} bytes`,
        `Response budget: ${details.peerEndpoint['max-response-bytes']} bytes`,
        `Deadline: ${details.peerEndpoint['timeout-ms']} ms`,
        ...(details.peerEndpoint.scope ? [`Transfer scope: ${canonical(details.peerEndpoint.scope)}`] : []),
      ] : []),
      `Data categories: ${details.dataCategories.join(', ') || '(none)'}`,
      `Delivery redirects: ${details.redirectOrigins.join(', ') || '(none)'}`,
      ...(details.artifact ? [
        `Artifact revision: ${details.artifact.revision}`,
        `Artifact SHA-256: ${details.artifact.sha256} (a mismatch is discarded)`,
        `Artifact byte budget: ${details.artifact['max-bytes']} bytes`,
        `Artifact delivery: ${details.artifact.delivery === 'host-stream' ? 'streamed to this app on the device' : 'held in page memory'}`,
      ] : []),
    ].join('\n');
    return new Promise((resolve, reject) => {
      pending = resolve;
      try {
        if (signal) {
          const onAbort = () => finish(false);
          signal.addEventListener('abort', onAbort, { once: true });
          pendingAbort = () => signal.removeEventListener('abort', onAbort);
          if (signal.aborted) { finish(false); return; }
        }
        disarm();
        dialog.showModal(); deny.focus();
        armedAt = clock() + ALLOW_ARM_MS;
        armTimer = setTimeout(() => { armTimer = null; if (pending === resolve) allow.disabled = false; }, ALLOW_ARM_MS);
      }
      catch (error) { pending = null; if (pendingAbort) { pendingAbort(); pendingAbort = null; } disarm(); reject(error); }
    });
  });
  return handle;
}

// In-memory artifacts are verified as one byte snapshot and stay within 512 MiB. A
// `delivery: "host-stream"` artifact is never held in page memory: the broker streams it to a
// host-supported sink with an incremental SHA-256 and the same byte budget, up to 64 GiB.
const ARTIFACT_MEMORY_MAX_BYTES = 536870912;
const ARTIFACT_STREAM_MAX_BYTES = 68719476736;
function hostStreamArtifact(value) { return record(value) && value.delivery === 'host-stream'; }
function validArtifactDeclaration(value) {
  const streamed = record(value) && Object.hasOwn(value, 'delivery');
  return exactKeys(value, streamed ? ['revision', 'sha256', 'max-bytes', 'delivery'] : ['revision', 'sha256', 'max-bytes'])
    && (!streamed || value.delivery === 'host-stream')
    && typeof value.revision === 'string' && /^[0-9a-f]{40}$/.test(value.revision)
    && typeof value.sha256 === 'string' && /^[0-9a-f]{64}$/.test(value.sha256)
    && Number.isSafeInteger(value['max-bytes']) && value['max-bytes'] > 0
    && value['max-bytes'] <= (streamed ? ARTIFACT_STREAM_MAX_BYTES : ARTIFACT_MEMORY_MAX_BYTES);
}

const hexBytes = (bytes) => Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
const decodeHex = (text) => Uint8Array.from(text.match(/../g) ?? [], (byte) => parseInt(byte, 16));
const sha256 = async (bytes) => hexBytes(new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes)));

/** Immutable Blob, pinned revision, independent digest verification. No execute. */
export async function verifyClientArtifact(bytes, declaration) {
  if (!validArtifactDeclaration(declaration) || hostStreamArtifact(declaration) || !(bytes instanceof Uint8Array)) throw new TypeError('artifact requires bytes, immutable revision and expected digest');
  declaration = freezeClone(declaration);
  const snapshot = new Uint8Array(bytes);
  if (snapshot.byteLength > declaration['max-bytes']) throw new Error('artifact exceeds declared byte budget');
  const digest = await sha256(snapshot);
  if (digest !== declaration.sha256) throw new Error('artifact digest mismatch; execution refused');
  const result = Object.freeze({ blob: new Blob([snapshot]), sha256: digest, revision: declaration.revision, verified: true });
  verifiedArtifacts.add(result);
  return result;
}

// CSP has no directive for WebRTC, so `connect-src 'none'` does not stop a guest from sending bytes to any host
// through ICE servers (a TURN username reaches the server, KOTOBA-159 R6). This runs before any guest script and
// removes the constructors from the guest realm. A nested about:blank frame of an opaque-origin sandbox is
// cross-origin and workers do not expose them (Chromium 156), so the guest cannot recover a fresh copy. Host-realm
// peer handlers are not affected. This is defense in depth for one browser, not a CSP guarantee.
const GUEST_PREAMBLE = '<script>for(const n of["RTCPeerConnection","webkitRTCPeerConnection"])try{Object.defineProperty(window,n,{value:undefined,writable:false,configurable:false})}catch{}</script>';

/** Isolated, self-contained HTML app only. The trusted host must first admit
 * its publisher and descriptor. Host-issued eligibility and adapters never
 * cross the port. CSP prevents the guest from issuing service requests itself.
 */
export async function mountRestrictedClientApp({ artifact, container, broker }) {
  if (!verifiedArtifacts.has(artifact) || !(container instanceof globalThis.HTMLElement)
      || typeof broker?.invoke !== 'function') throw new TypeError('verified app artifact and trusted host broker required');
  const html = await artifact.blob.text();
  if (!container.isConnected || container.ownerDocument !== globalThis.document || container.getRootNode() !== document || typeof MutationObserver !== 'function')
    throw new TypeError('connected host container and DOM observation required');
  if (html.length > 8388608) throw new Error('app HTML exceeds byte budget');
  const frame = document.createElement('iframe');
  frame.title = 'Restricted Kotoba application';
  frame.sandbox = 'allow-scripts';
  frame.referrerPolicy = 'no-referrer';
  frame.srcdoc = '<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; connect-src \'none\'; script-src \'unsafe-inline\' blob: \'wasm-unsafe-eval\'; style-src \'unsafe-inline\'; img-src data: blob:; media-src blob:; worker-src blob:; frame-src \'none\'; object-src \'none\'; form-action \'none\'; base-uri \'none\'">' + GUEST_PREAMBLE + html;
  let closed = false;
  let loaded = false;
  const lifetime = new AbortController();
  const channel = new MessageChannel();
  const observer = new MutationObserver((records) => {
    if (!frame.isConnected || frame.parentNode !== container || records.some(({ removedNodes }) =>
      Array.from(removedNodes).some((node) => node === frame || node.contains?.(frame)))) close();
  });
  function close() {
    if (closed) return;
    closed = true; observer.disconnect(); lifetime.abort(); channel.port1.close(); frame.remove();
  }
  observer.observe(document, { childList: true, subtree: true });
  channel.port1.onmessage = async ({ data }) => {
    if (closed || !plainData(data) || !exactKeys(data, ['protocol', 'id', 'selector', 'payload'])
        || data.protocol !== 'kotoba.client.operation.v1' || !validName(data.id)) return;
    try {
      const result = await broker.invoke(data.selector, data.payload, { signal: lifetime.signal });
      if (closed) return;
      if (result instanceof Response) {
        // Bridge bounded service data, never the host's transport/credentials.
        const bytes = result.body ? await boundedBytes(result.body, 1048576, 30000, lifetime.signal) : new Uint8Array();
        const content = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
        if (!closed) channel.port1.postMessage({ id: data.id, ok: true, status: result.status, content });
      } else if (!closed) channel.port1.postMessage({ id: data.id, ok: true, result });
    } catch (error) { if (!closed) channel.port1.postMessage({ id: data.id, ok: false, error: String(error.message).slice(0, 1024) }); }
  };
  frame.addEventListener('load', () => {
    if (closed) return;
    // A later completed navigation replaces the admitted guest. Invalidate its
    // channel and pending work; load does not detect navigation at its start.
    if (loaded) { close(); return; }
    loaded = true;
    frame.contentWindow.postMessage({ protocol: 'kotoba.client.host.v1' }, '*', [channel.port2]);
  });
  container.append(frame);
  return Object.freeze({ close });
}

/** Verify exact descriptor bytes against a host-pinned Ed25519 publisher key.
 * The pinned key/revision/digest are trusted installer inputs, never guest
 * declarations. The signature is over the exact bytes, without re-encoding.
 */
export async function verifySignedClientDescriptor({ bytes, signature, publicKey, pinnedPublicKey, revision, digest, requestedCapabilities = [], appOrigins = globalThis.location?.origin }) {
  if (!(bytes instanceof Uint8Array) || bytes.byteLength > 262144
      || !/^[0-9a-f]{64}$/.test(publicKey) || publicKey !== pinnedPublicKey
      || !/^[0-9a-f]{128}$/.test(signature)) throw new TypeError('descriptor publisher pin or signature is invalid');
  const artifact = await verifyClientArtifact(bytes, { revision, sha256: digest, 'max-bytes': 262144 });
  const snapshot = new Uint8Array(await artifact.blob.arrayBuffer());
  const key = await globalThis.crypto.subtle.importKey('raw', decodeHex(publicKey), 'Ed25519', false, ['verify']);
  if (!await globalThis.crypto.subtle.verify('Ed25519', key, decodeHex(signature), snapshot)) throw new Error('descriptor signature mismatch');
  const runtime = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(snapshot));
  const problems = clientRuntimeProblems(runtime, requestedCapabilities, appOrigins);
  if (problems.length) throw new Error(`invalid signed descriptor: ${JSON.stringify(problems)}`);
  return Object.freeze({ runtime: freezeClone(runtime), revision, digest, publicKey });
}

// A response that will not be read is cancelled, so its connection and buffered data are released (KOTOBA-159 R2).
function discardBody(response) {
  try { response?.body?.cancel().catch(() => {}); } catch { /* locked or already consumed */ }
}

// FIPS 180-4 SHA-256 with incremental update, for streamed artifacts (WebCrypto has no streaming digest).
const SHA256_K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]);
export function createSha256() {
  const h = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
  const w = new Uint32Array(64); const block = new Uint8Array(64); let used = 0; let total = 0; let done = false;
  function compress(bytes, offset) {
    for (let i = 0; i < 16; i++) { const j = offset + i * 4; w[i] = (bytes[j] << 24) | (bytes[j + 1] << 16) | (bytes[j + 2] << 8) | bytes[j + 3]; }
    for (let i = 16; i < 64; i++) {
      const a = w[i - 15], b = w[i - 2];
      const s0 = ((a >>> 7) | (a << 25)) ^ ((a >>> 18) | (a << 14)) ^ (a >>> 3);
      const s1 = ((b >>> 17) | (b << 15)) ^ ((b >>> 19) | (b << 13)) ^ (b >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) | 0;
    }
    let [a, b, c, d, e, f, g, k] = h;
    for (let i = 0; i < 64; i++) {
      const S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
      const t1 = (k + S1 + ((e & f) ^ (~e & g)) + SHA256_K[i] + w[i]) | 0;
      const S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
      const t2 = (S0 + ((a & b) ^ (a & c) ^ (b & c))) | 0;
      k = g; g = f; f = e; e = (d + t1) | 0; d = c; c = b; b = a; a = (t1 + t2) | 0;
    }
    h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e; h[5] += f; h[6] += g; h[7] += k;
  }
  return Object.freeze({
    update(bytes) {
      if (done || !(bytes instanceof Uint8Array)) throw new TypeError('sha256 update after digest or with non-bytes');
      total += bytes.length; let i = 0;
      if (used) { const take = Math.min(64 - used, bytes.length); block.set(bytes.subarray(0, take), used); used += take; i = take; if (used === 64) { compress(block, 0); used = 0; } }
      for (; i + 64 <= bytes.length; i += 64) compress(bytes, i);
      if (i < bytes.length) { block.set(bytes.subarray(i), 0); used = bytes.length - i; }
    },
    hex() {
      if (done) throw new TypeError('sha256 digest already taken');
      done = true; const bits = total * 8;
      block[used++] = 0x80; if (used > 56) { block.fill(0, used); compress(block, 0); used = 0; }
      block.fill(0, used, 56);
      const high = Math.floor(bits / 0x100000000), low = bits >>> 0;
      block[56] = high >>> 24; block[57] = high >>> 16; block[58] = high >>> 8; block[59] = high;
      block[60] = low >>> 24; block[61] = low >>> 16; block[62] = low >>> 8; block[63] = low;
      compress(block, 0);
      return Array.from(h, (x) => (x >>> 0).toString(16).padStart(8, '0')).join('');
    },
  });
}

const ARTIFACT_STREAM_IDLE_MS = 60000;
const plainSinkResult = (value) => (value === undefined ? null : (plainData(value) ? freezeClone(value) : null));

/** Stream a declared host-stream artifact into a host sink. The sink receives byte copies; it is
 * closed only after the whole body matches the declared SHA-256 within the byte budget, and is
 * aborted on any mismatch, overrun, idle timeout, cancellation or read error. */
async function streamArtifact(response, declaration, sinkFactory, selector, signal) {
  if (!response.body) throw new Error('artifact response has no readable body');
  const sink = await sinkFactory(Object.freeze({ selector, artifact: freezeClone(declaration) }));
  if (!sink || typeof sink.write !== 'function' || typeof sink.close !== 'function' || typeof sink.abort !== 'function') {
    discardBody(response); throw new TypeError('artifact sink must provide write, close and abort');
  }
  const reader = response.body.getReader();
  const hash = createSha256(); let bytes = 0; let finished = false;
  const fail = async (reason) => {
    if (finished) return; finished = true;
    try { await reader.cancel(); } catch { /* already closed */ }
    try { await sink.abort(reason); } catch { /* the host cleans up on its own failure */ }
  };
  let timer; let onAbort;
  const stalled = () => new Promise((_, reject) => { clearTimeout(timer); timer = setTimeout(() => reject(new Error('artifact stream idle deadline exceeded')), ARTIFACT_STREAM_IDLE_MS); });
  const cancelled = signal && new Promise((_, reject) => {
    onAbort = () => reject(new Error('client operation cancelled'));
    signal.addEventListener('abort', onAbort, { once: true });
    if (signal.aborted) onAbort();
  });
  try {
    while (true) {
      const { done, value } = await Promise.race(cancelled ? [reader.read(), stalled(), cancelled] : [reader.read(), stalled()]);
      if (done) break;
      bytes += value.byteLength;
      if (bytes > declaration['max-bytes']) { await fail('byte-budget'); throw new Error('artifact exceeds declared byte budget'); }
      const copy = new Uint8Array(value);
      hash.update(copy);
      await sink.write(copy);
    }
    const sha256 = hash.hex();
    if (sha256 !== declaration.sha256) { await fail('digest-mismatch'); throw new Error('artifact digest mismatch; execution refused'); }
    finished = true;
    const closed = await sink.close(Object.freeze({ sha256, bytes, revision: declaration.revision }));
    return Object.freeze({ verified: true, sha256, bytes, revision: declaration.revision, sink: plainSinkResult(closed) });
  } catch (error) {
    await fail(String(error?.message ?? 'artifact stream failed').slice(0, 120));
    throw error;
  } finally {
    clearTimeout(timer); signal?.removeEventListener('abort', onAbort);
  }
}

async function boundedArtifact(response, declaration) {
  if (!response.body) throw new Error('artifact response has no readable body');
  return verifyClientArtifact(await boundedBytes(response.body, declaration['max-bytes'], 120000), declaration);
}

async function boundedBytes(stream, maxBytes, deadlineMs, signal) {
  if (signal?.aborted) throw new Error('client operation cancelled');
  const reader = stream.getReader();
  const chunks = []; let size = 0;
  let timer, onAbort;
  const deadline = new Promise((resolve, reject) => { timer = setTimeout(() => reject(new Error('body snapshot deadline exceeded')), deadlineMs); });
  const cancelled = signal && new Promise((resolve, reject) => {
    onAbort = () => reject(new Error('client operation cancelled'));
    signal.addEventListener('abort', onAbort, { once: true });
    if (signal.aborted) onAbort();
  });
  try {
    while (true) {
      const { done, value } = await Promise.race(cancelled ? [reader.read(), deadline, cancelled] : [reader.read(), deadline]);
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) throw new Error('body exceeds declared byte budget');
      chunks.push(value);
    }
  } catch (error) { reader.cancel().catch(() => {}); throw error; }
  finally { clearTimeout(timer); if (onAbort) signal.removeEventListener('abort', onAbort); try { reader.releaseLock(); } catch { /* cancelled pending read */ } }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  return bytes;
}

/** Trusted host owns eligibility/handlers and exposes only bounded invoke to
 * its isolated guest. HTTP transport is the captured browser fetch, not an
 * app-supplied adapter. Changing a callback to return true cannot grant access.
 * The older approvedOperations name is an eligibility ceiling, never consent.
 */
export function createClientOperationBroker(options) {
  const { runtime, requestedCapabilities = [], approvedOperations = [], hostSupportedOperations = [], browserAdapters = {}, peerAdapters = {}, artifactSinks = {}, consentHost } = options;
  if (Object.hasOwn(options, 'confirmOperation') || Object.hasOwn(options, 'serviceAdapters')) throw new TypeError('caller-supplied confirmation and HTTP adapters are not authority');
  const confirm = consentHosts.get(consentHost);
  if (!confirm) throw new TypeError('a canonical trusted consent host is required');
  const descriptor = freezeClone(runtime);
  const problems = clientRuntimeProblems(descriptor, requestedCapabilities);
  if (problems.length) throw new TypeError(`invalid client runtime descriptor: ${JSON.stringify(problems)}`);
  const operations = effectiveClientOperations(descriptor, { requestedCapabilities, approvedOperations, hostSupportedOperations });
  const bySelector = new Map(operations.map((operation) => [operationSelector(operation), operation]));
  // Capture supported browser handlers before the guest runs. Reassigning the
  // caller's map during consent cannot change the operation that will execute.
  const handlers = new Map(operations.filter((op) => Object.hasOwn(op.endpoint, 'browser-action'))
    .map((op) => [operationSelector(op), serviceAdapter(browserAdapters, op.service, op.operation)]));
  const peerHandlers = new Map(operations.filter((op) => op.endpoint.transport === 'libp2p' || op.endpoint.transport === 'nearby')
    .map((op) => [operationSelector(op), serviceAdapter(peerAdapters, op.service, op.operation)]));
  // Host sinks for streamed artifacts, captured before any guest runs, like browser handlers.
  const sinks = new Map(operations.filter((op) => hostStreamArtifact(op.artifact))
    .map((op) => [operationSelector(op), serviceAdapter(artifactSinks, op.service, op.operation)]));
  const fetchRequest = globalThis.fetch.bind(globalThis);
  return Object.freeze({
    operations: Object.freeze(operations),
    async invoke(selector, payload, { signal } = {}) {
      if (signal !== undefined && !(signal instanceof AbortSignal)) throw new TypeError('invalid operation signal');
      if (signal?.aborted) throw new Error('client operation cancelled');
      const operation = bySelector.get(JSON.stringify([selector?.capability, selector?.service, selector?.operation]));
      if (!operation) throw new Error('client operation is not eligible and supported');
      const nearbyEndpoint = operation.endpoint.transport === 'nearby' ? operation.endpoint : null;
      // Both peer kinds run through the host adapter with the same budgets, deadline and abort signal.
      const peerEndpoint = operation.endpoint.transport === 'libp2p' || nearbyEndpoint ? operation.endpoint : null;
      const endpointOrigin = nearbyEndpoint ? 'nearby device (discovered locally)' : peerEndpoint ? `libp2p:${peerEndpoint['peer-id']}` : operation.endpoint.origin;
      if (endpointOrigin === globalThis.location?.origin) throw new Error('service endpoint must be distinct from the app origin');
      const browserAction = operation.endpoint['browser-action'];
      let approvedPayload; let request = null;
      if (peerEndpoint) {
        if (typeof peerHandlers.get(operationSelector(operation)) !== 'function') throw new Error('peer operation is not host-supported');
        if (!plainData(payload)) throw new TypeError('peer operation requires bounded plain data');
        const json = canonical(payload);
        if (typeof json !== 'string' || new TextEncoder().encode(json).length > peerEndpoint['max-request-bytes']) throw new Error('peer operation payload exceeds budget');
        approvedPayload = freezeClone(JSON.parse(json));
        if (nearbyEndpoint) {
          const problem = nearbyPayloadProblem(nearbyEndpoint, approvedPayload);
          if (problem) throw new TypeError(problem);
        }
      } else if (browserAction) {
        const handler = handlers.get(operationSelector(operation));
        if (typeof handler !== 'function') throw new Error('browser operation is not host-supported');
        // Browser API parameters must be bounded, plain JSON data. Functions,
        // streams, getters and mutable shared/transfer buffers are not a rail.
        if (!plainData(payload)) throw new TypeError('browser operation requires bounded plain data');
        const json = canonical(payload);
        if (typeof json !== 'string' || json.length > 65536) throw new Error('browser operation payload exceeds budget');
        approvedPayload = freezeClone(JSON.parse(json));
      } else {
        request = endpointRequest(payload, endpointOrigin);
        if (!request || request.hasCredentials || !endpointRequestMatches(operation.endpoint, payload, endpointOrigin)) throw new Error('request does not match declared service method/path/query');
        approvedPayload = await prepareClientOperationRequest(operation, payload, signal);
        request = endpointRequest(approvedPayload, endpointOrigin);
        if (!request || request.hasCredentials || !endpointRequestMatches(operation.endpoint, approvedPayload, endpointOrigin)) throw new Error('request scope changed while snapshotting');
      }
      if (hostStreamArtifact(operation.artifact) && typeof sinks.get(operationSelector(operation)) !== 'function') {
        throw new Error('artifact sink is not host-supported');
      }
      if (signal?.aborted) throw new Error('client operation cancelled');
      const allowed = await confirm(Object.freeze({
        capability: operation.capability, service: operation.service, operation: operation.operation,
        endpointOrigin, peerEndpoint: nearbyEndpoint ? null : peerEndpoint, browserAction, endpointMethod: request?.method ?? null,
        nearbyEndpoint, nearbyBearer: nearbyEndpoint ? approvedPayload.bearer : null, nearbyPeer: nearbyEndpoint ? (approvedPayload.peer ?? null) : null,
        endpointPath: request?.path ?? null, endpointSearch: request?.search ?? '',
        dataCategories: operation['data-categories'], redirectOrigins: Object.freeze([...(operation['redirect-origins'] ?? [])]),
        artifact: operation.artifact ? freezeClone(operation.artifact) : null,
      }), signal);
      if (signal?.aborted) throw new Error('client operation cancelled');
      if (allowed !== true) throw new Error('client operation was not approved');
      if (peerEndpoint) {
        const controller = new AbortController();
        let rejectCancelled;
        const cancelled = new Promise((_, reject) => { rejectCancelled = reject; });
        const abort = () => { controller.abort(); rejectCancelled(new Error('peer operation cancelled or timed out')); };
        signal?.addEventListener('abort', abort, { once: true });
        const timeout = setTimeout(abort, peerEndpoint['timeout-ms']);
        try {
          if (signal?.aborted) abort();
          const result = await Promise.race([
            Promise.resolve().then(() => {
              if (controller.signal.aborted) throw new Error('peer operation cancelled');
              return peerHandlers.get(operationSelector(operation))({ operation, payload: approvedPayload, signal: controller.signal });
            }), cancelled,
          ]);
          if (!plainData(result)) throw new Error('peer response must be bounded plain data');
          const json = canonical(result);
          if (typeof json !== 'string' || new TextEncoder().encode(json).length > peerEndpoint['max-response-bytes']) throw new Error('peer response exceeds budget');
          return freezeClone(JSON.parse(json));
        } finally {
          clearTimeout(timeout); signal?.removeEventListener('abort', abort);
        }
      }
      if (browserAction) return handlers.get(operationSelector(operation))({ operation, payload: approvedPayload });
      // No init: the approved Request already carries its signal, referrer policy and options.
      const result = await fetchRequest(approvedPayload.input);
      if (signal?.aborted) { discardBody(result); throw new Error('client operation cancelled'); }
      if (result.type === 'opaqueredirect' || (result.status >= 300 && result.status < 400) || !result.url) { discardBody(result); throw new Error('service response redirect could not be verified'); }
      const responseOrigin = new URL(result.url).origin;
      if (![endpointOrigin, ...(operation['redirect-origins'] ?? [])].some((origin) => redirectOriginAllows(origin, responseOrigin))) { discardBody(result); throw new Error('service response redirect origin is not declared'); }
      if (operation.artifact) {
        if (!result.ok) { discardBody(result); throw new Error('artifact download failed'); }
        if (hostStreamArtifact(operation.artifact)) {
          return streamArtifact(result, operation.artifact, sinks.get(operationSelector(operation)), Object.freeze({ capability: operation.capability, service: operation.service, operation: operation.operation }), signal);
        }
        return boundedArtifact(result, operation.artifact);
      }
      return result;
    },
  });
}
