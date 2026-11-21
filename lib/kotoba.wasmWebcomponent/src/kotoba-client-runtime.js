const NAME = /^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$/;
const ENTRY = /^[A-Za-z0-9._~!$&'()+,;=@/-]+$/;
const ORIGIN = /^https:\/\/(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?::(?:[1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?$/;
const USER_SELECTED_APP = 'user-selected-app';
const USER_SELECTED_APP_LABEL = 'an app you choose on this device (not chosen by this app)';
const BROWSER_PUSH_PROVIDER = 'browser-selected-push-provider';
const BROWSER_PUSH_PROVIDER_LABEL = 'the push provider selected by this browser';
const BROWSER_PUSH_ACTIONS = new Set(['request-notification-permission', 'create-push-subscription', 'remove-push-subscription']);
const RUNTIME_KEYS = ['entry', 'local-state', 'operations', 'profile', 'schema', 'target', 'workers'];
// KOTOBA-159 finding 9: `disclosure` is required; validated on its own so the problem names it.
const OPERATION_REQUIRED_KEYS = ['capability', 'consent', 'data-categories', 'endpoint', 'operation', 'service'];
const OPERATION_KEYS = [...OPERATION_REQUIRED_KEYS, 'redirect-origins', 'artifact', 'disclosure', 'scope'];
// Largest snapshot transfer a scoped peer operation may declare (KOTOBA-159 D2). The broker checks it
// again, and the host adapter's declared enforcement bound may only lower it.
export const PEER_TRANSFER_MAX_BYTES = 268435456;
export const PEER_SCOPE_ENFORCEMENT_SCHEMA = 'kotoba.peer-scope-enforcement.v1';

// KOTOBA-159 findings 8, P1, D1: internal addresses. A service origin, redirect origin, peer address,
// circuit-relay hop or receive listener on loopback, RFC 1918, link-local (169.254.169.254 included),
// CGNAT, 0.0.0.0/8 or the IPv6 equivalents (::1, fc00::/7, fe80::/10, IPv4-mapped/compatible and NAT64
// forms) reaches the user's device, LAN or cloud metadata. They are refused unless the operation
// declares `scope: "lan"`, which the consent dialog prints. Multicast/reserved space is always refused.
function ipv4Parts(text) {
  if (typeof text !== 'string' || !/^\d{1,3}(?:\.\d{1,3}){3}$/.test(text)) return null;
  const parts = text.split('.').map(Number);
  return parts.every((n, i) => n <= 255 && String(n) === text.split('.')[i]) ? parts : null;
}
function ipv4Scope([a, b]) {
  if (a === 0) return 'unspecified';
  if (a === 127) return 'loopback';
  if (a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168)) return 'private';
  if (a === 169 && b === 254) return 'link-local';
  if (a === 100 && b >= 64 && b <= 127) return 'cgnat';
  if (a >= 224) return 'reserved';
  return 'public';
}
function ipv6Hextets(text) {
  if (typeof text !== 'string' || text.length > 64 || !/^[0-9A-Fa-f:.]+$/.test(text)) return null;
  let tail = [];
  const dotted = text.match(/^(.*:)(\d{1,3}(?:\.\d{1,3}){3})$/);
  if (dotted) {
    const v4 = ipv4Parts(dotted[2]); if (!v4) return null;
    text = `${dotted[1]}${((v4[0] << 8) | v4[1]).toString(16)}:${((v4[2] << 8) | v4[3]).toString(16)}`;
  }
  const halves = text.split('::');
  if (halves.length > 2) return null;
  const parse = (part) => (part === '' ? [] : part.split(':'));
  const head = parse(halves[0]); tail = halves.length === 2 ? parse(halves[1]) : [];
  if (![...head, ...tail].every((h) => /^[0-9A-Fa-f]{1,4}$/.test(h))) return null;
  const missing = 8 - head.length - tail.length;
  if (halves.length === 1 ? missing !== 0 : missing < 1) return null;
  return [...head, ...Array(halves.length === 2 ? missing : 0).fill('0'), ...tail].map((h) => parseInt(h, 16));
}
function ipv6Scope(h) {
  const embedded = () => ipv4Scope([h[6] >> 8, h[6] & 255]);
  if (h.every((x) => x === 0)) return 'unspecified';
  if (h.slice(0, 7).every((x) => x === 0) && h[7] === 1) return 'loopback';
  if (h.slice(0, 5).every((x) => x === 0) && h[5] === 0xffff) return embedded();        // ::ffff:a.b.c.d
  if (h.slice(0, 6).every((x) => x === 0)) return embedded();                           // ::a.b.c.d
  if (h[0] === 0x64 && h[1] === 0xff9b && h.slice(2, 6).every((x) => x === 0)) return embedded(); // 64:ff9b::/96
  if ((h[0] & 0xfe00) === 0xfc00) return 'private';
  if ((h[0] & 0xffc0) === 0xfe80) return 'link-local';
  if ((h[0] & 0xff00) === 0xff00) return 'reserved';
  return 'public';
}
const LAN_NAMES = /(?:^|\.)(?:localhost|local|home\.arpa|internal)$/;
/** Classify a host (IPv4, IPv6 with or without brackets, or DNS name) as 'public' or the kind of
 * internal address it names: loopback, private, link-local, cgnat, unspecified, reserved, lan-name. */
export function clientAddressScope(host) {
  if (typeof host !== 'string' || host.length === 0) return 'reserved';
  let text = host.toLowerCase();
  if (text.startsWith('[') && text.endsWith(']')) text = text.slice(1, -1);
  if (text.includes('%')) return 'link-local';                      // a zone id names a local interface
  const v4 = ipv4Parts(text);
  if (v4) return ipv4Scope(v4);
  if (text.includes(':')) { const h = ipv6Hextets(text); return h ? ipv6Scope(h) : 'reserved'; }
  const name = text.replace(/\.$/, '');
  if (name === 'localhost' || name.endsWith('.localhost')) return 'loopback';
  return LAN_NAMES.test(name) ? 'lan-name' : 'public';
}
function originHost(origin) {
  if (typeof origin !== 'string') return null;
  if (origin.startsWith('https://*.')) return origin.slice('https://*.'.length);
  try { return new URL(origin).hostname; } catch { return null; }
}
function hostAllowed(host, lan) {
  const scope = clientAddressScope(host);
  return scope === 'public' || (lan && scope !== 'reserved');
}

// KOTOBA-159 finding 9 (Legal design and wording, 2026-11-22): what the user is told before sending.
// Every field is declared by the app and shown as written; nothing is inferred from the payload.
// recipient: the legal entity's official name (not an origin or abbreviation). data: categories in
// words a user reads (氏名、メールアドレス、相談内容 …). purpose: one specific sentence. withdrawal: the
// name of the place in settings (「設定 › 許可した送信」). special-care: 要配慮個人情報 or a GDPR special
// category; when true, special-care-kinds names them (病歴 …). A recipient outside Japan also carries
// country-name and foreign-info-url, a page with the 施行規則 17 条 2 項 information: the country, its
// data-protection regime and the recipient's measures.
const DISCLOSURE_KEYS = ['recipient', 'country', 'data', 'special-care', 'purpose', 'frequency', 'withdrawal'];
const FOREIGN_DISCLOSURE_KEYS = ['country-name', 'foreign-info-url'];
// Plain words: no control, bidi-override or zero-width characters that could disguise the text.
function plainWords(value, max) {
  return typeof value === 'string' && value.trim().length > 0 && value.length <= max && value.trim() === value
    && !/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2066-\u2069\ufeff]/.test(value);
}
const plainList = (value, max) => Array.isArray(value) && value.length >= 1 && value.length <= 32
  && value.every((item) => plainWords(item, max)) && new Set(value).size === value.length;
function validHttpsUrl(value) {
  if (typeof value !== 'string' || value.length > 512) return false;
  try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password && url.href === value; } catch { return false; }
}
/** Problems with an operation's `disclosure` (finding 9). Empty when it is complete. */
export function clientDisclosureProblems(value) {
  if (!record(value)) return ['missing-disclosure'];
  const foreign = value.country !== 'JP';
  const special = value['special-care'] === true;
  const keys = [...DISCLOSURE_KEYS, ...(special ? ['special-care-kinds'] : []), ...(foreign ? FOREIGN_DISCLOSURE_KEYS : []),
    ...(Object.hasOwn(value, 'note') ? ['note'] : [])];
  const problems = [];
  if (!exactKeys(value, keys)) problems.push('invalid-disclosure-keys');
  // Optional app note: plain text up to 200 characters, no control characters; shown as text only.
  if (Object.hasOwn(value, 'note') && !plainWords(value.note, 200)) problems.push('invalid-note');
  if (!plainWords(value.recipient, 120)) problems.push('invalid-recipient');
  if (typeof value.country !== 'string' || !/^[A-Z]{2}$/.test(value.country)) problems.push('invalid-country');
  if (!plainList(value.data, 80)) problems.push('invalid-data');
  if (typeof value['special-care'] !== 'boolean') problems.push('invalid-special-care');
  if (special && !plainList(value['special-care-kinds'], 60)) problems.push('invalid-special-care-kinds');
  if (!plainWords(value.purpose, 120)) problems.push('invalid-purpose');
  if (!['one-time', 'continuous'].includes(value.frequency)) problems.push('invalid-frequency');
  if (!plainWords(value.withdrawal, 120)) problems.push('invalid-withdrawal');
  if (foreign) {
    if (!plainWords(value['country-name'], 60)) problems.push('invalid-country-name');
    if (!validHttpsUrl(value['foreign-info-url'])) problems.push('invalid-foreign-info-url');
  }
  return problems;
}
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
function literalPeerAddress(address, peer, listener = false, lan = false) {
  if (typeof address !== 'string' || address.length > 512) return false;
  const match = address.match(/^\/ip4\/(\d{1,3}(?:\.\d{1,3}){3})\/(?:udp\/(\d{1,5})\/(quic-v1|webrtc-direct\/certhash\/u[A-Za-z0-9_-]{46})|tcp\/(\d{1,5}))(.*)$/);
  if (!match || !match[1].split('.').every(n => String(Number(n)) === n && Number(n) <= 255)
      || match[1] === '0.0.0.0' || Number(match[1].split('.')[0]) >= 224
      || Number(match[2] ?? match[4]) < 1 || Number(match[2] ?? match[4]) > 65535
      || !hostAllowed(match[1], lan)) return false;
  const suffix = match[5];
  const id = '[1-9A-HJ-NP-Za-km-z]{32,128}';
  if (listener) return !match[3]?.startsWith('webrtc')
    && (suffix === '' || new RegExp(`^/p2p/(${id})/p2p-circuit$`).test(suffix));
  if (suffix === `/p2p/${peer}`) return true;
  const circuit = suffix.match(new RegExp(`^/p2p/(${id})/p2p-circuit/p2p/(${id})$`));
  return !match[3]?.startsWith('webrtc') && !!circuit && circuit[1] !== peer && circuit[2] === peer;
}
function peerScopeValid(value, receive, lan) {
  const keys = receive ? ['snapshot-cid','max-transfer-bytes','listen-address','receive-ms','allow-read-back'] : ['snapshot-cid','max-transfer-bytes'];
  return exactKeys(value, keys)
    && typeof value['snapshot-cid'] === 'string' && /^b[a-z2-7]{30,127}$/.test(value['snapshot-cid'])
    && Number.isSafeInteger(value['max-transfer-bytes']) && value['max-transfer-bytes'] > 0 && value['max-transfer-bytes'] <= 268435456
    && (!receive || (typeof value['allow-read-back'] === 'boolean' && literalPeerAddress(value['listen-address'], null, true, lan)
      && Number.isSafeInteger(value['receive-ms']) && value['receive-ms'] > 0 && value['receive-ms'] <= 21600000));
}
/** `options.scope === 'lan'` admits internal addresses (findings P1, D1); otherwise they are refused. */
export function clientPeerEndpointProblems(value, options = {}) {
  const lan = record(options) && options.scope === 'lan';
  const keys = ['transport','peer-id','addresses','protocol','action','max-request-bytes','max-response-bytes','timeout-ms'];
  const scoped = record(value) && Object.hasOwn(value, 'scope');
  const receive = value?.action === 'receive-snapshot';
  if (!exactKeys(value, scoped ? [...keys, 'scope'] : keys)
      || value.transport !== 'libp2p'
      || typeof value['peer-id'] !== 'string' || !/^[1-9A-HJ-NP-Za-km-z]{32,128}$/.test(value['peer-id'])
      || !Array.isArray(value.addresses) || value.addresses.length < (receive ? 0 : 1) || value.addresses.length > 4
      || new Set(value.addresses).size !== value.addresses.length
      || !value.addresses.every(address => literalPeerAddress(address, value['peer-id'], false, lan))
      || typeof value.protocol !== 'string' || !/^\/[A-Za-z0-9._/-]{1,110}\/\d+\.\d+\.\d+$/.test(value.protocol)
      || !validName(value.action)
      || (scoped && (!['sync-push','sync-pull','pin-query','receive-snapshot'].includes(value.action)
        || value.protocol !== '/awai/yataverse/1.0.0' || !peerScopeValid(value.scope, receive, lan)))
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

function validEndpoint(value, lan = false) {
  // An HTTP or browser-action origin must name a public host unless the operation is `scope: "lan"`.
  if (record(value) && Object.hasOwn(value, 'origin') && !hostAllowed(originHost(value.origin), lan)) return false;
  return (record(value) && value.transport === 'libp2p' && clientPeerEndpointProblems(value, { scope: lan ? 'lan' : undefined }).length === 0)
    || (record(value) && value.transport === 'nearby' && clientNearbyEndpointProblems(value).length === 0)
    || (exactKeys(value, ['origin', 'browser-action'])
      && validOrigin(value.origin) && validName(value['browser-action']))
    // AWAI-3336: a browser-native hand-off whose receiver the user picks in the OS (a share sheet).
    // There is no service origin to declare, so none is fabricated; the recipient is a fixed marker.
    || (exactKeys(value, ['browser-action', 'recipient'])
      && value.recipient === USER_SELECTED_APP && validName(value['browser-action']))
    || (exactKeys(value, ['browser-action', 'recipient'])
      && value.recipient === BROWSER_PUSH_PROVIDER && BROWSER_PUSH_ACTIONS.has(value['browser-action']))
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

// KOTOBA-159 finding 7: a generic network rail is refused by its shape, whatever it is called.
// A wildcard or non-literal service origin (any host), or a path made only of parameters (no path
// restriction: `/:a`, `/:a/:b`), lets the guest choose where a request goes.
function genericNetworkEndpoint(endpoint) {
  if (!record(endpoint)) return false;
  if (typeof endpoint.origin === 'string' && /[*?{}<>\s]/.test(endpoint.origin)) return true;
  const unrestricted = (path) => typeof path === 'string' && path !== '/'
    && path.slice(1).split('/').every((segment) => ENDPOINT_PARAMETER.test(segment));
  if (unrestricted(endpoint.path)) return true;
  return Array.isArray(endpoint.routes) && endpoint.routes.some((route) => record(route) && unrestricted(route.path));
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
  return { snapshot: Object.freeze(snapshot), body, headers: requestSnapshot.headers };
}

/** Pure preflight/snapshot, not an approval or a transport capability. */
export async function prepareClientOperationRequest(operation, payload, signal) {
  return (await prepareRequest(operation, payload, signal)).snapshot;
}
async function prepareRequest(operation, payload, signal) {
  if (signal !== undefined && !(signal instanceof AbortSignal)) throw new TypeError('invalid operation signal');
  if (signal?.aborted) throw new Error('client operation cancelled');
  if (!validEndpoint(operation?.endpoint, operation?.scope === 'lan') || Object.hasOwn(operation.endpoint, 'browser-action') || Object.hasOwn(operation.endpoint, 'transport')) throw new TypeError('HTTP endpoint declaration required');
  const pinned = freezeClone(operation), origin = pinned.endpoint.origin;
  if (origin === globalThis.location?.origin) throw new Error('app-origin API refused');
  const request = endpointRequest(payload, origin);
  if (!request || request.hasCredentials || !endpointRequestMatches(pinned.endpoint, payload, origin)) throw new Error('request scope is not declared');
  const captured = await snapshotOperationPayload(payload, pinned, origin, request, signal);
  if (signal?.aborted) throw new Error('client operation cancelled');
  if (!endpointRequestMatches(pinned.endpoint, captured.snapshot, origin)) throw new Error('request scope changed while snapshotting');
  return captured;
}

/** Match an app request against one declared endpoint. Pass `{ scope: 'lan' }` for a LAN operation. */
export function clientEndpointAllowsRequest(endpoint, input, method = 'GET', options = {}) {
  if (!record(endpoint) || !validEndpoint(endpoint, record(options) && options.scope === 'lan') || Object.hasOwn(endpoint, 'browser-action') || Object.hasOwn(endpoint, 'transport')) return false;
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
      if (record(operation) && genericNetworkEndpoint(operation.endpoint)) {
        problems.push({ field: 'operations', error: 'generic-network-endpoint' });
        continue;
      }
      const lan = record(operation) && operation.scope === 'lan';
      if (record(operation) && Object.hasOwn(operation, 'scope') && !lan) {
        problems.push({ field: 'operations', error: 'invalid-scope' });
        continue;
      }
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
          // Shape first, with internal hosts admitted; the address rule below then names its own problem.
          || !validEndpoint(operation.endpoint, true)
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
      if (!lan && operationHosts(operation).some((host) => !hostAllowed(host, false))) {
        problems.push({ field: 'operations', error: 'internal-address-requires-lan-scope', selector });
        continue;
      }
      const disclosureProblems = clientDisclosureProblems(operation.disclosure);
      if (disclosureProblems.length) {
        problems.push({ field: 'operations', error: 'invalid-disclosure', selector, details: disclosureProblems });
      }
      if (lan) {
        // `scope: "lan"` is printed as "a device on your local network"; it must not cover a public host.
        const hosts = operationHosts(operation);
        if (hosts.length === 0 || hosts.some((host) => clientAddressScope(host) === 'public')) {
          problems.push({ field: 'operations', error: 'lan-scope-requires-internal-addresses', selector });
        }
      }
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
      // Kept from the name-based check; the structural check above is the one that does not depend on naming.
      if (operation.capability === 'net/http-post') {
        problems.push({ field: 'operations', error: 'generic-network-capability', selector });
      }
    }
  }
  return problems;
}

// Every host an operation reaches: service and redirect origins, peer and relay addresses, the listener.
function operationHosts(operation) {
  const endpoint = operation?.endpoint;
  const hosts = [];
  if (record(endpoint) && typeof endpoint.origin === 'string') hosts.push(originHost(endpoint.origin));
  for (const origin of Array.isArray(operation?.['redirect-origins']) ? operation['redirect-origins'] : []) hosts.push(originHost(origin));
  const ip = (address) => (typeof address === 'string' ? address.match(/^\/ip4\/([^/]+)\//)?.[1] : null);
  if (record(endpoint) && Array.isArray(endpoint.addresses)) hosts.push(...endpoint.addresses.map(ip));
  if (record(endpoint?.scope) && Object.hasOwn(endpoint.scope, 'listen-address')) hosts.push(ip(endpoint.scope['listen-address']));
  return hosts.filter((host) => typeof host === 'string');
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
const canonicalBrokers = new WeakSet();

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

// DRAFT WORDING（下書きの文言）: KOTOBA-159 findings 1 and 9. Strings from Legal's draft
// reports/kotoba-159-consent-wording.md (2026-11-22). Legal finalizes them before any public release;
// a lawyer still has to confirm the EU points (GDPR 49(1)(a) for continuous transfers, an Art. 27
// representative). Every user-facing string of the consent dialog lives here and only here, so the
// final wording replaces this one object. Do not add dialog text elsewhere.
// Rule from the draft: a line whose inserted value is missing is left out entirely, never shown blank.
// A paragraph is a string, or an array of strings and links ({ link, href }); links render as <a>.
const consentLink = (link, href) => Object.freeze({ link, href });
const CONSENT_TEXT_JA = Object.freeze({
  ariaLabel: '外部への送信の確認',
  appFallback: 'この app',
  titleRestricted: (app) => `${app} が、次の情報を送ろうとしています`,
  titleTrusted: (app) => `${app} が、次の情報を送ります`,
  recipient: (name, country) => `送り先: ${name}（${country}）`,
  japan: '日本',
  data: (list) => `送る情報: ${list}`,
  listSeparator: '、',
  purpose: (text) => `目的: ${text}`,
  frequency: (text) => `送る回数: ${text}`,
  once: '1 回だけ',
  continuous: '許可を取り消すまで続けて',
  specialCare: (kinds) => `この中には、${kinds} が含まれます。`,
  restrictedNotice: (withdrawal) => `許可しない場合、この情報は送られません。許可は、あとで ${withdrawal} から取り消せます。`,
  foreign: (country, url) => [`送り先は日本の外（${country}）にあります。${country} の個人情報の保護に関する制度と、送り先が講じている保護の措置は、`, consentLink('こちら', url), ' で確かめられます。日本と同じ水準の保護が受けられないことがあります。'],
  // trusted-page-v1 (Itonami, AWAI-3819): the same facts, without any claim that refusing prevents sending.
  trustedWithdrawal: (withdrawal) => `許可は、あとで ${withdrawal} から取り消せます。`,
  trustedForeign: (country, url) => [`送り先は日本の外（${country}）にあります。制度と送り先の措置は `, consentLink('こちら', url), '。'],
  trustedProvider: (name, url) => [`この app は ${name} が提供する app です。通信は ${name} の`, consentLink('プライバシーポリシー', url), ' に従います。'],
  trustedNotice: 'この画面は送信の確認で、送信の制限を保証するものではありません。',
  lan: '送り先は、この端末と同じローカルネットワーク（LAN）の中の機器か、この端末そのものです。',
  details: '詳細を見る',
  deny: '許可しない',
  allow: '許可する',
  close: '閉じる',
  continue: '続ける',
  // Inside 詳細 (technical details; not part of Legal's first-screen wording).
  fullText: '全文',
  shortText: '短く表示',
  length: (n) => `${n} 文字`,
  truncated: (n) => `…（全 ${n} 文字。「全文」で表示）`,
  payload: '送る内容',
  payloadType: '内容の種類',
  payloadSize: (n) => `大きさ: ${n} バイト`,
  payloadDigest: 'SHA-256',
  payloadFields: 'フィールド名',
  payloadHeaders: 'ヘッダー名',
  payloadNone: '（送る内容はありません）',
  payloadBinary: '（文字ではない内容のため表示しません）',
  payloadCut: (n) => `（表示は先頭 ${n} 文字まで）`,
  none: '（なし）',
});
const CONSENT_TEXT_EN = Object.freeze({
  ariaLabel: 'Confirm sending',
  appFallback: 'This app',
  titleRestricted: (app) => `${app} wants to send the following information`,
  titleTrusted: (app) => `${app} will send the following information`,
  recipient: (name, country) => `Recipient: ${name} (${country})`,
  japan: 'Japan',
  data: (list) => `Information: ${list}`,
  listSeparator: ', ',
  purpose: (text) => `Purpose: ${text}`,
  frequency: (text) => `Frequency: ${text}`,
  once: 'Once',
  continuous: 'Continuously, until you withdraw permission',
  specialCare: (kinds) => `This includes ${kinds}.`,
  restrictedNotice: (withdrawal) => `If you do not allow it, this information will not be sent. You can withdraw your permission at any time in ${withdrawal}. Withdrawing does not affect sending that already took place.`,
  foreign: (country, url) => [`The recipient is located in ${country}, outside Japan. Data protection law there may not give the same level of protection. Information about ${country}'s data protection rules and the safeguards the recipient uses is available `, consentLink('here', url), '.'],
  trustedWithdrawal: (withdrawal) => `You can withdraw your permission at any time in ${withdrawal}. Withdrawing does not affect sending that already took place.`,
  trustedForeign: (country, url) => [`The recipient is located outside Japan (${country}). Its data protection rules and the recipient's safeguards are described `, consentLink('here', url), '.'],
  trustedProvider: (name, url) => [`This app is provided by ${name}. Its network use is governed by ${name}'s `, consentLink('Privacy Policy', url), '.'],
  trustedNotice: 'This screen is a notice. It does not guarantee that sending is restricted.',
  lan: 'The recipient is a device on the same local network (LAN) as this device, or this device itself.',
  details: 'View details',
  deny: "Don't allow",
  allow: 'Allow',
  close: 'Close',
  continue: 'Continue',
  fullText: 'Full text',
  shortText: 'Show less',
  length: (n) => `${n} characters`,
  truncated: (n) => `… (${n} characters; "Full text" shows all)`,
  payload: 'Content',
  payloadType: 'Content type',
  payloadSize: (n) => `Size: ${n} bytes`,
  payloadDigest: 'SHA-256',
  payloadFields: 'Field names',
  payloadHeaders: 'Header names',
  payloadNone: '(nothing is sent)',
  payloadBinary: '(not text; not shown)',
  payloadCut: (n) => `(first ${n} characters shown)`,
  none: '(none)',
});
export const CLIENT_CONSENT_TEXT = Object.freeze({
  status: 'draft', source: 'Legal draft reports/kotoba-159-consent-wording.md, 2026-11-22',
  ja: CONSENT_TEXT_JA, en: CONSENT_TEXT_EN,
});

// R5 / D4: a value longer than this is cut, with its length and the 全文 toggle shown.
const CONSENT_VALUE_MAX = 160;
// The full payload text shown behind 詳細 > 全文 is capped so a large body cannot freeze the host tab.
const CONSENT_PAYLOAD_TEXT_MAX = 65536;
const present = (value) => typeof value === 'string' && value.length > 0;

/** The first screen (finding 9, Legal draft): [title, list lines, paragraphs]. Missing values drop their line. */
function consentFirstScreen(details, T) {
  const d = details.disclosure;
  const trusted = details.profile !== 'restricted-wasm-v1';
  const app = present(details.app?.name) ? details.app.name : T.appFallback;
  const foreign = d.country !== 'JP';
  const country = foreign ? d['country-name'] : T.japan;
  // Both profiles show the same declared facts (Itonami, AWAI-3819); only the notice differs.
  const lines = [
    T.recipient(d.recipient, country),
    T.data(d.data.join(T.listSeparator)),
    T.purpose(d.purpose),
    ...(present(d.frequency) ? [T.frequency(d.frequency === 'continuous' ? T.continuous : T.once)] : []),
  ];
  const foreignLine = foreign && present(d['country-name']) && present(d['foreign-info-url']);
  const paragraphs = [
    ...(d['special-care'] ? [T.specialCare(d['special-care-kinds'].join(T.listSeparator))] : []),
    // The app's optional note: plain text, shown as written (textContent, never parsed).
    ...(present(d.note) ? [d.note] : []),
    ...(details.scope === 'lan' ? [T.lan] : []),
    ...(trusted
      ? [
        ...(present(d.withdrawal) ? [T.trustedWithdrawal(d.withdrawal)] : []),
        ...(foreignLine ? [T.trustedForeign(country, d['foreign-info-url'])] : []),
        ...(present(details.app?.provider) && present(details.app?.['privacy-policy']) ? [T.trustedProvider(details.app.provider, details.app['privacy-policy'])] : []),
        T.trustedNotice]
      : [T.restrictedNotice(d.withdrawal), ...(foreignLine ? [T.foreign(country, d['foreign-info-url'])] : [])]),
  ];
  return [trusted ? T.titleTrusted(app) : T.titleRestricted(app), lines, paragraphs];
}
// Plain text of a paragraph, for hosts without DOM nodes (and tests): a link shows its URL.
const paragraphText = (paragraph) => (typeof paragraph === 'string' ? paragraph
  : paragraph.map((part) => (typeof part === 'string' ? part : `${part.link}（${part.href}）`)).join(''));

// Technical scope behind 詳細. Fixed declared fields come before the guest-chosen Action (R5, D4).
function consentScopeEntries(details) {
  const peer = details.peerEndpoint; const nearby = details.nearbyEndpoint;
  const action = nearby?.action ?? peer?.action ?? details.browserAction ?? `${details.endpointMethod} ${details.endpointPath}${details.endpointSearch}`;
  return [
    ['Service', details.service], ['Operation', details.operation], ['Capability', details.capability],
    ['Endpoint', details.endpointOrigin],
    ...(details.userSelectedApp ? [['Receiver', 'the app you pick next receives the data and handles it under its own rules']] : []),
    ['Data categories', details.dataCategories.join(', ') || '(none)'],
    ['Delivery redirects', details.redirectOrigins.join(', ') || '(none)'],
    ['Network scope', details.scope === 'lan' ? 'lan (local network or this device)' : 'public'],
    ...(peer?.scope ? [['Transfer scope', canonical(peer.scope), true]] : []),
    ...(details.artifact ? [
      ['Artifact revision', details.artifact.revision],
      ['Artifact SHA-256', `${details.artifact.sha256} (a mismatch is discarded)`],
      ['Artifact byte budget', `${details.artifact['max-bytes']} bytes`],
      ['Artifact delivery', details.artifact.delivery === 'host-stream' ? 'streamed to this app on the device' : 'held in page memory'],
    ] : []),
    ...(nearby ? [
      ['Nearby device', `${nearby.action} over ${details.nearbyBearer}`],
      ['Peer', details.nearbyPeer ?? '(none: not a specific device)'],
      ['Request budget', `${nearby['max-request-bytes']} bytes`],
      ['Response budget', `${nearby['max-response-bytes']} bytes`],
      ['Deadline', `${nearby['timeout-ms']} ms`],
    ] : []),
    ...(peer ? [
      ['PeerID', peer['peer-id']], ['Addresses', peer.addresses.join(', '), true], ['Protocol', peer.protocol],
      ['Request budget', `${peer['max-request-bytes']} bytes`], ['Response budget', `${peer['max-response-bytes']} bytes`],
      ['Deadline', `${peer['timeout-ms']} ms`],
    ] : []),
    ['Action', action, true],
    ...(details.endpointSearch ? [['Query length', `${details.endpointSearch.length - 1} characters`]] : []),
  ];
}

/** Render label/value entries; values over CONSENT_VALUE_MAX are cut unless `full`. Returns [text, cut]. */
function renderEntries(entries, full, T) {
  let cut = false;
  const text = entries.map(([label, value, measured]) => {
    const raw = String(value);
    const long = raw.length > CONSENT_VALUE_MAX;
    if (long && !full) cut = true;
    const shown = long && !full ? `${raw.slice(0, CONSENT_VALUE_MAX)}${T.truncated(raw.length)}` : raw;
    return `${label}: ${shown}${measured && !long ? ` (${T.length(raw.length)})` : ''}`;
  }).join('\n');
  return [text, cut];
}

function renderPayload(payload, full, T) {
  if (!payload) return [T.payloadNone, false];
  const lines = [
    `${T.payloadType}: ${payload.contentType || T.none}`,
    T.payloadSize(payload.bytes),
    `${T.payloadDigest}: ${payload.sha256}`,
    `${T.payloadFields}: ${payload.fields.length ? payload.fields.join(', ') : T.none}`,
    ...(payload.headers ? [`${T.payloadHeaders}: ${payload.headers.length ? payload.headers.join(', ') : T.none}`] : []),
  ];
  let cut = false;
  if (payload.bytes === 0) lines.push(T.payloadNone);
  else if (payload.text === null) lines.push(T.payloadBinary);
  else {
    const limit = full ? CONSENT_PAYLOAD_TEXT_MAX : CONSENT_VALUE_MAX;
    if (payload.text.length > limit && !full) cut = true;
    lines.push(`${T.payload}:`, payload.text.length > limit
      ? `${payload.text.slice(0, limit)}${full ? T.payloadCut(limit) : T.truncated(payload.text.length)}` : payload.text);
  }
  return [lines.join('\n'), cut];
}

/** `locale` picks the draft wording: 'ja' (default) or 'en'. */
export function createClientConsentHost({ document: doc = globalThis.document, locale = 'ja' } = {}) {
  if (doc !== globalThis.document || !doc?.body || typeof doc.createElement !== 'function') {
    throw new TypeError('consent requires the trusted host document');
  }
  if (!['ja', 'en'].includes(locale)) throw new TypeError('consent locale must be ja or en');
  const T = CLIENT_CONSENT_TEXT[locale];
  const dialog = doc.createElement('dialog');
  dialog.className = 'kotoba-client-consent';
  dialog.setAttribute('aria-label', T.ariaLabel);
  dialog.setAttribute('data-wording', CLIENT_CONSENT_TEXT.status);
  dialog.setAttribute('lang', locale);
  // The heading takes focus when the dialog opens, so neither choice is selected by default.
  const title = doc.createElement('h2'); title.tabIndex = -1;
  // Created first so tests and hosts that look for the scope find it; it is shown inside 詳細.
  const scope = doc.createElement('pre'); scope.className = 'kotoba-client-consent-scope';
  // Equal visual weight (Legal draft): one class for both choices, no default, no autofocus.
  const deny = doc.createElement('button'); deny.type = 'button'; deny.textContent = T.deny;
  const allow = doc.createElement('button'); allow.type = 'button'; allow.textContent = T.allow;
  deny.className = 'kotoba-client-consent-choice'; allow.className = 'kotoba-client-consent-choice';
  allow.disabled = true;
  const summary = doc.createElement('ul'); summary.className = 'kotoba-client-consent-summary';
  // A container: each notice paragraph is its own <p> (App QA A, 2026-11-22).
  const note = doc.createElement('div'); note.className = 'kotoba-client-consent-note';
  const more = doc.createElement('details'); more.className = 'kotoba-client-consent-details';
  const moreLabel = doc.createElement('summary'); moreLabel.textContent = T.details;
  const payloadView = doc.createElement('pre'); payloadView.className = 'kotoba-client-consent-payload';
  const fullToggle = doc.createElement('button'); fullToggle.type = 'button'; fullToggle.textContent = T.fullText;
  fullToggle.className = 'kotoba-client-consent-full'; fullToggle.hidden = true;
  const actions = doc.createElement('div'); actions.className = 'kotoba-client-consent-actions';
  more.append(moreLabel, fullToggle, scope, payloadView);
  actions.append(deny, allow);
  dialog.append(title, summary, note, more, actions); doc.body.append(dialog);
  // App QA B: the details stay inside the dialog even on a host page that did not load the stylesheet.
  for (const block of [scope, payloadView]) {
    if (block.style) Object.assign(block.style, { whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', maxWidth: '100%', overflow: 'auto', boxSizing: 'border-box' });
  }
  // App QA C: Safari's default Tab order skips buttons. Every control is explicitly tabbable, and Tab /
  // Shift+Tab cycle inside the modal. Nothing is focused by default and Allow stays disabled until armed.
  for (const control of [moreLabel, fullToggle, deny, allow]) { control.tabIndex = 0; control.setAttribute('tabindex', '0'); }
  dialog.addEventListener('keydown', (event) => {
    if (event.key !== 'Tab' || !dialog.open) return;
    const order = [moreLabel, ...(more.open && !fullToggle.hidden ? [fullToggle] : []), deny, ...(allow.disabled ? [] : [allow])];
    const at = order.indexOf(doc.activeElement);
    const next = at < 0 ? (event.shiftKey ? order.length - 1 : 0) : (at + (event.shiftKey ? order.length - 1 : 1)) % order.length;
    event.preventDefault?.();
    order[next].focus();
  });
  const paragraphsOf = (paragraphs) => {
    if (typeof note.replaceChildren !== 'function') { note.textContent = paragraphs.map(paragraphText).join('\n\n'); return; }
    note.replaceChildren(...paragraphs.map((paragraph) => {
      const para = doc.createElement('p');
      // Text goes in through textContent only; a link is an <a> to an https URL checked by the validator.
      for (const part of typeof paragraph === 'string' ? [paragraph] : paragraph) {
        if (typeof part === 'string') { const span = doc.createElement('span'); span.textContent = part; para.append(span); continue; }
        const link = doc.createElement('a');
        link.textContent = part.link; link.href = part.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
        para.append(link);
      }
      return para;
    }));
  };
  const listItems = (lines) => {
    if (typeof summary.replaceChildren === 'function') summary.replaceChildren(...lines.map((line) => { const li = doc.createElement('li'); li.textContent = line; return li; }));
    else summary.textContent = lines.join('\n');
    summary.lines = Object.freeze([...lines]);
  };
  let pending = null;
  let pendingAbort = null;
  let destroyed = false;
  let shown = null; let full = false;
  function render() {
    if (!shown) return;
    const [scopeText, scopeCut] = renderEntries(consentScopeEntries(shown), full, T);
    const [payloadText, payloadCut] = renderPayload(shown.payload, full, T);
    scope.textContent = scopeText;
    payloadView.textContent = payloadText;
    fullToggle.hidden = !(full || scopeCut || payloadCut);
    fullToggle.textContent = full ? T.shortText : T.fullText;
  }
  fullToggle.addEventListener('click', () => { full = !full; render(); });
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
    // First screen: the declared disclosure (finding 9), the LAN scope (finding 8) and the profile
    // notice (finding 1), in the draft wording. The technical scope and the payload stay behind 詳細.
    const [heading, lines, paragraphs] = consentFirstScreen(details, T);
    title.textContent = heading;
    listItems(lines);
    paragraphsOf(paragraphs);
    const restricted = details.profile === 'restricted-wasm-v1';
    deny.textContent = restricted ? T.deny : T.close;
    allow.textContent = restricted ? T.allow : T.continue;
    shown = details; full = false; more.open = false;
    render();
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
        dialog.showModal(); title.focus();
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
  // R4: only a broker made by createClientOperationBroker (which always asks the trusted consent host)
  // is mounted. There is no exported way to register another object.
  if (!verifiedArtifacts.has(artifact) || !(container instanceof globalThis.HTMLElement)
      || !canonicalBrokers.has(broker)) throw new TypeError('verified app artifact and trusted host broker required');
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

// Finding 9: a technical summary of what will be sent, for the 詳細 disclosure only. Field names are
// shown as data; the plain-word categories on the first screen come from the descriptor, never from here.
// Synchronous (the incremental SHA-256 below), so showing the dialog takes no extra task.
function payloadSummary(bytes, contentType, headerNames = null) {
  let text = null;
  try { text = new TextDecoder('utf-8', { fatal: true }).decode(bytes); } catch { text = null; }
  let fields = [];
  if (text !== null && text.length > 0) {
    if (/json/i.test(contentType)) {
      try { const parsed = JSON.parse(text); if (record(parsed)) fields = Object.keys(parsed); } catch { /* not JSON */ }
    } else if (/application\/x-www-form-urlencoded/i.test(contentType)) {
      fields = [...new Set(new URLSearchParams(text).keys())];
    }
  }
  return Object.freeze({
    contentType, bytes: bytes.byteLength, sha256: (() => { const h = createSha256(); h.update(bytes); return h.hex(); })(),
    fields: Object.freeze(fields.slice(0, 64)), text, headers: headerNames ? Object.freeze(headerNames) : null,
  });
}

// D2: a scoped peer operation (snapshot CID, transfer bound, listener, read-back) is enforced by the host
// adapter, not by the broker. The adapter must say so: `{ handle, scopeEnforcement: { schema, enforces,
// 'max-transfer-bytes' } }`. A plain function is refused for a scoped operation. The declaration is a
// claim; `verifyPeerAdapterScopeConformance` is the test each host runs and records to back it.
function scopeKeysFor(endpoint) {
  return endpoint.action === 'receive-snapshot'
    ? ['snapshot-cid', 'max-transfer-bytes', 'listen-address', 'receive-ms', 'allow-read-back']
    : ['snapshot-cid', 'max-transfer-bytes'];
}
function scopedPeerAdapterProblem(entry, endpoint) {
  if (!record(entry) || typeof entry.handle !== 'function') return 'scoped peer adapter must be { handle, scopeEnforcement }';
  const declared = entry.scopeEnforcement;
  if (!exactKeys(declared, ['schema', 'enforces', 'max-transfer-bytes']) || declared.schema !== PEER_SCOPE_ENFORCEMENT_SCHEMA
      || !Array.isArray(declared.enforces) || !scopeKeysFor(endpoint).every((key) => declared.enforces.includes(key))) {
    return 'peer adapter does not declare enforcement of this scope';
  }
  if (!Number.isSafeInteger(declared['max-transfer-bytes']) || declared['max-transfer-bytes'] < 1
      || declared['max-transfer-bytes'] > PEER_TRANSFER_MAX_BYTES) return 'peer adapter transfer bound is invalid';
  if (!(endpoint.scope['max-transfer-bytes'] <= declared['max-transfer-bytes'])) return 'transfer scope exceeds what the peer adapter enforces';
  return null;
}

/** Host-adapter conformance check for scoped peer operations (KOTOBA-159 D2). Hosts must run it in their
 * own test suite against their real adapter and a fixture peer, and record the report with the runtime
 * digest they vendor. Each `violations` payload must be rejected by the adapter; `inScope` must succeed.
 * Required violation cases: `snapshot-cid` (a different snapshot), `max-transfer-bytes` (a transfer over
 * the bound) and, for receive-snapshot with allow-read-back false, `allow-read-back`. */
export async function verifyPeerAdapterScopeConformance(adapter, { operation, inScope, violations = {}, timeoutMs = 10000 } = {}) {
  const results = [];
  const endpoint = operation?.endpoint;
  const fail = (name, message) => { results.push(Object.freeze({ case: name, passed: false, message })); };
  if (!record(endpoint) || endpoint.transport !== 'libp2p' || !record(endpoint.scope)
      || clientPeerEndpointProblems(endpoint, { scope: operation.scope }).length) {
    fail('operation', 'a valid scoped libp2p operation is required');
  } else {
    const problem = scopedPeerAdapterProblem(adapter, endpoint);
    results.push(Object.freeze({ case: 'declaration', passed: problem === null, message: problem ?? 'declared' }));
    const required = ['snapshot-cid', 'max-transfer-bytes', ...(endpoint.action === 'receive-snapshot' && endpoint.scope['allow-read-back'] === false ? ['allow-read-back'] : [])];
    for (const key of required) if (!record(violations) || !Object.hasOwn(violations, key)) fail(key, 'violation case not supplied');
    const frozen = freezeClone(operation);
    const run = async (payload) => {
      const controller = new AbortController();
      let timer;
      try {
        return await Promise.race([
          Promise.resolve().then(() => adapter.handle({ operation: frozen, payload: freezeClone(payload), signal: controller.signal })),
          new Promise((_, reject) => { timer = setTimeout(() => { controller.abort(); reject(new Error('conformance case timed out')); }, timeoutMs); }),
        ]);
      } finally { clearTimeout(timer); }
    };
    if (problem === null && typeof adapter?.handle === 'function') {
      for (const [key, payload] of Object.entries(record(violations) ? violations : {})) {
        try { await run(payload); fail(key, 'adapter accepted a payload outside the declared scope'); }
        catch (error) {
          const timedOut = String(error?.message) === 'conformance case timed out';
          results.push(Object.freeze({ case: key, passed: !timedOut, message: timedOut ? 'timed out instead of refusing' : 'refused' }));
        }
      }
      try { await run(inScope); results.push(Object.freeze({ case: 'in-scope', passed: true, message: 'accepted' })); }
      catch (error) { fail('in-scope', `adapter refused an in-scope payload: ${String(error?.message).slice(0, 200)}`); }
    }
  }
  return Object.freeze({
    schema: 'kotoba.peer-scope-conformance.v1', conformant: results.length > 0 && results.every((r) => r.passed),
    results: Object.freeze(results),
  });
}

/** Trusted host owns eligibility/handlers and exposes only bounded invoke to
 * its isolated guest. HTTP transport is the captured browser fetch, not an
 * app-supplied adapter. Changing a callback to return true cannot grant access.
 * The older approvedOperations name is an eligibility ceiling, never consent.
 * One request at a time is snapshotted and shown (R3): a second invoke while one is being snapshotted
 * or awaits consent is refused at once, before its body is read.
 */
export function createClientOperationBroker(options) {
  const { runtime, requestedCapabilities = [], approvedOperations = [], hostSupportedOperations = [], browserAdapters = {}, peerAdapters = {}, artifactSinks = {}, consentHost, app = null } = options;
  // Host-supplied app identity for the dialog (from the host's own registry, not the guest):
  // { name, provider, 'privacy-policy' }. A missing field leaves its line out of the dialog.
  if (app !== null && !(record(app) && Object.keys(app).every((key) => ['name', 'provider', 'privacy-policy'].includes(key))
      && (!Object.hasOwn(app, 'name') || plainWords(app.name, 80)) && (!Object.hasOwn(app, 'provider') || plainWords(app.provider, 120))
      && (!Object.hasOwn(app, 'privacy-policy') || validHttpsUrl(app['privacy-policy'])))) throw new TypeError('invalid app identity');
  const appIdentity = app === null ? null : freezeClone(app);
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
  // Unscoped peer operations take a handler function; scoped ones a declared adapter (D2).
  const peerHandlers = new Map(operations.filter((op) => op.endpoint.transport === 'libp2p' || op.endpoint.transport === 'nearby')
    .map((op) => {
      const entry = serviceAdapter(peerAdapters, op.service, op.operation);
      if (!op.endpoint.scope) return [operationSelector(op), { handle: entry, problem: typeof entry === 'function' ? null : 'peer operation is not host-supported' }];
      const problem = scopedPeerAdapterProblem(entry, op.endpoint);
      return [operationSelector(op), { handle: problem ? null : entry.handle.bind(entry), problem }];
    }));
  // Host sinks for streamed artifacts, captured before any guest runs, like browser handlers.
  const sinks = new Map(operations.filter((op) => hostStreamArtifact(op.artifact))
    .map((op) => [operationSelector(op), serviceAdapter(artifactSinks, op.service, op.operation)]));
  const fetchRequest = globalThis.fetch.bind(globalThis);
  let slotTaken = false;
  const broker = Object.freeze({
    operations: Object.freeze(operations),
    async invoke(selector, payload, { signal } = {}) {
      if (signal !== undefined && !(signal instanceof AbortSignal)) throw new TypeError('invalid operation signal');
      if (signal?.aborted) throw new Error('client operation cancelled');
      const operation = bySelector.get(JSON.stringify([selector?.capability, selector?.service, selector?.operation]));
      if (!operation) throw new Error('client operation is not eligible and supported');
      const nearbyEndpoint = operation.endpoint.transport === 'nearby' ? operation.endpoint : null;
      // Both peer kinds run through the host adapter with the same budgets, deadline and abort signal.
      const peerEndpoint = operation.endpoint.transport === 'libp2p' || nearbyEndpoint ? operation.endpoint : null;
      const userSelectedApp = operation.endpoint.recipient === USER_SELECTED_APP;
      const endpointOrigin = nearbyEndpoint ? 'nearby device (discovered locally)' : peerEndpoint ? `libp2p:${peerEndpoint['peer-id']}`
        : userSelectedApp ? USER_SELECTED_APP_LABEL
        : operation.endpoint.recipient === BROWSER_PUSH_PROVIDER ? BROWSER_PUSH_PROVIDER_LABEL : operation.endpoint.origin;
      if (endpointOrigin === globalThis.location?.origin) throw new Error('service endpoint must be distinct from the app origin');
      const browserAction = operation.endpoint['browser-action'];
      // R3: take the broker's single slot before any payload or body is read.
      if (slotTaken) throw new Error('another client operation is awaiting consent');
      slotTaken = true;
      let approvedPayload; let request = null; let summary = null;
      try {
        if (peerEndpoint) {
          const peerHandler = peerHandlers.get(operationSelector(operation));
          if (peerHandler?.problem) throw new Error(peerHandler.problem);
          if (peerEndpoint.scope && !(peerEndpoint.scope['max-transfer-bytes'] <= PEER_TRANSFER_MAX_BYTES)) throw new Error('transfer scope exceeds the runtime bound');
          if (!plainData(payload)) throw new TypeError('peer operation requires bounded plain data');
          const json = canonical(payload);
          const encoded = typeof json === 'string' ? new TextEncoder().encode(json) : null;
          if (!encoded || encoded.length > peerEndpoint['max-request-bytes']) throw new Error('peer operation payload exceeds budget');
          approvedPayload = freezeClone(JSON.parse(json));
          if (nearbyEndpoint) {
            const problem = nearbyPayloadProblem(nearbyEndpoint, approvedPayload);
            if (problem) throw new TypeError(problem);
          }
          summary = payloadSummary(encoded, 'application/json');
        } else if (browserAction) {
          const handler = handlers.get(operationSelector(operation));
          if (typeof handler !== 'function') throw new Error('browser operation is not host-supported');
          // Browser API parameters must be bounded, plain JSON data. Functions,
          // streams, getters and mutable shared/transfer buffers are not a rail.
          if (!plainData(payload)) throw new TypeError('browser operation requires bounded plain data');
          const json = canonical(payload);
          if (typeof json !== 'string' || json.length > 65536) throw new Error('browser operation payload exceeds budget');
          approvedPayload = freezeClone(JSON.parse(json));
          summary = payloadSummary(new TextEncoder().encode(json), 'application/json');
        } else {
          request = endpointRequest(payload, endpointOrigin);
          if (!request || request.hasCredentials || !endpointRequestMatches(operation.endpoint, payload, endpointOrigin)) throw new Error('request does not match declared service method/path/query');
          const captured = await prepareRequest(operation, payload, signal);
          approvedPayload = captured.snapshot;
          request = endpointRequest(approvedPayload, endpointOrigin);
          if (!request || request.hasCredentials || !endpointRequestMatches(operation.endpoint, approvedPayload, endpointOrigin)) throw new Error('request scope changed while snapshotting');
          summary = payloadSummary(captured.body ?? new Uint8Array(), captured.headers.get('content-type') ?? '', [...captured.headers.keys()]);
        }
        if (hostStreamArtifact(operation.artifact) && typeof sinks.get(operationSelector(operation)) !== 'function') {
          throw new Error('artifact sink is not host-supported');
        }
        if (signal?.aborted) throw new Error('client operation cancelled');
        const allowed = await confirm(Object.freeze({
          profile: descriptor.profile, app: appIdentity, disclosure: operation.disclosure, scope: operation.scope ?? null, payload: summary,
          capability: operation.capability, service: operation.service, operation: operation.operation,
          endpointOrigin, userSelectedApp, peerEndpoint: nearbyEndpoint ? null : peerEndpoint, browserAction, endpointMethod: request?.method ?? null,
          nearbyEndpoint, nearbyBearer: nearbyEndpoint ? approvedPayload.bearer : null, nearbyPeer: nearbyEndpoint ? (approvedPayload.peer ?? null) : null,
          endpointPath: request?.path ?? null, endpointSearch: request?.search ?? '',
          dataCategories: operation['data-categories'], redirectOrigins: Object.freeze([...(operation['redirect-origins'] ?? [])]),
          artifact: operation.artifact ? freezeClone(operation.artifact) : null,
        }), signal);
        if (signal?.aborted) throw new Error('client operation cancelled');
        if (allowed !== true) throw new Error('client operation was not approved');
      } finally {
        slotTaken = false;
      }
      if (peerEndpoint) {
        const peerHandle = peerHandlers.get(operationSelector(operation)).handle;
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
              return peerHandle({ operation, payload: approvedPayload, signal: controller.signal });
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
  canonicalBrokers.add(broker);
  return broker;
}
