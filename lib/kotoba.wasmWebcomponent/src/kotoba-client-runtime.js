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

function validEndpoint(value) {
  return (exactKeys(value, ['origin', 'browser-action'])
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
        : request.path.startsWith(route['path-prefix']))
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

async function snapshotOperationPayload(payload, operation, endpointOrigin, request) {
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
  const init = record(payload.init) ? { ...payload.init } : {};
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
  // Request.clone() alone does not freeze a caller-owned ReadableStream.
  // Materialize a bounded body before showing consent; a later stream write
  // cannot change what the user is being asked to send.
  const body = captured.body ? await boundedBytes(captured.body, 16777216, 5000) : null;
  const requestSnapshot = body === null ? captured : new Request(captured, {
    body, credentials: 'omit', referrerPolicy: 'no-referrer', redirect,
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
export async function prepareClientOperationRequest(operation, payload) {
  if (!validEndpoint(operation?.endpoint) || Object.hasOwn(operation.endpoint, 'browser-action')) throw new TypeError('HTTP endpoint declaration required');
  const pinned = freezeClone(operation), origin = pinned.endpoint.origin;
  if (origin === globalThis.location?.origin) throw new Error('app-origin API refused');
  const request = endpointRequest(payload, origin);
  if (!request || request.hasCredentials || !endpointRequestMatches(pinned.endpoint, payload, origin)) throw new Error('request scope is not declared');
  const snapshot = await snapshotOperationPayload(payload, pinned, origin, request);
  if (!endpointRequestMatches(pinned.endpoint, snapshot, origin)) throw new Error('request scope changed while snapshotting');
  return snapshot;
}

/** Match an app request against one declared endpoint. */
export function clientEndpointAllowsRequest(endpoint, input, method = 'GET') {
  if (!record(endpoint) || !validEndpoint(endpoint) || Object.hasOwn(endpoint, 'browser-action')) return false;
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
      || !['indexeddb', 'opfs', 'localstorage'].includes(state.adapter)
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
      if (Object.hasOwn(operation.endpoint, 'browser-action')
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
  const problems = clientRuntimeProblems(runtime, requestedCapabilities, appOrigins);
  if (problems.length) {
    throw new Error(`invalid client runtime descriptor: ${problems.map(({field, error}) => `${field}:${error}`).join(', ')}`);
  }
  const origins = new Set();
  for (const operation of runtime.operations) {
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
 * No approval token or approval store is exposed to application code.
 */
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
  dialog.append(title, scope, note, deny, allow); doc.body.append(dialog);
  let pending = null;
  let destroyed = false;
  function finish(approved) {
    if (!pending) return;
    const resolve = pending; pending = null;
    if (dialog.open) dialog.close();
    resolve(approved);
  }
  allow.addEventListener('click', (event) => {
    if (event.isTrusted === true && event.currentTarget === allow
        && event instanceof doc.defaultView.MouseEvent && dialog.open) finish(true);
  });
  deny.addEventListener('click', () => finish(false));
  dialog.addEventListener('cancel', (event) => { event.preventDefault(); finish(false); });
  dialog.addEventListener('close', () => finish(false));
  const handle = Object.freeze({ destroy() { destroyed = true; finish(false); dialog.remove(); } });
  consentHosts.set(handle, async (details) => {
    if (destroyed || pending || !dialog.isConnected) throw new Error('trusted consent UI is unavailable or busy');
    scope.textContent = [
      `Service: ${details.service}`, `Operation: ${details.operation}`,
      `Capability: ${details.capability}`, `Endpoint: ${details.endpointOrigin}`,
      `Action: ${details.browserAction ?? `${details.endpointMethod} ${details.endpointPath}${details.endpointSearch}`}`,
      `Data categories: ${details.dataCategories.join(', ') || '(none)'}`,
      `Delivery redirects: ${details.redirectOrigins.join(', ') || '(none)'}`,
    ].join('\n');
    return new Promise((resolve, reject) => {
      pending = resolve;
      try { dialog.showModal(); deny.focus(); }
      catch (error) { pending = null; reject(error); }
    });
  });
  return handle;
}

function validArtifactDeclaration(value) {
  return exactKeys(value, ['revision', 'sha256', 'max-bytes'])
    && typeof value.revision === 'string' && /^[0-9a-f]{40}$/.test(value.revision)
    && typeof value.sha256 === 'string' && /^[0-9a-f]{64}$/.test(value.sha256)
    && Number.isSafeInteger(value['max-bytes']) && value['max-bytes'] > 0
    && value['max-bytes'] <= 536870912;
}

const hexBytes = (bytes) => Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
const decodeHex = (text) => Uint8Array.from(text.match(/../g) ?? [], (byte) => parseInt(byte, 16));
const sha256 = async (bytes) => hexBytes(new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes)));

/** Immutable Blob, pinned revision, independent digest verification. No execute. */
export async function verifyClientArtifact(bytes, declaration) {
  if (!validArtifactDeclaration(declaration) || !(bytes instanceof Uint8Array)) throw new TypeError('artifact requires bytes, immutable revision and expected digest');
  declaration = freezeClone(declaration);
  const snapshot = new Uint8Array(bytes);
  if (snapshot.byteLength > declaration['max-bytes']) throw new Error('artifact exceeds declared byte budget');
  const digest = await sha256(snapshot);
  if (digest !== declaration.sha256) throw new Error('artifact digest mismatch; execution refused');
  const result = Object.freeze({ blob: new Blob([snapshot]), sha256: digest, revision: declaration.revision, verified: true });
  verifiedArtifacts.add(result);
  return result;
}

/** Isolated, self-contained HTML app only. The trusted host must first admit
 * its publisher and descriptor. Host-issued eligibility and adapters never
 * cross the port. CSP prevents the guest from issuing service requests itself.
 */
export async function mountRestrictedClientApp({ artifact, container, broker }) {
  if (!verifiedArtifacts.has(artifact) || !(container instanceof globalThis.HTMLElement)
      || typeof broker?.invoke !== 'function') throw new TypeError('verified app artifact and trusted host broker required');
  const html = await artifact.blob.text();
  if (html.length > 8388608) throw new Error('app HTML exceeds byte budget');
  const frame = document.createElement('iframe');
  frame.title = 'Restricted Kotoba application';
  frame.sandbox = 'allow-scripts';
  frame.referrerPolicy = 'no-referrer';
  frame.srcdoc = '<!doctype html><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; connect-src \'none\'; script-src \'unsafe-inline\' blob: \'wasm-unsafe-eval\'; style-src \'unsafe-inline\'; img-src data: blob:; media-src blob:; worker-src blob:; frame-src \'none\'; object-src \'none\'; form-action \'none\'; base-uri \'none\'">' + html;
  let closed = false;
  const channel = new MessageChannel();
  channel.port1.onmessage = async ({ data }) => {
    if (closed || !plainData(data) || !exactKeys(data, ['protocol', 'id', 'selector', 'payload'])
        || data.protocol !== 'kotoba.client.operation.v1' || !validName(data.id)) return;
    try {
      const result = await broker.invoke(data.selector, data.payload);
      if (result instanceof Response) {
        // Bridge bounded service data, never the host's transport/credentials.
        const bytes = result.body ? await boundedBytes(result.body, 1048576, 30000) : new Uint8Array();
        const content = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
        channel.port1.postMessage({ id: data.id, ok: true, status: result.status, content });
      } else channel.port1.postMessage({ id: data.id, ok: true, result });
    } catch (error) { channel.port1.postMessage({ id: data.id, ok: false, error: String(error.message).slice(0, 1024) }); }
  };
  frame.addEventListener('load', () => {
    if (!closed) frame.contentWindow.postMessage({ protocol: 'kotoba.client.host.v1' }, '*', [channel.port2]);
  }, { once: true });
  container.append(frame);
  return Object.freeze({ close() { closed = true; channel.port1.close(); frame.remove(); } });
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

async function boundedArtifact(response, declaration) {
  if (!response.body) throw new Error('artifact response has no readable body');
  return verifyClientArtifact(await boundedBytes(response.body, declaration['max-bytes'], 120000), declaration);
}

async function boundedBytes(stream, maxBytes, deadlineMs) {
  const reader = stream.getReader();
  const chunks = []; let size = 0;
  let timer;
  const deadline = new Promise((resolve, reject) => { timer = setTimeout(() => reject(new Error('body snapshot deadline exceeded')), deadlineMs); });
  try {
    while (true) {
      const { done, value } = await Promise.race([reader.read(), deadline]);
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) throw new Error('body exceeds declared byte budget');
      chunks.push(value);
    }
  } catch (error) { reader.cancel().catch(() => {}); throw error; }
  finally { clearTimeout(timer); try { reader.releaseLock(); } catch { /* cancelled pending read */ } }
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
  const { runtime, requestedCapabilities = [], approvedOperations = [], hostSupportedOperations = [], browserAdapters = {}, consentHost } = options;
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
  const fetchRequest = globalThis.fetch.bind(globalThis);
  return Object.freeze({
    operations: Object.freeze(operations),
    async invoke(selector, payload) {
      const operation = bySelector.get(JSON.stringify([selector?.capability, selector?.service, selector?.operation]));
      if (!operation) throw new Error('client operation is not eligible and supported');
      const endpointOrigin = operation.endpoint.origin;
      if (endpointOrigin === globalThis.location?.origin) throw new Error('service endpoint must be distinct from the app origin');
      const browserAction = operation.endpoint['browser-action'];
      let approvedPayload; let request = null;
      if (browserAction) {
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
        approvedPayload = await prepareClientOperationRequest(operation, payload);
        request = endpointRequest(approvedPayload, endpointOrigin);
        if (!request || request.hasCredentials || !endpointRequestMatches(operation.endpoint, approvedPayload, endpointOrigin)) throw new Error('request scope changed while snapshotting');
      }
      const allowed = await confirm(Object.freeze({
        capability: operation.capability, service: operation.service, operation: operation.operation,
        endpointOrigin, browserAction, endpointMethod: request?.method ?? null,
        endpointPath: request?.path ?? null, endpointSearch: request?.search ?? '',
        dataCategories: operation['data-categories'], redirectOrigins: Object.freeze([...(operation['redirect-origins'] ?? [])]),
      }));
      if (allowed !== true) throw new Error('client operation was not approved');
      if (browserAction) return handlers.get(operationSelector(operation))({ operation, payload: approvedPayload });
      const result = await fetchRequest(approvedPayload.input);
      if (result.type === 'opaqueredirect' || (result.status >= 300 && result.status < 400) || !result.url) throw new Error('service response redirect could not be verified');
      const responseOrigin = new URL(result.url).origin;
      if (![endpointOrigin, ...(operation['redirect-origins'] ?? [])].some((origin) => redirectOriginAllows(origin, responseOrigin))) throw new Error('service response redirect origin is not declared');
      if (operation.artifact) {
        if (!result.ok) throw new Error('artifact download failed');
        return boundedArtifact(result, operation.artifact);
      }
      return result;
    },
  });
}
