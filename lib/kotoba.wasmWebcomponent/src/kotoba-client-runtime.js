const NAME = /^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$/;
const ENTRY = /^[A-Za-z0-9._~!$&'()+,;=@/-]+$/;
const ORIGIN = /^https:\/\/(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?::(?:[1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?$/;
const USER_SELECTED_APP = 'user-selected-app';
const USER_SELECTED_APP_LABEL = 'an app you choose on this device (not chosen by this app)';
const BROWSER_PUSH_PROVIDER = 'browser-selected-push-provider';
const BROWSER_PUSH_PROVIDER_LABEL = 'the push provider selected by this browser';
const BROWSER_PUSH_ACTIONS = new Set(['request-notification-permission', 'create-push-subscription', 'remove-push-subscription']);
const RUNTIME_KEYS = ['entry', 'host-local', 'local-state', 'operations', 'profile', 'schema', 'target', 'workers'];
// KOTOBA-159 finding 9: `disclosure` is required; validated on its own so the problem names it.
const OPERATION_REQUIRED_KEYS = ['capability', 'consent', 'data-categories', 'endpoint', 'operation', 'service'];
// KOTOBA-968 body keys: request-body / response-body ('bytes' or 'text') with their max-*-bytes, the request
// content-type and the body deadline (timeout-ms).
const BODY_KEYS = ['request-body', 'max-request-bytes', 'content-type', 'response-body', 'max-response-bytes', 'timeout-ms'];
// KOTOBA-974: `oauth` names a host-local OAuth declaration whose host-held session authorizes the request.
const OPERATION_KEYS = [...OPERATION_REQUIRED_KEYS, 'redirect-origins', 'artifact', 'disclosure', 'scope', 'oauth', ...BODY_KEYS];
// KOTOBA-968 host-local calls and binary bodies. One global cap for a binary HTTP body, a stored value and a saved file: packs are up
// to 12 MiB, so 16 MiB leaves room for framing. A descriptor that declares more is refused.
export const CLIENT_PORT_BYTES_MAX = 16777216;
// Largest host-local storage quota one app may declare (Yataverse declares 2 GiB). A larger logical value
// than max-value-bytes is stored by the app as chunks under one key prefix, committed in one storage.batch.
export const CLIENT_STORAGE_QUOTA_MAX = 4294967296;
// Largest body a request may send from, or a response may write to, host-local storage (nagare's videos are up
// to 512 MiB). The bytes stay in the host and never cross the guest bridge.
export const CLIENT_REFERENCE_BODY_MAX = 1073741824;
// Largest stored request body a host buffers in memory when it cannot stream an upload (WebKit, or Chromium over
// HTTP/1.1). A declared max-request-bytes above it needs a host that streams uploads.
export const CLIENT_UPLOAD_BUFFER_MAX = 268435456;
// Longest URL device.openLink may open.
export const CLIENT_LINK_URL_MAX = 2048;
const CLIENT_STORAGE_ENTRIES_MAX = 1000000;
// Body deadline an operation may declare (timeout-ms), and the default for a declared body.
const BODY_DEADLINE_MAX_MS = 120000;
// Per broker, the declared request + response bytes of binary operations in flight may not exceed this, so
// concurrent large bodies cannot exhaust the host tab (with the R3 slot, which still guards snapshot+consent).
const BYTES_INFLIGHT_MAX = 2 * CLIENT_PORT_BYTES_MAX;
// Files a guest may hand to the host's save prompt. Nothing that a browser or OS renders as a document with
// scripts or runs when opened: no text/html, SVG, XML, JavaScript, executables or installers.
export const CLIENT_SAVE_TYPES = Object.freeze({
  'application/json': Object.freeze(['json']), 'application/x-ndjson': Object.freeze(['ndjson', 'jsonl']),
  'text/plain': Object.freeze(['txt']), 'text/csv': Object.freeze(['csv']), 'text/tab-separated-values': Object.freeze(['tsv']),
  'application/pdf': Object.freeze(['pdf']), 'image/png': Object.freeze(['png']), 'image/jpeg': Object.freeze(['jpg', 'jpeg']),
  'image/webp': Object.freeze(['webp']), 'application/gzip': Object.freeze(['gz']), 'application/zip': Object.freeze(['zip']),
  'application/warc': Object.freeze(['warc']),
  // Opaque app files (Bunsho .bs1 …): only with extensions the descriptor declares in save.octet-stream-extensions.
  'application/octet-stream': Object.freeze([]),
});
// Extensions an app may never declare for an opaque file: anything a system runs, installs or renders with scripts.
const UNSAFE_EXTENSIONS = new Set(['exe', 'msi', 'msix', 'bat', 'cmd', 'com', 'scr', 'pif', 'cpl', 'ps1', 'psm1', 'vbs', 'vbe', 'js', 'jse', 'mjs',
  'wsf', 'wsh', 'hta', 'html', 'htm', 'xhtml', 'shtml', 'mht', 'mhtml', 'svg', 'svgz', 'xml', 'xsl', 'jar', 'jnlp', 'app', 'dmg', 'pkg',
  'mpkg', 'deb', 'rpm', 'apk', 'aab', 'ipa', 'xap', 'appx', 'sh', 'bash', 'zsh', 'csh', 'command', 'tool', 'desktop', 'lnk', 'url',
  'webloc', 'inetloc', 'reg', 'dll', 'so', 'dylib', 'sys', 'drv', 'py', 'pyc', 'pyw', 'rb', 'pl', 'php', 'iso', 'img', 'vhd', 'vhdx',
  'library-ms', 'settingcontent-ms', 'scf', 'chm', 'hlp', 'gadget', 'msc', 'msp', 'mst', 'application', 'xbap', 'xll', 'docm',
  'xlsm', 'pptm', 'swf', 'workflow', 'scpt', 'action', 'run', 'bin', 'elf', 'out', 'wasm']);
export const CLIENT_STORAGE_CONFORMANCE_SCHEMA = 'kotoba.host-storage-conformance.v1';
// Legal (2026-11-22): a host gets the storage port only when it declares every one of these MUSTs.
// (no-cloud-backup and key-custody are checked on their own: see clientStorageBackendProblems.)
const STORAGE_MUSTS = ['no-logging', 'encrypted-at-rest', 'encrypted-names', 'user-clearable', 'removed-with-app'];
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
// Country status (AWAI-3883): the consent dialog reads the machine country field for display, so an
// unconfirmed country must never be written as a code. `countryStatus: "pending"` requires
// `country: null` plus a user-visible `note` and a `confirmCondition` (what would confirm it);
// the dialog then shows 未確認/Unconfirmed and no code. `countryStatus: "confirmed"` (or a legacy
// disclosure without countryStatus) requires a two-letter code. A pending disclosure carrying a
// code is invalid: the state space grows by one state, the code requirement itself is not weakened.
// withdrawal is required for a continuous operation only (Legal, 2026-11-22): a one-time permission is not
// saved, so there is nothing to withdraw; a one-time operation may still declare it, and it is not shown.
const DISCLOSURE_KEYS = ['recipient', 'country', 'data', 'special-care', 'purpose', 'frequency'];
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
  const pending = value.countryStatus === 'pending';
  const foreign = !pending && value.country !== 'JP';
  const special = value['special-care'] === true;
  const withdrawal = value.frequency !== 'one-time' || Object.hasOwn(value, 'withdrawal');
  const keys = [...DISCLOSURE_KEYS, ...(withdrawal ? ['withdrawal'] : []), ...(special ? ['special-care-kinds'] : []), ...(foreign ? FOREIGN_DISCLOSURE_KEYS : []),
    ...(Object.hasOwn(value, 'note') ? ['note'] : []),
    ...(Object.hasOwn(value, 'countryStatus') ? ['countryStatus'] : []),
    ...(pending && Object.hasOwn(value, 'confirmCondition') ? ['confirmCondition'] : [])];
  const problems = [];
  if (!exactKeys(value, keys)) problems.push('invalid-disclosure-keys');
  // Optional app note: plain text up to 200 characters, no control characters; shown as text only.
  // Mandatory when pending: it is the user-visible wording for the unconfirmed country.
  if (Object.hasOwn(value, 'note') && !plainWords(value.note, 200)) problems.push('invalid-note');
  if (pending && !plainWords(value.note, 200)) problems.push('invalid-note');
  if (!plainWords(value.recipient, 120)) problems.push('invalid-recipient');
  if (Object.hasOwn(value, 'countryStatus') && !['pending', 'confirmed'].includes(value.countryStatus)) problems.push('invalid-country-status');
  if (pending) {
    // Unconfirmed must be expressed as unconfirmed: no code, ever.
    if (value.country !== null) problems.push('invalid-country');
    if (!plainWords(value.confirmCondition, 200)) problems.push('invalid-confirm-condition');
  } else if (typeof value.country !== 'string' || !/^[A-Z]{2}$/.test(value.country)) problems.push('invalid-country');
  if (!plainList(value.data, 80)) problems.push('invalid-data');
  if (typeof value['special-care'] !== 'boolean') problems.push('invalid-special-care');
  if (special && !plainList(value['special-care-kinds'], 60)) problems.push('invalid-special-care-kinds');
  if (!plainWords(value.purpose, 120)) problems.push('invalid-purpose');
  if (!['one-time', 'continuous'].includes(value.frequency)) problems.push('invalid-frequency');
  if (withdrawal && !plainWords(value.withdrawal, 120)) problems.push('invalid-withdrawal');
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

// KOTOBA-968: a path parameter may be constrained to a fixed set of values or a character class and length
// (`path-params: { topic: { charset: 'lower-alnum-dash', 'min-length': 1, 'max-length': 64 } }` or
// `{ enum: ['a', 'b'] }`). A path made only of parameters is accepted when every one is constrained.
const PATH_PARAM_CHARSETS = Object.freeze({ 'lower-alnum-dash': /^[a-z0-9-]+$/, alnum: /^[A-Za-z0-9]+$/, hex: /^[0-9a-f]+$/, digits: /^[0-9]+$/ });
const pathParamNames = (path) => (typeof path === 'string' ? path.split('/').filter((segment) => ENDPOINT_PARAMETER.test(segment)).map((segment) => segment.slice(1)) : []);
function validParamRule(rule) {
  return (exactKeys(rule, ['enum']) && Array.isArray(rule.enum) && rule.enum.length > 0 && rule.enum.length <= 64 && new Set(rule.enum).size === rule.enum.length
      && rule.enum.every((value) => typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9._~:@_-]{0,63}$/.test(value)))
    || (exactKeys(rule, ['charset', 'min-length', 'max-length']) && Object.hasOwn(PATH_PARAM_CHARSETS, rule.charset)
      && Number.isSafeInteger(rule['min-length']) && Number.isSafeInteger(rule['max-length'])
      && rule['min-length'] >= 1 && rule['min-length'] <= rule['max-length'] && rule['max-length'] <= 128);
}
function validPathParams(params, path) {
  if (!record(params) || Object.keys(params).length === 0) return false;
  const names = pathParamNames(path);
  return Object.entries(params).every(([name, rule]) => names.includes(name) && validParamRule(rule));
}
// KOTOBA-968, Legal 2026-11-22: a link opened without a full disclosure carries only public or fixed data. A link
// target is a fixed URL (origin and path) or a template whose every path and query parameter is constrained
// (enum or charset); no free text, no undeclared query parameter, no fragment.
function validLinkTarget(target) {
  const optional = ['path-params', 'query-params'].filter((key) => record(target) && Object.hasOwn(target, key));
  if (!exactKeys(target, ['origin', 'path', ...optional]) || !validOrigin(target.origin) || !validEndpointPath(target.path)) return false;
  const names = pathParamNames(target.path);
  if (names.length > 0 !== Object.hasOwn(target, 'path-params')) return false;
  if (names.length > 0 && (!validPathParams(target['path-params'], target.path) || !names.every((name) => Object.hasOwn(target['path-params'], name)))) return false;
  if (Object.hasOwn(target, 'query-params')) {
    const query = target['query-params'];
    if (!record(query) || Object.keys(query).length === 0 || Object.keys(query).length > 16
        || !Object.entries(query).every(([name, rule]) => ENDPOINT_QUERY_PARAMETER.test(name) && validParamRule(rule))) return false;
  }
  return true;
}
function linkTargetAllows(target, url) {
  if (url.origin !== target.origin || url.hash !== '' || url.href.includes('#')) return false;
  if (!endpointPathMatches(target.path, url.pathname, target['path-params'] ?? null)) return false;
  const query = target['query-params'] ?? {};
  const names = [...new Set(url.searchParams.keys())];
  if (url.search !== '' && url.searchParams.size !== names.length) return false;
  return names.every((name) => Object.hasOwn(query, name) && pathParamAllows(query[name], url.searchParams.get(name)));
}
function pathParamAllows(rule, value) {
  if (!rule) return true;
  if (Array.isArray(rule.enum)) return rule.enum.includes(value);
  return value.length >= rule['min-length'] && value.length <= rule['max-length'] && PATH_PARAM_CHARSETS[rule.charset].test(value);
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
    || ((exactKeys(value, ['origin', 'method', 'path']) || (exactKeys(value, ['origin', 'method', 'path', 'path-params']) && validPathParams(value['path-params'], value.path)))
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
  // A parameter-only path is generic unless every parameter is constrained (KOTOBA-968 path-params).
  const unrestricted = (path, params) => typeof path === 'string' && path !== '/'
    && path.slice(1).split('/').every((segment) => ENDPOINT_PARAMETER.test(segment))
    && !(record(params) && pathParamNames(path).every((name) => Object.hasOwn(params, name)));
  if (unrestricted(endpoint.path, endpoint['path-params'])) return true;
  return Array.isArray(endpoint.routes) && endpoint.routes.some((route) => record(route) && unrestricted(route.path, route['path-params']));
}

function validEndpointRoute(route) {
  const constrained = record(route) && Object.hasOwn(route, 'path-params');
  if (constrained && (!Object.hasOwn(route, 'path') || !validPathParams(route['path-params'], route.path))) return false;
  const extra = constrained ? ['path-params'] : [];
  const exactPath = exactKeys(route, ['method', 'path', 'query-params', ...extra])
    || exactKeys(route, ['method', 'path', 'query-params', 'query-values', ...extra]);
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

function endpointPathMatches(pattern, path, params = null) {
  if (!validEndpointPath(pattern) || typeof path !== 'string') return false;
  const expected = pattern === '/' ? [] : pattern.slice(1).split('/');
  const actual = path === '/' ? [] : path.startsWith('/') ? path.slice(1).split('/') : null;
  if (!actual || expected.length !== actual.length) return false;
  return expected.every((segment, index) => ENDPOINT_PARAMETER.test(segment)
    ? /^[A-Za-z0-9][A-Za-z0-9._~:@_-]{0,127}$/.test(actual[index]) && pathParamAllows(record(params) ? params[segment.slice(1)] : null, actual[index])
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
        ? endpointPathMatches(route.path, request.path, route['path-params'])
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
    && endpointPathMatches(endpoint.path, request.path, endpoint['path-params']);
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

async function snapshotOperationPayload(payload, operation, endpointOrigin, request, signal, referenced = null) {
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
  // KOTOBA-968: a body by reference is read from storage only after consent and streamed then; the guest's
  // reference object is never a body.
  if (referenced) delete init.body;
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
  // A declared request body (KOTOBA-968) is read up to its max-request-bytes, and the stream is cancelled past
  // it, before consent; a declared content-type is the only one accepted.
  const declaredBody = Object.hasOwn(operation, 'request-body');
  if (declaredBody && Object.hasOwn(operation, 'content-type') && (captured.body || referenced)) {
    // A body without a content type is sent as the declared one; any other content type is refused.
    if (!captured.headers.has('content-type')) captured.headers.set('content-type', operation['content-type']);
    if (captured.headers.get('content-type').split(';')[0].trim().toLowerCase() !== operation['content-type']) throw new Error('request content type is not the declared one');
  }
  const bodyMax = declaredBody ? operation['max-request-bytes'] : 16777216;
  const body = referenced ? null : captured.body ? await boundedBytes(captured.body, bodyMax, declaredBody ? (operation['timeout-ms'] ?? BODY_DEADLINE_MAX_MS) : 5000, signal) : null;
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
async function prepareRequest(operation, payload, signal, referenced = null) {
  if (signal !== undefined && !(signal instanceof AbortSignal)) throw new TypeError('invalid operation signal');
  if (signal?.aborted) throw new Error('client operation cancelled');
  if (!validEndpoint(operation?.endpoint, operation?.scope === 'lan') || Object.hasOwn(operation.endpoint, 'browser-action') || Object.hasOwn(operation.endpoint, 'transport')) throw new TypeError('HTTP endpoint declaration required');
  const pinned = freezeClone(operation), origin = pinned.endpoint.origin;
  if (origin === globalThis.location?.origin) throw new Error('app-origin API refused');
  const request = endpointRequest(payload, origin);
  if (!request || request.hasCredentials || !endpointRequestMatches(pinned.endpoint, payload, origin)) throw new Error('request scope is not declared');
  const captured = await snapshotOperationPayload(payload, pinned, origin, request, signal, referenced);
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

  // KOTOBA-968: host-local calls (no consent; nothing leaves the device). A trusted-page-v1 app may declare them
  // too, so its last trusted-page release can move its data into host-local storage (migration).
  if (Object.hasOwn(runtime, 'host-local')) {
    problems.push(...clientHostLocalProblems(runtime['host-local']).map((error) => ({ field: 'host-local', error })));
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
      if (BODY_KEYS.some((key) => Object.hasOwn(operation, key))) {
        const problem = bodyDeclarationProblem(operation);
        if (problem) problems.push({ field: 'operations', error: problem, selector });
        // A body by reference reads or writes this app's own host-local storage, so the app must declare it.
        if ([operation['request-body'], operation['response-body']].includes('host-local') && !record(runtime['host-local']?.storage)) {
          problems.push({ field: 'operations', error: 'host-local-body-requires-storage', selector });
        }
      }
      if (Object.hasOwn(operation, 'artifact') && !endpointSupportsDeclaredRedirects(operation.endpoint)) {
        problems.push({ field: 'operations', error: 'artifact-requires-read-only-fixed-query', selector });
      }
      // KOTOBA-974: a request authorized by a host OAuth session names a declared oauth entry, over HTTP only.
      if (Object.hasOwn(operation, 'oauth') && (typeof operation.oauth !== 'string' || typeof operation.endpoint.origin !== 'string'
          || Object.hasOwn(operation.endpoint, 'browser-action') || Object.hasOwn(operation.endpoint, 'transport')
          || !(Array.isArray(runtime['host-local']?.oauth) && runtime['host-local'].oauth.some((entry) => entry?.id === operation.oauth)))) {
        problems.push({ field: 'operations', error: 'oauth-session-not-declared', selector });
      }
      // Kept from the name-based check; the structural check above is the one that does not depend on naming.
      if (operation.capability === 'net/http-post') {
        problems.push({ field: 'operations', error: 'generic-network-capability', selector });
      }
    }
  }
  return problems;
}

export const CLIENT_HOST_LOCAL_SCHEMA = 'kotoba.host-local.v1';
// Calls a host-local declaration may name. A host implements a subset; any other call is refused as
// not-declared. KOTOBA-974 (PR 2) adds keys.*, crypto.*, device.pick/open, device.command and oauth.*.
export const CLIENT_HOST_LOCAL_CALLS = Object.freeze([
  'storage.get', 'storage.put', 'storage.delete', 'storage.list', 'storage.clear', 'storage.batch', 'storage.usage', 'storage.watch',
  'device.save', 'device.openLink', 'device.pick', 'device.open', 'keys.generate', 'keys.open', 'keys.delete',
  'crypto.hkdf', 'crypto.aesGcmEncrypt', 'crypto.aesGcmDecrypt', 'crypto.unwrapKey', 'crypto.wrapKey', 'crypto.x25519Derive',
  'crypto.hybridEncapsulate', 'crypto.hybridDecapsulate', 'crypto.generateKey', 'crypto.xchachaEncrypt', 'crypto.xchachaDecrypt',
  'crypto.aesKwpWrap', 'crypto.aesKwpUnwrap', 'crypto.release', 'crypto.sha256', 'crypto.ed25519Sign', 'crypto.ed25519Verify', 'crypto.importKey',
  'keys.sign', 'device.command', 'oauth.authorize', 'oauth.refresh', 'oauth.release',
]);
const APP_ID = /^[a-z][a-z0-9-]{0,62}(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/;
const STORE_NAME = /^[a-z][a-z0-9-]{0,31}$/;
const limit = (value, min, max) => Number.isSafeInteger(value) && value >= min && value <= max;
const overCap = (value, max) => Number.isSafeInteger(value) && value > max;
/** KOTOBA-968: problems with a descriptor's `host-local` declaration. Empty when valid. It names an app id,
 * device-only storage (backup excluded, encrypted at rest, erasable: Legal L1, L3, L4), its stores, quotas
 * and calls, and never a network destination (no other key is accepted). */
export function clientHostLocalProblems(value) {
  const optional = ['storage', 'stores', 'keys', 'save', 'links', 'pick', 'open', 'device-commands', 'oauth'].filter((key) => record(value) && Object.hasOwn(value, key));
  if (!exactKeys(value, ['schema', 'app-id', 'calls', ...optional])) return ['invalid-host-local-keys'];
  const problems = [];
  if (value.schema !== CLIENT_HOST_LOCAL_SCHEMA) problems.push('invalid-host-local-schema');
  if (typeof value['app-id'] !== 'string' || value['app-id'].length > 128 || !APP_ID.test(value['app-id'])) problems.push('invalid-app-id');
  const calls = value.calls;
  if (!Array.isArray(calls) || calls.length === 0 || new Set(calls).size !== calls.length
      || !calls.every((call) => CLIENT_HOST_LOCAL_CALLS.includes(call))) problems.push('invalid-calls');
  const named = (prefix) => Array.isArray(calls) && calls.some((call) => typeof call === 'string' && call.startsWith(prefix));
  if (named('storage.') !== Object.hasOwn(value, 'storage') || Object.hasOwn(value, 'storage') !== Object.hasOwn(value, 'stores')) problems.push('storage-calls-need-storage-and-stores');
  if (Object.hasOwn(value, 'storage')) {
    const storage = value.storage;
    if (!exactKeys(storage, ['class', 'backup', 'at-rest', 'erasable', 'quota-bytes', 'max-entries', 'max-value-bytes'])) problems.push('invalid-storage');
    else if (storage.class !== 'device-only' || storage.backup !== 'excluded' || storage['at-rest'] !== 'encrypted' || storage.erasable !== true) problems.push('storage-must-be-device-only-excluded-encrypted-erasable');
    else if (overCap(storage['quota-bytes'], CLIENT_STORAGE_QUOTA_MAX) || overCap(storage['max-value-bytes'], CLIENT_PORT_BYTES_MAX)
        || overCap(storage['max-entries'], CLIENT_STORAGE_ENTRIES_MAX)) problems.push('limit-over-global-cap');
    else if (!limit(storage['quota-bytes'], 1, CLIENT_STORAGE_QUOTA_MAX) || !limit(storage['max-value-bytes'], 1, storage['quota-bytes'])
        || !limit(storage['max-entries'], 1, CLIENT_STORAGE_ENTRIES_MAX)) problems.push('invalid-storage');
  }
  if (Object.hasOwn(value, 'stores') && (!Array.isArray(value.stores) || value.stores.length === 0 || value.stores.length > 16
      || new Set(value.stores).size !== value.stores.length || !value.stores.every((store) => typeof store === 'string' && STORE_NAME.test(store)))) problems.push('invalid-stores');
  // KOTOBA-974: persistent keys are declared one by one: a device secret ('secret-32', HKDF) or a signing key
  // ('ed25519', keys.sign with key approval; continuous only when declared, with its withdrawal place).
  if (Object.hasOwn(value, 'keys')) problems.push(...keyDeclarationProblems(value.keys));
  if (named('keys.') && !Object.hasOwn(value, 'keys')) problems.push('key-calls-need-keys');
  if (Array.isArray(calls) && calls.includes('keys.sign') && !(Array.isArray(value.keys) && value.keys.some((key) => key?.type === 'ed25519'))) problems.push('keys-sign-needs-signing-key');
  for (const [call, key, check] of [['device.pick', 'pick', pickDeclarationProblems], ['device.open', 'open', openDeclarationProblems],
    ['device.command', 'device-commands', deviceCommandDeclarationProblems], ['oauth.', 'oauth', oauthDeclarationProblems]]) {
    const uses = call.endsWith('.') ? named(call) : Array.isArray(calls) && calls.includes(call);
    if (uses !== Object.hasOwn(value, key)) problems.push(`${call.replace(/\.$/, '')}-needs-${key}`);
    if (Object.hasOwn(value, key)) problems.push(...check(value[key]));
  }
  if (named('device.save') !== Object.hasOwn(value, 'save')) problems.push('device-save-needs-save');
  if (Object.hasOwn(value, 'save')) {
    const save = value.save;
    const opaque = record(save) && Object.hasOwn(save, 'octet-stream-extensions');
    if (!exactKeys(save, ['max-bytes', 'mime-types', ...(opaque ? ['octet-stream-extensions'] : [])])) problems.push('invalid-save');
    else if (save['mime-types'].includes?.('application/octet-stream') !== opaque) problems.push('octet-stream-needs-extensions');
    else if (opaque && (!Array.isArray(save['octet-stream-extensions']) || save['octet-stream-extensions'].length === 0 || save['octet-stream-extensions'].length > 16
        || new Set(save['octet-stream-extensions']).size !== save['octet-stream-extensions'].length
        || !save['octet-stream-extensions'].every((ext) => typeof ext === 'string' && /^[a-z0-9]{1,8}$/.test(ext) && !UNSAFE_EXTENSIONS.has(ext)))) problems.push('save-extension-not-allowed');
    else if (overCap(save['max-bytes'], CLIENT_PORT_BYTES_MAX)) problems.push('limit-over-global-cap');
    else if (!limit(save['max-bytes'], 1, CLIENT_PORT_BYTES_MAX) || !Array.isArray(save['mime-types']) || save['mime-types'].length === 0
        || new Set(save['mime-types']).size !== save['mime-types'].length) problems.push('invalid-save');
    else if (!save['mime-types'].every((type) => typeof type === 'string' && Object.hasOwn(CLIENT_SAVE_TYPES, type))) problems.push('save-type-not-allowed');
  }
  if (named('device.openLink') !== Object.hasOwn(value, 'links')) problems.push('device-open-link-needs-links');
  if (Object.hasOwn(value, 'links')) {
    // Opening a link is egress (the URL can carry data): only to declared, public https targets whose every
    // parameter is constrained (Legal 2026-11-22), each time after the trusted host prompt names the destination.
    const links = value.links;
    if (!exactKeys(links, ['targets', 'max-url-length'])) problems.push('invalid-links');
    else if (overCap(links['max-url-length'], CLIENT_LINK_URL_MAX)) problems.push('limit-over-global-cap');
    else if (!limit(links['max-url-length'], 16, CLIENT_LINK_URL_MAX) || !Array.isArray(links.targets) || links.targets.length === 0 || links.targets.length > 64
        || new Set(links.targets.map(canonical)).size !== links.targets.length || !links.targets.every(validLinkTarget)) problems.push('invalid-links');
    else if (!links.targets.every((target) => hostAllowed(originHost(target.origin), false))) problems.push('internal-address-requires-lan-scope');
  }
  return problems;
}
// Declared bodies of an HTTP operation (KOTOBA-968). request-body / response-body are 'bytes' (Uint8Array) or
// 'text' (UTF-8), each with its max-*-bytes (at most CLIENT_PORT_BYTES_MAX). content-type, when declared, is the
// only request content type accepted. timeout-ms bounds reading each body (default and maximum 120 s).
function bodyDeclarationProblem(operation) {
  const endpoint = operation.endpoint;
  const http = record(endpoint) && typeof endpoint.origin === 'string' && !Object.hasOwn(endpoint, 'browser-action') && !Object.hasOwn(endpoint, 'transport');
  if (!http || Object.hasOwn(operation, 'artifact')) return 'body-declaration-requires-http-endpoint';
  for (const [kind, max] of [['request-body', 'max-request-bytes'], ['response-body', 'max-response-bytes']]) {
    if (Object.hasOwn(operation, kind) !== Object.hasOwn(operation, max)) return 'invalid-body-declaration';
    if (!Object.hasOwn(operation, kind)) continue;
    if (!['bytes', 'text', 'host-local'].includes(operation[kind])) return 'invalid-body-declaration';
    const cap = operation[kind] === 'host-local' ? CLIENT_REFERENCE_BODY_MAX : CLIENT_PORT_BYTES_MAX;
    if (overCap(operation[max], cap)) return 'bytes-limit-over-global-cap';
    if (!limit(operation[max], kind === 'request-body' ? 0 : 1, cap)) return 'invalid-body-declaration';
  }
  if (Object.hasOwn(operation, 'content-type') && (!Object.hasOwn(operation, 'request-body') || typeof operation['content-type'] !== 'string'
      || !/^[a-z0-9][a-z0-9!#$&^_.+-]{0,63}\/[a-z0-9][a-z0-9!#$&^_.+-]{0,63}$/.test(operation['content-type']))) return 'invalid-content-type';
  if (Object.hasOwn(operation, 'timeout-ms') && !limit(operation['timeout-ms'], 1, BODY_DEADLINE_MAX_MS)) return 'invalid-timeout';
  return null;
}
const bodyLimits = (operation) => (Object.hasOwn(operation, 'request-body') || Object.hasOwn(operation, 'response-body') ? Object.freeze({
  request: operation['request-body'] ?? null, 'max-request-bytes': operation['max-request-bytes'] ?? null,
  response: operation['response-body'] ?? null, 'max-response-bytes': operation['max-response-bytes'] ?? null,
  'content-type': operation['content-type'] ?? null, 'timeout-ms': operation['timeout-ms'] ?? BODY_DEADLINE_MAX_MS,
}) : null);

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
  // AWAI-3883: a pending country is shown as unconfirmed, never as a code.
  countryPending: '未確認',
  data: (list) => `送る情報: ${list}`,
  listSeparator: '、',
  purpose: (text) => `目的: ${text}`,
  frequency: (text) => `送る回数: ${text}`,
  once: '1 回だけ',
  continuous: '許可を取り消すまで続けて',
  specialCare: (kinds) => `この中には、${kinds} が含まれます。`,
  restrictedNotice: (withdrawal) => `許可しない場合、この情報は送られません。許可は、あとで ${withdrawal} から取り消せます。`,
  // Legal 2026-11-22 (draft): a one-time operation says the permission is not kept, instead of where to withdraw it.
  restrictedNoticeOnce: '許可しない場合、この情報は送られません。この許可は今回の 1 回だけです。保存しません。',
  onceOnly: 'この許可は今回の 1 回だけです。保存しません。',
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
  // KOTOBA-968: byte limits, save and link prompts. Confirmed by Legal on 2026-11-22, with the save and link notices reworded.
  sendLimit: (size) => `送る大きさの上限: ${size}`,
  receiveLimit: (size) => `受け取る大きさの上限: ${size}`,
  byteSize: (n, unit) => (unit ? `${unit}（${n} バイト）` : `${n} バイト`),
  saveAriaLabel: 'ファイルの保存の確認',
  saveTitle: (app) => `${app} が、ファイルをこの端末に保存しようとしています`,
  saveName: (name) => `ファイル名: ${name}`,
  saveType: (type) => `種類: ${type}`,
  saveSize: (size) => `大きさ: ${size}`,
  saveNotice: '保存先はこの端末です。この操作で、app が外部に何かを送ることはありません。',
  saveDeny: '保存しない',
  saveAllow: '保存する',
  linkAriaLabel: '外部のサイトを開く確認',
  linkTitle: (app) => `${app} が、外部のサイトを開こうとしています`,
  linkOrigin: (origin) => `開く先: ${origin}`,
  linkNotice: 'このサイトは、この端末の外にあります。開くと、端末の IP アドレスなどと、URL に含まれる情報がそのサイトに送られます。URL の全文は「詳細を見る」で確かめられます。',
  linkDeny: '開かない',
  linkAllow: '開く',
  // App QA 2026-11-22 (3): the link details are consistent with linkNotice (not 「送る内容はありません」). Pending Legal.
  linkPayload: 'URL と、端末の IP アドレスなどが送られます。',
  storedResponse: '端末内に保存',
  // KOTOBA-974 (PR 2). All strings confirmed by Legal (reports/kotoba-974-pr2-consent-wording.md, 2026-11-22). The link payload line is not covered and awaits Legal.
  localAriaLabel: '端末の中の AI に渡す確認',
  localTitle: (app) => `${app} が、端末の中の AI を使おうとしています`,
  localFixed: 'この端末の中の AI（Murakumo）に渡します。端末の外には送りません。',
  localPurpose: (text) => `目的: ${text}`,
  localSpecialCare: '病歴などの健康の情報を含みます',
  localStop: 'この機能は、設定 › 端末内の AI でいつでも止められます。',
  localDeny: '渡さない',
  localAllow: '渡す',
  pickAriaLabel: 'ファイルを読み込む確認',
  pickTitle: (app) => `${app} が、この端末のファイルを 1 つ読み込もうとしています`,
  pickTypes: (list) => `読み込める種類: ${list}`,
  pickLimit: (size) => `大きさの上限: ${size}`,
  pickNotice: '次の画面で選んだファイルだけが、この app に渡ります。この操作で、app が外部に何かを送ることはありません。',
  pickDeny: '選ばない',
  pickAllow: 'ファイルを選ぶ',
  openAriaLabel: 'ファイルを別の app で開く確認',
  openTitle: (app) => `${app} が、ファイルをこの端末の別の app で開こうとしています`,
  openNotice: 'この種類のファイルを開く、この端末の既定の app に渡します。この操作で、この app が外部に何かを送ることはありません。開いたあとの扱いは、開いた app の決まりに従います。',
  openDeny: '開かない',
  openAllow: '開く',
  signAriaLabel: '署名の確認',
  signTitle: (app) => `${app} が、この端末の鍵で署名しようとしています`,
  signOperation: (text) => `操作: ${text}`,
  signRecipient: (text) => `相手: ${text}`,
  signAmount: (text) => `金額: ${text}`,
  signDigest: (hex) => `署名する内容の SHA-256: ${hex}`,
  signNotice: '署名すると、この内容をあなたが認めたことの証明になります。内容を確かめてから署名してください。',
  signContinuous: (withdrawal) => `許可すると、同じ操作と相手には、今後は確認せずに署名します。${withdrawal} からいつでも止められます。`,
  signDeny: '署名しない',
  signAllow: '署名する',
});
const CONSENT_TEXT_EN = Object.freeze({
  ariaLabel: 'Confirm sending',
  appFallback: 'This app',
  titleRestricted: (app) => `${app} wants to send the following information`,
  titleTrusted: (app) => `${app} will send the following information`,
  recipient: (name, country) => `Recipient: ${name} (${country})`,
  japan: 'Japan',
  // AWAI-3883: a pending country is shown as unconfirmed, never as a code.
  countryPending: 'Unconfirmed',
  data: (list) => `Information: ${list}`,
  listSeparator: ', ',
  purpose: (text) => `Purpose: ${text}`,
  frequency: (text) => `Frequency: ${text}`,
  once: 'Once',
  continuous: 'Continuously, until you withdraw permission',
  specialCare: (kinds) => `This includes ${kinds}.`,
  restrictedNotice: (withdrawal) => `If you do not allow it, this information will not be sent. You can withdraw your permission at any time in ${withdrawal}. Withdrawing does not affect sending that already took place.`,
  restrictedNoticeOnce: 'If you do not allow it, this information will not be sent. This permission is for this one time only and is not saved.',
  onceOnly: 'This permission is for this one time only and is not saved.',
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
  sendLimit: (size) => `Sends at most: ${size}`,
  receiveLimit: (size) => `Receives at most: ${size}`,
  byteSize: (n, unit) => (unit ? `${unit} (${n} bytes)` : `${n} bytes`),
  saveAriaLabel: 'Confirm saving a file',
  saveTitle: (app) => `${app} wants to save a file on this device`,
  saveName: (name) => `File name: ${name}`,
  saveType: (type) => `Type: ${type}`,
  saveSize: (size) => `Size: ${size}`,
  saveNotice: 'The file is saved on this device. This action does not send anything outside it from the app.',
  saveDeny: "Don't save",
  saveAllow: 'Save',
  linkAriaLabel: 'Confirm opening an external site',
  linkTitle: (app) => `${app} wants to open an external site`,
  linkOrigin: (origin) => `Opens: ${origin}`,
  linkNotice: "This site is outside this device. Opening it sends your device's IP address and similar details, and the information in the URL, to that site. 'View details' shows the whole URL.",
  linkDeny: "Don't open",
  linkAllow: 'Open',
  linkPayload: "The URL and your device's IP address and similar details are sent.",
  storedResponse: 'saved on this device',
  localAriaLabel: 'Confirm passing data to the on-device AI',
  localTitle: (app) => `${app} wants to use the AI on this device`,
  localFixed: 'This is passed to the AI inside this device (Murakumo). It is not sent outside the device.',
  localPurpose: (text) => `Purpose: ${text}`,
  localSpecialCare: 'This includes health information such as medical history.',
  localStop: 'You can turn this off at any time in Settings › On-device AI.',
  localDeny: "Don't pass",
  localAllow: 'Pass',
  pickAriaLabel: 'Confirm reading a file',
  pickTitle: (app) => `${app} wants to read one file from this device`,
  pickTypes: (list) => `Types: ${list}`,
  pickLimit: (size) => `Size limit: ${size}`,
  pickNotice: 'Only the file you choose next is given to this app. This action does not send anything outside the device.',
  pickDeny: "Don't choose",
  pickAllow: 'Choose a file',
  openAriaLabel: 'Confirm opening a file in another app',
  openTitle: (app) => `${app} wants to open a file in another app on this device`,
  openNotice: "The file is given to this device's default app for its type. This action does not send anything outside the device. After that, the app that opens it handles it under its own rules.",
  openDeny: "Don't open",
  openAllow: 'Open',
  signAriaLabel: 'Confirm signing',
  signTitle: (app) => `${app} wants to sign with a key on this device`,
  signOperation: (text) => `Operation: ${text}`,
  signRecipient: (text) => `Recipient: ${text}`,
  signAmount: (text) => `Amount: ${text}`,
  signDigest: (hex) => `SHA-256 of what is signed: ${hex}`,
  signNotice: 'A signature proves that you approved this content. Check it before you sign.',
  signContinuous: (withdrawal) => `If you allow this, the same operation for the same recipient is signed from now on without asking. You can stop it at any time in ${withdrawal}.`,
  signDeny: "Don't sign",
  signAllow: 'Sign',
});
export const CLIENT_CONSENT_TEXT = Object.freeze({
  status: 'confirmed', source: 'Legal reports/kotoba-974-pr2-consent-wording.md, 2026-11-22',
  ja: CONSENT_TEXT_JA, en: CONSENT_TEXT_EN,
});

// R5 / D4: a value longer than this is cut, with its length and the 全文 toggle shown.
const CONSENT_VALUE_MAX = 160;
// The full payload text shown behind 詳細 > 全文 is capped so a large body cannot freeze the host tab.
const CONSENT_PAYLOAD_TEXT_MAX = 65536;
const present = (value) => typeof value === 'string' && value.length > 0;

// A byte count for people: 12 MiB (12582912 bytes). Units are binary and exact to one decimal.
function byteText(n, T) {
  const unit = n >= 1048576 ? `${Number((n / 1048576).toFixed(1))} MiB` : n >= 1024 ? `${Number((n / 1024).toFixed(1))} KiB` : null;
  return T.byteSize(n, unit);
}
/** The first screen (finding 9, Legal draft): [title, list lines, paragraphs]. Missing values drop their line. */
function consentFirstScreen(details, T) {
  if (details.kind === 'save') {
    const app = present(details.app?.name) ? details.app.name : T.appFallback;
    return [T.saveTitle(app), [T.saveName(details.save.name), T.saveType(details.save.type), T.saveSize(byteText(details.save.bytes, T))], [T.saveNotice]];
  }
  if (details.kind === 'link') {
    const app = present(details.app?.name) ? details.app.name : T.appFallback;
    return [T.linkTitle(app), [T.linkOrigin(details.link.origin)], [T.linkNotice]];
  }
  const appName = present(details.app?.name) ? details.app.name : T.appFallback;
  // KOTOBA-974: Legal's short device-local confirmation (not the egress dialog), one time each.
  if (details.kind === 'device-local') {
    return [T.localTitle(appName), [T.localPurpose(details.deviceLocal.purpose), T.frequency(T.once)],
      [T.localFixed, ...(details.deviceLocal.specialCare ? [T.localSpecialCare] : []), T.onceOnly, T.localStop]];
  }
  if (details.kind === 'pick') return [T.pickTitle(appName), [T.pickTypes(details.pick.types.join(T.listSeparator)), T.pickLimit(byteText(details.pick.limit, T))], [T.pickNotice]];
  if (details.kind === 'open') return [T.openTitle(appName), [T.saveName(details.open.name), T.saveType(details.open.type), T.saveSize(byteText(details.open.bytes, T))], [T.openNotice]];
  if (details.kind === 'sign') {
    const d = details.sign;
    return [T.signTitle(appName), [T.signOperation(d.operation), T.signRecipient(d.recipient), ...(present(d.amount) ? [T.signAmount(d.amount)] : []), T.signDigest(d.sha256)],
      [T.signNotice, d.continuous ? T.signContinuous(d.withdrawal) : T.onceOnly]];
  }
  const d = details.disclosure;
  const trusted = details.profile !== 'restricted-wasm-v1';
  const app = present(details.app?.name) ? details.app.name : T.appFallback;
  // AWAI-3883: pending = unconfirmed country (null code); show 未確認/Unconfirmed, no code, no foreign line.
  const pending = d.countryStatus === 'pending';
  const foreign = !pending && d.country !== 'JP';
  const country = pending ? T.countryPending : foreign ? d['country-name'] : T.japan;
  // Both profiles show the same declared facts (Itonami, AWAI-3819); only the notice differs.
  const lines = [
    T.recipient(d.recipient, country),
    T.data(d.data.join(T.listSeparator)),
    T.purpose(d.purpose),
    ...(present(d.frequency) ? [T.frequency(d.frequency === 'continuous' ? T.continuous : T.once)] : []),
    // KOTOBA-968: declared body limits are shown on the first screen.
    ...(Number.isSafeInteger(details.bytes?.['max-request-bytes']) ? [T.sendLimit(byteText(details.bytes['max-request-bytes'], T))] : []),
    ...(Number.isSafeInteger(details.bytes?.['max-response-bytes']) ? [T.receiveLimit(byteText(details.bytes['max-response-bytes'], T))] : []),
  ];
  const foreignLine = foreign && present(d['country-name']) && present(d['foreign-info-url']);
  const once = d.frequency === 'one-time';
  const paragraphs = [
    ...(d['special-care'] ? [T.specialCare(d['special-care-kinds'].join(T.listSeparator))] : []),
    // The app's optional note: plain text, shown as written (textContent, never parsed).
    ...(present(d.note) ? [d.note] : []),
    ...(details.scope === 'lan' ? [T.lan] : []),
    ...(trusted
      ? [
        ...(once ? [T.onceOnly] : present(d.withdrawal) ? [T.trustedWithdrawal(d.withdrawal)] : []),
        ...(foreignLine ? [T.trustedForeign(country, d['foreign-info-url'])] : []),
        ...(present(details.app?.provider) && present(details.app?.['privacy-policy']) ? [T.trustedProvider(details.app.provider, details.app['privacy-policy'])] : []),
        T.trustedNotice]
      : [once ? T.restrictedNoticeOnce : T.restrictedNotice(d.withdrawal), ...(foreignLine ? [T.foreign(country, d['foreign-info-url'])] : [])]),
  ];
  return [trusted ? T.titleTrusted(app) : T.titleRestricted(app), lines, paragraphs];
}
// Plain text of a paragraph, for hosts without DOM nodes (and tests): a link shows its URL.
const paragraphText = (paragraph) => (typeof paragraph === 'string' ? paragraph
  : paragraph.map((part) => (typeof part === 'string' ? part : `${part.link}（${part.href}）`)).join(''));

// Technical scope behind 詳細. Fixed declared fields come before the guest-chosen Action (R5, D4).
function consentScopeEntries(details, T) {
  if (details.kind === 'link') {
    return [['Call', 'device.openLink (system browser, no opener)'], ['Destination origin', details.link.origin], ['URL', details.link.url, true]];
  }
  if (details.kind === 'device-local') {
    return [['Call', 'device.command (on this device; no network; not logged)'], ['Command', details.deviceLocal.command], ['Action', details.deviceLocal.action]];
  }
  if (details.kind === 'pick') return [['Call', 'device.pick (OS file chooser; no network)'], ['Types', details.pick.types.join(', ')], ['Size limit', `${details.pick.limit} bytes`]];
  if (details.kind === 'open') {
    return [['Call', 'device.open (default app on this device; no network)'], ['File name', details.open.name, true], ['Content type', details.open.type],
      ['Size', `${details.open.bytes} bytes`], ['Declared open limit', `${details.open.limit} bytes`]];
  }
  if (details.kind === 'sign') {
    const d = details.sign;
    return [['Call', 'keys.sign (host-held key; signs the statement shown here)'], ['Key', d.key], ['Operation', d.operation, true], ['Recipient', d.recipient, true],
      ...(present(d.amount) ? [['Amount', d.amount, true]] : []), ['Payload SHA-256', d.sha256], ['Payload size', `${d.bytes} bytes`],
      ['Signed statement', 'kotoba.key-approval.v1: app, key, operation, recipient, amount, payload-sha256'], ['Approval', d.continuous ? 'continuous for this operation and recipient, until stopped' : 'this time only']];
  }
  if (details.kind === 'save') {
    return [['Call', 'device.save (host prompt; no network)'], ['File name', details.save.name, true], ['Content type', details.save.type],
      ['Size', `${details.save.bytes} bytes`], ['Declared save limit', `${details.save.limit} bytes`]];
  }
  const peer = details.peerEndpoint; const nearby = details.nearbyEndpoint;
  const action = nearby?.action ?? peer?.action ?? details.browserAction ?? `${details.endpointMethod} ${details.endpointPath}${details.endpointSearch}`;
  return [
    ['Service', details.service], ['Operation', details.operation], ['Capability', details.capability],
    ['Endpoint', details.endpointOrigin],
    ...(details.userSelectedApp ? [['Receiver', 'the app you pick next receives the data and handles it under its own rules']] : []),
    ['Data categories', details.dataCategories.join(', ') || '(none)'],
    ['Delivery redirects', details.redirectOrigins.join(', ') || '(none)'],
    ['Network scope', details.scope === 'lan' ? 'lan (local network or this device)' : 'public'],
    ...(details.oauth ? [['OAuth', `${details.oauth.step}: ${details.oauth.issuer}, scope ${details.oauth.scope} (PKCE S256, state, DPoP ES256; the tokens and the DPoP key stay in the host)`, true],
      ['Client', details.oauth.clientId, true], ['Redirect', details.oauth.redirectUri, true]] : []),
    ...(details.oauthSession ? [['Authorization', `OAuth session ${details.oauthSession} (DPoP; the host adds the token and proof after you allow)`]] : []),
    ...(Number.isSafeInteger(details.bytes?.['max-request-bytes']) ? [['Request body', `${details.bytes.request === 'host-local' ? 'read from this app\'s storage on this device' : details.bytes.request}, at most ${details.bytes['max-request-bytes']} bytes${details.bytes['content-type'] ? `, ${details.bytes['content-type']}` : ''}`]] : []),
    ...(details.storedBody ? [['Body from storage', `${details.storedBody.store}: ${details.storedBody.keys.length} value(s), ${details.storedBody.bytes} bytes, ${details.storedBody.upload === 'stream' ? 'streamed' : 'buffered by the host'}`, true]] : []),
    ...(details.storeResponse ? [['Response written to', `this app's storage on this device: ${details.storeResponse.store}/${details.storeResponse.key}`, true]] : []),
    ...(Number.isSafeInteger(details.bytes?.['max-response-bytes']) ? [['Response body', `${details.bytes.response === 'host-local' ? T.storedResponse : details.bytes.response}, at most ${details.bytes['max-response-bytes']} bytes (a larger response is cut off and refused)`]] : []),
    ...(details.bytes ? [['Body deadline', `${details.bytes['timeout-ms']} ms`]] : []),
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
    ...(payload.sha256 ? [`${T.payloadDigest}: ${payload.sha256}`] : []),
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
  // App QA r2: the cycle is every focusable descendant in DOM order (links included), skipping
  // disabled and hidden controls and the inside of a closed <details> other than its <summary>.
  const focusable = (node) => {
    const tag = String(node.tagName ?? '').toLowerCase();
    if (node.disabled || node.hidden) return false;
    return (tag === 'a' && !!node.href) || tag === 'summary' || tag === 'button' || (typeof node.tabIndex === 'number' && node.tabIndex >= 0 && tag !== 'h2');
  };
  const focusOrder = () => {
    const order = [];
    const walk = (node) => {
      for (const child of Array.from(node.children ?? [])) {
        if (child.hidden) continue;
        if (focusable(child)) order.push(child);
        const tag = String(child.tagName ?? '').toLowerCase();
        if (tag === 'details' && !child.open) { for (const inner of Array.from(child.children ?? [])) if (String(inner.tagName ?? '').toLowerCase() === 'summary' && !order.includes(inner)) order.push(inner); continue; }
        walk(child);
      }
    };
    walk(dialog);
    // A host DOM without element children (some test doubles) falls back to the fixed controls.
    return order.length ? order : [moreLabel, ...(more.open && !fullToggle.hidden ? [fullToggle] : []), deny, ...(allow.disabled ? [] : [allow])];
  };
  dialog.addEventListener('keydown', (event) => {
    if (event.key !== 'Tab' || !dialog.open) return;
    const order = focusOrder();
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
        link.textContent = part.link; link.href = part.href; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.tabIndex = 0;
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
  // KOTOBA-968: a host effect (the save) that runs inside the trusted Allow click, before the promise settles.
  let pendingEffect = null;
  let destroyed = false;
  let shown = null; let full = false;
  function render() {
    if (!shown) return;
    const [scopeText, scopeCut] = renderEntries(consentScopeEntries(shown, T), full, T);
    // App QA 2026-11-22 (3): a link sends the URL and the IP address, and a device-local call passes its input to
    // the on-device AI, so neither says that nothing is sent.
    const [payloadText, payloadCut] = shown.kind === 'link' ? [T.linkPayload, false] : shown.kind === 'device-local' ? [T.localFixed, false] : renderPayload(shown.payload, full, T);
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
    const effect = pendingEffect; pendingEffect = null;
    if (pendingAbort) { pendingAbort(); pendingAbort = null; }
    if (approved && effect) {
      // The effect is host code. If it fails, the request counts as not approved; its error is not shown or echoed.
      try { effect(); } catch { approved = false; }
    }
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
  consentHosts.set(handle, async (details, signal, onApproved = null) => {
    if (signal?.aborted) return false;
    if (onApproved !== null && typeof onApproved !== 'function') throw new TypeError('invalid consent effect');
    if (destroyed || pending || !dialog.isConnected) throw new Error('trusted consent UI is unavailable or busy');
    // First screen: the declared disclosure (finding 9), the LAN scope (finding 8) and the profile
    // notice (finding 1), in the draft wording. The technical scope and the payload stay behind 詳細.
    const [heading, lines, paragraphs] = consentFirstScreen(details, T);
    title.textContent = heading;
    listItems(lines);
    paragraphsOf(paragraphs);
    const restricted = details.profile === 'restricted-wasm-v1';
    // KOTOBA-974: each host prompt names its own action on equal buttons.
    const prompt = { save: 'save', link: 'link', 'device-local': 'local', pick: 'pick', open: 'open', sign: 'sign' }[details.kind] ?? null;
    dialog.setAttribute('aria-label', prompt ? T[`${prompt}AriaLabel`] : T.ariaLabel);
    deny.textContent = prompt ? T[`${prompt}Deny`] : restricted ? T.deny : T.close;
    allow.textContent = prompt ? T[`${prompt}Allow`] : restricted ? T.allow : T.continue;
    shown = details; full = false; more.open = false;
    render();
    return new Promise((resolve, reject) => {
      pending = resolve; pendingEffect = onApproved;
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
      catch (error) { pending = null; pendingEffect = null; if (pendingAbort) { pendingAbort(); pendingAbort = null; } disarm(); reject(error); }
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
export async function mountRestrictedClientApp({ artifact, container, broker, hostLocal = null }) {
  // R4: only a broker made by createClientOperationBroker (which always asks the trusted consent host)
  // is mounted. There is no exported way to register another object.
  if (!verifiedArtifacts.has(artifact) || !(container instanceof globalThis.HTMLElement)
      || !canonicalBrokers.has(broker)) throw new TypeError('verified app artifact and trusted host broker required');
  // KOTOBA-968: host-local calls only from createClientHostLocal, for the same descriptor as the broker.
  const local = hostLocal === null ? null : canonicalHostLocals.get(hostLocal);
  if (hostLocal !== null && (!local || local.descriptor !== brokerDescriptors.get(broker))) throw new TypeError('host-local calls must come from createClientHostLocal for the broker descriptor');
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
  // Results that carry bytes are transferred, not copied; every buffer is a fresh copy made by the host.
  const post = (message) => {
    const transfer = [];
    const walk = (value, depth) => {
      if (value instanceof Uint8Array) { if (value.byteOffset === 0 && value.byteLength === value.buffer.byteLength && !transfer.includes(value.buffer)) transfer.push(value.buffer); return; }
      if (depth < 4 && record(value)) for (const child of Object.values(value)) walk(child, depth + 1);
    };
    walk(message, 0);
    channel.port1.postMessage(message, transfer);
  };
  channel.port1.onmessage = async ({ data }) => {
    if (closed) return;
    if (record(data) && data.protocol === CLIENT_LOCAL_PROTOCOL) {
      // KOTOBA-968 host-local call. Errors are fixed codes only (Legal L2).
      if (!exactKeys(data, ['protocol', 'id', 'call', 'args']) || !validName(data.id)) return;
      try {
        if (!local) throw localError('not-declared');
        const result = await local.dispatch(data.call, data.args, lifetime.signal,
          (event) => { if (!closed) channel.port1.postMessage({ protocol: CLIENT_LOCAL_PROTOCOL, ...event }); });
        if (!closed) post({ id: data.id, ok: true, result: result ?? null });
      } catch (error) { if (!closed) channel.port1.postMessage({ id: data.id, ok: false, error: error instanceof ClientLocalError ? error.message : 'unavailable' }); }
      return;
    }
    // A declared binary request body may be a byte array; everything else in an operation message is plain data.
    const body = record(data) && record(data.payload) && record(data.payload.init) && Object.hasOwn(data.payload.init, 'body') ? data.payload.init.body : undefined;
    const bodyFree = body === undefined ? data : { ...data, payload: { ...data.payload, init: { ...data.payload.init, body: null } } };
    if (!plainData(bodyFree) || !(body === undefined || body === null || typeof body === 'string' || isBytes(body) || (record(body) && plainData(body)))
        || !exactKeys(data, ['protocol', 'id', 'selector', 'payload'])
        || data.protocol !== 'kotoba.client.operation.v1' || !validName(data.id)) return;
    try {
      const result = await broker.invoke(data.selector, data.payload, { signal: lifetime.signal });
      if (closed) return;
      if (bodyResults.has(result)) {
        // KOTOBA-968: a declared response body, already bounded by the broker: bytes or text.
        post({ id: data.id, ok: true, status: result.status, headers: { ...result.headers },
          ...(Object.hasOwn(result, 'bytes') ? { bytes: result.bytes } : Object.hasOwn(result, 'stored') ? { stored: { ...result.stored } } : { content: result.content }) });
      } else if (result instanceof Response) {
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
  const admitted = Object.freeze({ runtime: freezeClone(runtime), revision, digest, publicKey });
  admittedDescriptors.add(admitted);
  return admitted;
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

// KOTOBA-968: the body of an operation that declares response-body. A declared Content-Length over the limit is refused
// before reading; otherwise the body is read up to the limit and the stream is cancelled past it.
const BYTES_RESPONSE_HEADERS = ['content-type', 'content-length', 'content-range', 'etag', 'last-modified'];
const bodyResults = new WeakSet();
async function boundedBodyResponse(response, limits, signal) {
  const maxBytes = limits['max-response-bytes'];
  const declared = response.headers?.get?.('content-length');
  if (declared !== null && declared !== undefined && /^\d+$/.test(declared) && Number(declared) > maxBytes) {
    discardBody(response); throw new Error('response exceeds declared byte budget');
  }
  let bytes;
  try { bytes = response.body ? await boundedBytes(response.body, maxBytes, limits['timeout-ms'], signal) : new Uint8Array(); }
  catch (error) { discardBody(response); throw String(error?.message).includes('byte budget') ? new Error('response exceeds declared byte budget') : error; }
  const headers = {};
  for (const name of BYTES_RESPONSE_HEADERS) { const value = response.headers?.get?.(name); if (typeof value === 'string') headers[name] = value.slice(0, 512); }
  let content = null;
  if (limits.response === 'text') {
    try { content = new TextDecoder('utf-8', { fatal: true }).decode(bytes); } catch { throw new Error('response is not UTF-8 text'); }
  }
  const result = Object.freeze({ status: response.status, ok: response.ok === true, headers: Object.freeze(headers),
    ...(content === null ? { bytes } : { content }) });
  bodyResults.add(result);
  return result;
}

// KOTOBA-968: bodies by reference. A request body names stored values of this app: { 'host-local': { store,
// keys } } (in order). Before consent only their sizes and versions are read (no value is decrypted), and the total
// is checked against max-request-bytes. After consent each value is read, checked against the version that was
// approved and streamed into the request one at a time, so the whole body is never held in memory (Yataverse
// review (c)). A value that changed after approval stops the request.
async function planStoredBody(link, body, maxBytes) {
  const ref = record(body) ? body['host-local'] : null;
  if (!exactKeys(body, ['host-local']) || !exactKeys(ref, ['store', 'keys']) || !link.declaration.stores.includes(ref.store)
      || !Array.isArray(ref.keys) || ref.keys.length === 0 || ref.keys.length > 4096 || !ref.keys.every(validStorageKey)) {
    throw new TypeError('a stored request body names a declared store and its keys');
  }
  const names = ref.keys.map((key) => `${ref.store}/${key}`);
  const usage = await link.core.run(() => link.core.load());
  let bytes = 0;
  const versions = [];
  for (const full of names) {
    if (!usage.has(full)) throw new Error('a stored request body value was not found');
    bytes += usage.get(full).size - utf8Length(full);
    versions.push(usage.get(full).version);
  }
  if (bytes > maxBytes) throw new Error('body exceeds declared byte budget');
  return Object.freeze({ names: Object.freeze(names), versions: Object.freeze(versions), bytes, store: ref.store, keys: Object.freeze([...ref.keys]) });
}
// Can this engine send a ReadableStream as a request body (duplex 'half')? WebKit cannot. Chromium can, but only
// over HTTP/2 or later, which the host attests with uploadStreams.
function requestStreamsSupported() {
  try {
    let duplexAccessed = false;
    const probe = new Request('https://upload-stream.invalid/', { method: 'POST', body: new ReadableStream(), get duplex() { duplexAccessed = true; return 'half'; } });
    return duplexAccessed && !probe.headers.has('content-type');
  } catch { return false; }
}
// After consent: read each value, check it against the approved version, then stream it (one value at a time)
// or buffer it in the host (bounded by max-request-bytes and CLIENT_UPLOAD_BUFFER_MAX), as chosen before consent.
async function storedBodyRequest(approved, plan, link, maxBytes) {
  const readValue = async (index) => {
    let found;
    try { found = await link.core.run(() => link.core.read(plan.names[index])); } catch { throw new Error('a stored request body could not be read'); }
    if (!found || found.version !== plan.versions[index]) throw new Error('a stored request body changed after approval');
    return found.value;
  };
  const init = { method: approved.method, headers: approved.headers, credentials: 'omit', referrerPolicy: 'no-referrer', redirect: approved.redirect, mode: 'cors', cache: 'no-store', signal: approved.signal };
  if (plan.upload === 'buffer') {
    const parts = []; let sent = 0;
    for (let index = 0; index < plan.names.length; index++) {
      if (approved.signal?.aborted) throw new Error('client operation cancelled');
      const value = await readValue(index);
      sent += value.byteLength;
      if (sent > maxBytes || sent > CLIENT_UPLOAD_BUFFER_MAX) throw new Error('body exceeds declared byte budget');
      parts.push(value);
    }
    return new Request(approved.url, { ...init, body: new Blob(parts) });
  }
  let next = 0; let sent = 0;
  const stream = new ReadableStream({
    async pull(controller) {
      if (approved.signal?.aborted) { controller.error(new Error('client operation cancelled')); return; }
      if (next >= plan.names.length) { controller.close(); return; }
      try {
        const value = await readValue(next++);
        sent += value.byteLength;
        if (sent > maxBytes) throw new Error('body exceeds declared byte budget');
        controller.enqueue(value);
      } catch (error) { controller.error(error); }
    },
  }, { highWaterMark: 0 });
  return new Request(approved.url, { ...init, body: stream, duplex: 'half' });
}
function storedBodyTarget(link, target) {
  if (!exactKeys(target, ['store', 'key']) || !link.declaration.stores.includes(target.store) || !validStorageKey(target.key) || target.key.length > 1000) {
    throw new TypeError('store-response names a declared store and a key');
  }
  return Object.freeze({ store: target.store, key: target.key });
}
// A response written to storage: chunks of max-value-bytes under `${key}/000000`, …, then a manifest at `key`
// (the commit marker: { schema, bytes, chunks, sha256, content-type }). Over the limit, at the deadline, on
// cancellation or a failed write, the stream is cancelled and the chunks written so far are deleted.
async function storeBodyResponse(response, limits, link, target, signal) {
  const maxBytes = limits['max-response-bytes'];
  const declared = response.headers?.get?.('content-length');
  if (declared !== null && declared !== undefined && /^\d+$/.test(declared) && Number(declared) > maxBytes) { discardBody(response); throw new Error('response exceeds declared byte budget'); }
  const storage = link.declaration.storage;
  const chunkSize = storage['max-value-bytes'];
  const written = []; const hash = createSha256(); let total = 0; let buffer = new Uint8Array(0);
  const write = async (full, value) => { await link.core.run(() => link.core.commit([{ put: { key: full, value } }], storage)); };
  const flush = async (chunk) => {
    const full = `${target.store}/${target.key}/${String(written.length).padStart(6, '0')}`;
    await write(full, chunk); written.push(full);
  };
  const reader = response.body ? response.body.getReader() : null;
  let timer; let onAbort;
  const deadline = new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('body deadline exceeded')), limits['timeout-ms']); });
  const cancelled = signal && new Promise((_, reject) => { onAbort = () => reject(new Error('client operation cancelled')); signal.addEventListener('abort', onAbort, { once: true }); if (signal.aborted) onAbort(); });
  try {
    while (reader) {
      const { done, value } = await Promise.race(cancelled ? [reader.read(), deadline, cancelled] : [reader.read(), deadline]);
      if (done) break;
      total += value.byteLength;
      if (total > maxBytes) throw new Error('response exceeds declared byte budget');
      hash.update(value);
      const joined = new Uint8Array(buffer.byteLength + value.byteLength); joined.set(buffer); joined.set(value, buffer.byteLength); buffer = joined;
      while (buffer.byteLength >= chunkSize) { const chunk = buffer.slice(0, chunkSize); buffer = buffer.slice(chunkSize); await flush(chunk); }
    }
    if (buffer.byteLength > 0 || written.length === 0) await flush(buffer);
    const sha256 = hash.hex();
    const manifest = { schema: 'kotoba.host-local.stored-body.v1', bytes: total, chunks: written.length, sha256, 'content-type': (response.headers?.get?.('content-type') ?? '').slice(0, 128) };
    await write(`${target.store}/${target.key}`, new TextEncoder().encode(JSON.stringify(manifest)));
    const headers = {};
    for (const name of BYTES_RESPONSE_HEADERS) { const value = response.headers?.get?.(name); if (typeof value === 'string') headers[name] = value.slice(0, 512); }
    const result = Object.freeze({ status: response.status, ok: response.ok === true, headers: Object.freeze(headers),
      stored: Object.freeze({ store: target.store, key: target.key, bytes: total, chunks: written.length, sha256 }) });
    bodyResults.add(result);
    return result;
  } catch (error) {
    try { await reader?.cancel(); } catch { /* already closed */ }
    discardBody(response);
    if (written.length) { try { await link.core.run(() => link.core.commit(written.map((key) => ({ delete: { key } })), storage)); } catch { /* left for the app's orphan sweep */ } }
    throw error instanceof ClientLocalError ? new Error(`stored response failed: ${error.message}`) : error;
  } finally { clearTimeout(timer); if (onAbort) signal.removeEventListener('abort', onAbort); }
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
  const { runtime, requestedCapabilities = [], approvedOperations = [], hostSupportedOperations = [], browserAdapters = {}, peerAdapters = {}, artifactSinks = {}, consentHost, app = null, hostLocal = null, uploadStreams = false } = options;
  // uploadStreams: the host attests that its declared targets accept streamed request bodies (HTTP/2 or later)
  // and that its engine supports them. Without it, a stored request body is buffered (up to 256 MiB).
  if (typeof uploadStreams !== 'boolean') throw new TypeError('uploadStreams must be a boolean');
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
  // KOTOBA-968: bodies by reference read from / write to this app's host-local storage only.
  const storageLink = hostLocal === null ? null : canonicalHostLocals.get(hostLocal)?.storage ?? null;
  // KOTOBA-974: OAuth sessions held by this app's host-local handle (tokens and DPoP key stay in the host).
  const keyLink = hostLocal === null ? null : canonicalHostLocals.get(hostLocal)?.keys ?? null;
  if (hostLocal !== null && (canonicalHostLocals.get(hostLocal)?.descriptor !== canonical(descriptor))) throw new TypeError('hostLocal must come from createClientHostLocal for this descriptor');
  const fetchRequest = globalThis.fetch.bind(globalThis);
  let slotTaken = false;
  let inflightBytes = 0; let referenceBytes = 0;
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
      // KOTOBA-968: a binary operation reserves its declared request + response bytes before any body is read.
      const bytesLimits = bodyLimits(operation);
      // Bodies by reference have their own budget (one 1 GiB transfer at a time); the rest share 32 MiB.
      const byReference = (kind) => operation[kind] === 'host-local';
      const reserved = bytesLimits ? (byReference('request-body') ? 0 : bytesLimits['max-request-bytes'] ?? 0) + (byReference('response-body') ? 0 : bytesLimits['max-response-bytes'] ?? 0) : 0;
      const referenced = bytesLimits ? (byReference('request-body') ? bytesLimits['max-request-bytes'] : 0) + (byReference('response-body') ? bytesLimits['max-response-bytes'] : 0) : 0;
      if (reserved > 0 && inflightBytes + reserved > BYTES_INFLIGHT_MAX) throw new Error('the byte budget for binary operations is in use');
      if (referenced > 0 && referenceBytes + referenced > CLIENT_REFERENCE_BODY_MAX) throw new Error('the byte budget for stored bodies is in use');
      if (referenced > 0 && !storageLink) throw new Error('host-local storage is not available to this broker');
      slotTaken = true; inflightBytes += reserved; referenceBytes += referenced;
      let storedBody = null; let storeTarget = null; let oauthSession = null;
      try {
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
            // The target of a stored response is checked, and shown, before consent.
            if (record(payload) && Object.hasOwn(payload, 'store-response') !== byReference('response-body')) throw new TypeError('store-response is required exactly when the response body is declared host-local');
            if (byReference('response-body')) storeTarget = storedBodyTarget(storageLink, payload['store-response']);
            if (byReference('request-body')) {
              storedBody = await planStoredBody(storageLink, payload?.init?.body, bytesLimits['max-request-bytes']);
              // Choose how the body will be sent now, so the request never fails after consent for a reason known before it.
              const upload = uploadStreams && requestStreamsSupported() ? 'stream' : bytesLimits['max-request-bytes'] <= CLIENT_UPLOAD_BUFFER_MAX ? 'buffer' : null;
              if (!upload) throw new Error('this host cannot stream an upload, and the declared body is larger than it buffers');
              storedBody = Object.freeze({ ...storedBody, upload });
            }
            // KOTOBA-974: an OAuth-authorized request names its host session; the guest never sets the token or proof.
            if (operation.oauth) {
              if (!keyLink || byReference('request-body')) throw new Error('an OAuth session is not available to this broker');
              try { oauthSession = oauthSessionFor(keyLink, signal, payload?.session, operation.oauth); } catch { throw new Error('the OAuth session is not valid for this app'); }
            }
            const captured = await prepareRequest(operation, payload, signal, storedBody);
            if (operation.oauth && (captured.headers.has('authorization') || captured.headers.has('dpop'))) throw new Error('the host adds the OAuth authorization; the app may not');
            approvedPayload = captured.snapshot;
            request = endpointRequest(approvedPayload, endpointOrigin);
            if (!request || request.hasCredentials || !endpointRequestMatches(operation.endpoint, approvedPayload, endpointOrigin)) throw new Error('request scope changed while snapshotting');
            summary = storedBody
              ? Object.freeze({ contentType: captured.headers.get('content-type') ?? '', bytes: storedBody.bytes, sha256: null, fields: Object.freeze([]), text: null, headers: Object.freeze([...captured.headers.keys()]) })
              : payloadSummary(captured.body ?? new Uint8Array(), captured.headers.get('content-type') ?? '', [...captured.headers.keys()]);
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
            artifact: operation.artifact ? freezeClone(operation.artifact) : null, bytes: bytesLimits,
            storedBody: storedBody ? Object.freeze({ store: storedBody.store, keys: storedBody.keys, bytes: storedBody.bytes, upload: storedBody.upload }) : null,
            storeResponse: storeTarget ? Object.freeze({ store: storeTarget.store, key: storeTarget.key }) : null,
            oauthSession: oauthSession ? operation.oauth : null,
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
        // No init: the approved Request already carries its signal, referrer policy and options. A body by
        // reference is streamed from storage now, one value at a time (Yataverse review (c)).
        let result;
        if (oauthSession) {
          // After consent the host adds `Authorization: DPoP <token>` and a fresh ES256 proof (htm, htu, ath, nonce),
          // retrying once when the server asks for a DPoP nonce (RFC 9449).
          const base = approvedPayload.input;
          const body = base.body ? new Uint8Array(await base.clone().arrayBuffer()) : null;
          const authorized = async () => {
            const headers = new Headers(base.headers);
            headers.set('authorization', `DPoP ${oauthSession.access}`);
            headers.set('dpop', await dpopProof(oauthSession, base.method, base.url, oauthSession.access));
            return new Request(base.url, { method: base.method, headers, ...(body ? { body } : {}), credentials: 'omit', referrerPolicy: 'no-referrer', redirect: base.redirect, mode: 'cors', cache: 'no-store', signal: base.signal });
          };
          result = await fetchRequest(await authorized());
          const nonce = result.headers.get('dpop-nonce');
          if (result.status === 401 && nonce && /^[\x21-\x7e]{1,256}$/.test(nonce) && /use_dpop_nonce/.test(result.headers.get('www-authenticate') ?? '')) {
            oauthSession.nonces.set(new URL(base.url).origin, nonce);
            discardBody(result);
            result = await fetchRequest(await authorized());
          } else if (nonce && /^[\x21-\x7e]{1,256}$/.test(nonce)) oauthSession.nonces.set(new URL(base.url).origin, nonce);
        } else result = await fetchRequest(storedBody ? await storedBodyRequest(approvedPayload.input, storedBody, storageLink, bytesLimits['max-request-bytes']) : approvedPayload.input);
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
        if (storeTarget) return storeBodyResponse(result, bytesLimits, storageLink, storeTarget, signal);
        if (bytesLimits?.response) return boundedBodyResponse(result, bytesLimits, signal);
        return result;
      } finally {
        inflightBytes -= reserved; referenceBytes -= referenced;
      }
    },
  });
  canonicalBrokers.add(broker);
  brokerDescriptors.set(broker, canonical(descriptor));
  return broker;
}

// ---- KOTOBA-968: host-local calls for restricted-wasm-v1 guests (storage, device.save) ----
// A host-local call never reaches the network. Storage needs no consent (nothing leaves the device, Legal
// 2026-11-22); device.save asks the trusted host prompt and runs only inside its trusted click.
// Guest protocol: { protocol: 'kotoba.client.local.v1', id, call, args } -> { id, ok: true, result } or
// { id, ok: false, error } with a fixed code. A code never carries a key, value, file name or content (L2).
export const CLIENT_LOCAL_PROTOCOL = 'kotoba.client.local.v1';
export const CLIENT_LOCAL_ERRORS = Object.freeze(['not-declared', 'invalid-key', 'invalid-arguments', 'not-found', 'key-exists',
  'version-conflict', 'too-large', 'quota-exceeded', 'busy', 'unavailable', 'not-approved']);
// Calls this runtime implements. A declared call outside this list is refused as not-declared.
const LOCAL_IMPLEMENTED = new Set(CLIENT_HOST_LOCAL_CALLS);
const KEY_CALL = (call) => call.startsWith('keys.') || call.startsWith('crypto.');
class ClientLocalError extends Error {}
const localError = (code) => new ClientLocalError(code);
const admittedDescriptors = new WeakSet();
const canonicalHostLocals = new WeakMap();
const brokerDescriptors = new WeakMap();
const STORAGE_PENDING_MAX = 16;
// Total bytes the queued calls of one app may hold at once (Yataverse review (b)): two full batches.
const STORAGE_PENDING_BYTES_MAX = 2 * 4 * 16777216;
const BATCH_OPS_MAX = 1000;
const BATCH_BYTES_MAX = 4 * CLIENT_PORT_BYTES_MAX;
const LIST_LIMIT_MAX = 1000;
const WATCHES_MAX = 16;
// Change notices per app id: every mount of the app in this document, and (BroadcastChannel) the host's
// other tabs of the same origin. A notice names the store and keys only, never a value.
const localWatchers = new Map();
const localChannels = new Map();
function changeChannel(appId) {
  if (typeof globalThis.BroadcastChannel !== 'function') return null;
  if (!localChannels.has(appId)) {
    const channel = new globalThis.BroadcastChannel(`kotoba.client.local.v1:${appId}`);
    channel.onmessage = ({ data }) => { if (record(data) && Array.isArray(data.keys)) deliverChange(appId, data.keys, true); };
    channel.unref?.();
    localChannels.set(appId, channel);
  }
  return localChannels.get(appId);
}
function deliverChange(appId, keys, remote) {
  for (const watcher of localWatchers.get(appId) ?? []) watcher(keys, remote);
}
function announceChange(appId, keys) {
  if (keys.length === 0) return;
  deliverChange(appId, keys, false);
  try { changeChannel(appId)?.postMessage({ keys }); } catch { /* no other tabs */ }
}
const utf8Length = (text) => new TextEncoder().encode(text).length;

// A storage key is a relative path: 1..1024 characters, no control, bidi or zero-width characters, no
// backslash, no leading slash, no empty, `.` or `..` segment. The host never treats it as a file path.
function validStorageKey(key) {
  return typeof key === 'string' && key.length > 0 && key.length <= 1024 && !key.startsWith('/') && !key.includes('\\')
    && !/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2066-\u2069\ufeff]/.test(key)
    && key.split('/').every((segment) => segment !== '' && segment !== '.' && segment !== '..');
}

// Bytes a guest hands over: a Uint8Array over an ordinary ArrayBuffer, or an ArrayBuffer. Always copied.
function guestBytes(value) {
  if (value instanceof ArrayBuffer) return new Uint8Array(value.slice(0));
  if (value instanceof Uint8Array && value.buffer instanceof ArrayBuffer) return new Uint8Array(value);
  return null;
}
const isBytes = (value) => value instanceof ArrayBuffer || (value instanceof Uint8Array && value.buffer instanceof ArrayBuffer);
// Plain data whose leaves may also be byte arrays (guest host-local arguments).
function plainLocalData(value, depth = 0) {
  // Byte arrays are already in host memory; each call checks their size against its own declared limit.
  if (isBytes(value)) return true;
  if (depth > 8) return false;
  if (value === null || typeof value === 'boolean' || typeof value === 'string') return true;
  if (typeof value === 'number') return Number.isFinite(value);
  if (typeof value !== 'object' || (!Array.isArray(value) && ![Object.prototype, null].includes(Object.getPrototypeOf(value)))) return false;
  if (Object.values(Object.getOwnPropertyDescriptors(value)).some((descriptor) => descriptor.get || descriptor.set)) return false;
  const children = Object.values(value);
  return children.length <= BATCH_OPS_MAX && children.every((child) => plainLocalData(child, depth + 1));
}

// Total bytes in a call's arguments, counted before the call is queued (Yataverse review 2026-11-22, finding 5).
function argumentBytes(value, depth = 0) {
  if (isBytes(value)) return value.byteLength;
  if (depth > 8 || value === null || typeof value !== 'object') return 0;
  let total = 0;
  for (const child of Object.values(value)) total += argumentBytes(child, depth + 1);
  return total;
}

/** Problems with a host storage backend: its methods and its declaration of Legal's MUSTs. Empty when it may
 * get the storage calls. The declaration is the host's attestation, with its own evidence; there is no default.
 * `verifyHostStorageConformance` checks the behaviour it can observe.
 * Backend contract (partition = the app id; keys are store-qualified names):
 * - get(partition, key) -> { value: Uint8Array, version } | null
 * - list(partition) -> [{ key, bytes, modified, version }]
 * - batch(partition, ops) -> { versions: { [key]: version } } | { conflict: true }. ops: [{ put: { key, value } } |
 *   { delete: { key } }], each with an optional `expect` (the version the key must have; 0: absent). Applied in
 *   order, all or nothing, in one transaction. A put gets the key's current version + 1; a delete leaves 0.
 * - clear(partition)
 * - conformance: { schema, host, 'key-custody': 'platform-keystore' | 'host-profile',
 *   'no-cloud-backup': true | 'no-os-backup', 'no-logging', 'encrypted-at-rest', 'encrypted-names',
 *   'user-clearable', 'removed-with-app' }. A key kept in the host profile next to the data is accepted only
 *   for a host with no OS backup at all (a plain browser); any other host keeps its keys in the platform keystore. */
export function clientStorageBackendProblems(backend) {
  const problems = [];
  for (const method of ['get', 'list', 'batch', 'clear']) if (typeof backend?.[method] !== 'function') problems.push(`missing-${method}`);
  const declared = backend?.conformance;
  if (!record(declared) || declared.schema !== CLIENT_STORAGE_CONFORMANCE_SCHEMA || !plainWords(declared.host, 64)) return [...problems, 'missing-conformance-declaration'];
  if (declared['no-cloud-backup'] !== true && declared['no-cloud-backup'] !== 'no-os-backup') problems.push('not-declared:no-cloud-backup');
  for (const must of STORAGE_MUSTS) if (declared[must] !== true) problems.push(`not-declared:${must}`);
  if (!['platform-keystore', 'host-profile'].includes(declared['key-custody'])) problems.push('not-declared:key-custody');
  else if (declared['key-custody'] === 'host-profile' && declared['no-cloud-backup'] !== 'no-os-backup') problems.push('key-custody-requires-platform-keystore');
  return problems;
}

function captureBackend(backend) {
  const bound = {};
  for (const method of ['get', 'list', 'batch', 'clear']) bound[method] = backend[method].bind(backend);
  return Object.freeze(bound);
}

// One storage core per (backend, app id) in this document: every mount of the app shares its queue and its
// cache, so one mount never acts on another's stale view (Yataverse review, finding 1). Versions and
// compare-and-swap are decided inside the backend's transaction; the cache only plans quotas and lists.
const storageCores = new WeakMap();
function storageCore(backend, partition) {
  let byPartition = storageCores.get(backend);
  if (!byPartition) { byPartition = new Map(); storageCores.set(backend, byPartition); }
  if (!byPartition.has(partition)) byPartition.set(partition, createStorageCore(captureBackend(backend), partition));
  return byPartition.get(partition);
}
function createStorageCore(store, partition) {
  let usage = null; // `${store}/${key}` -> { size, modified, version }; size = UTF-8 length of the name + value bytes
  let queue = Promise.resolve(); let waiting = 0;
  // Another tab of this app changed the store: drop the cached sizes and versions, so they are read again.
  if (!localWatchers.has(partition)) localWatchers.set(partition, new Set());
  localWatchers.get(partition).add((keys, remote) => { if (remote) usage = null; });
  changeChannel(partition);
  const sizeOf = (full, n) => utf8Length(full) + n;
  const total = (map) => { let sum = 0; for (const entry of map.values()) sum += entry.size; return sum; };
  // A backend error may carry stored data in its message; it is replaced by a code, never forwarded.
  const backend = async (fn) => { try { return await fn(); } catch { throw localError('unavailable'); } };
  async function load() {
    if (usage) return usage;
    const entries = await backend(() => store.list(partition));
    if (!Array.isArray(entries) || !entries.every((entry) => record(entry) && typeof entry.key === 'string'
        && Number.isSafeInteger(entry.bytes) && entry.bytes >= 0 && Number.isFinite(entry.modified)
        && Number.isSafeInteger(entry.version) && entry.version >= 1)) throw localError('unavailable');
    usage = new Map(entries.map((entry) => [entry.key, { size: sizeOf(entry.key, entry.bytes), modified: entry.modified, version: entry.version }]));
    return usage;
  }
  async function read(full) {
    const found = await backend(() => store.get(partition, full));
    if (found === null || found === undefined) return null;
    if (!record(found) || !(found.value instanceof Uint8Array) || !Number.isSafeInteger(found.version)) throw localError('unavailable');
    return found;
  }
  // Plan quota and entries on the cache, then let the backend apply the writes atomically, check every
  // `expect` and assign versions. A conflict drops the cache (it was stale) and changes nothing.
  async function commit(writes, limits) {
    await load();
    const next = new Map(usage);
    const now = Date.now();
    for (const write of writes) {
      if (write.put) {
        if (!next.has(write.put.key) && next.size >= limits['max-entries']) throw localError('quota-exceeded');
        next.set(write.put.key, { size: sizeOf(write.put.key, write.put.value.byteLength), modified: now, version: 0 });
        if (total(next) > limits['quota-bytes']) throw localError('quota-exceeded');
      } else next.delete(write.delete.key);
    }
    if (writes.length === 0) return {};
    const result = await backend(() => store.batch(partition, writes));
    if (record(result) && result.conflict === true) { usage = null; throw localError('version-conflict'); }
    if (!record(result) || !record(result.versions)) { usage = null; throw localError('unavailable'); }
    for (const [key, entry] of next) if (entry.version === 0) entry.version = result.versions[key] ?? 1;
    usage = next;
    announceChange(partition, [...new Set(writes.map((write) => (write.put ?? write.delete).key))]);
    return result.versions;
  }
  async function clear() {
    const keys = [...(await load()).keys()];
    await backend(() => store.clear(partition));
    usage = new Map();
    announceChange(partition, keys);
  }
  // One call at a time per app, in order; at most STORAGE_PENDING_MAX waiting, holding at most
  // STORAGE_PENDING_BYTES_MAX of argument bytes together.
  let pendingBytes = 0;
  function run(fn, bytes = 0) {
    if (waiting >= STORAGE_PENDING_MAX || pendingBytes + bytes > STORAGE_PENDING_BYTES_MAX) return Promise.reject(localError('busy'));
    waiting += 1; pendingBytes += bytes;
    const result = queue.then(fn);
    queue = result.catch(() => {});
    return result.finally(() => { waiting -= 1; pendingBytes -= bytes; });
  }
  return Object.freeze({ partition, load, read, commit, clear, run });
}

function createStorage(core, declaration) {
  const limits = declaration.storage;
  const stores = new Set(declaration.stores);
  const partition = core.partition;
  const name = (storeName, key) => `${storeName}/${key}`;
  const storeOf = (storeName) => { if (typeof storeName !== 'string' || !stores.has(storeName)) throw localError('not-declared'); return storeName; };
  const keyOf = (key) => { if (!validStorageKey(key)) throw localError('invalid-key'); return key; };
  const valueOf = (value) => {
    const bytes = guestBytes(value);
    if (!bytes) throw localError('invalid-arguments');
    if (bytes.byteLength > limits['max-value-bytes']) throw localError('too-large');
    return bytes;
  };
  const args = (input, required, optional = []) => {
    if (!record(input) || !required.every((key) => Object.hasOwn(input, key)) || Object.keys(input).some((key) => !required.includes(key) && !optional.includes(key))) throw localError('invalid-arguments');
    return input;
  };
  const versionOf = (value) => { if (!limit(value, 0, Number.MAX_SAFE_INTEGER)) throw localError('invalid-arguments'); return value; };
  const expectOf = (input) => (Object.hasOwn(input, 'ifVersion') ? { expect: versionOf(input.ifVersion) } : {});
  // Arguments are checked here, before the call is queued; the queued part only touches the backend.
  const prepare = {
    'storage.get'(input) {
      args(input, ['store', 'key'], ['offset', 'length']);
      const full = name(storeOf(input.store), keyOf(input.key));
      const offset = input.offset ?? 0; const length = input.length ?? limits['max-value-bytes'];
      if (!limit(offset, 0, CLIENT_PORT_BYTES_MAX) || !limit(length, 0, limits['max-value-bytes'])) throw localError('invalid-arguments');
      return async () => {
        const found = await core.read(full);
        return found === null ? null : { value: found.value.slice(offset, offset + length), size: found.value.byteLength, version: found.version };
      };
    },
    'storage.put'(input) {
      args(input, ['store', 'key', 'value'], ['ifAbsent', 'ifVersion']);
      const full = name(storeOf(input.store), keyOf(input.key));
      const value = valueOf(input.value);
      if (Object.hasOwn(input, 'ifAbsent') && typeof input.ifAbsent !== 'boolean') throw localError('invalid-arguments');
      const write = { put: { key: full, value }, ...expectOf(input) };
      return async () => {
        if (input.ifAbsent === true) {
          if ((await core.load()).has(full)) throw localError('key-exists');
          if (!Object.hasOwn(write, 'expect')) write.expect = 0;
        }
        const versions = await core.commit([write], limits);
        return { size: value.byteLength, version: versions[full] };
      };
    },
    'storage.delete'(input) {
      args(input, ['store', 'key'], ['ifVersion']);
      const full = name(storeOf(input.store), keyOf(input.key));
      const write = { delete: { key: full }, ...expectOf(input) };
      return async () => {
        const existed = (await core.load()).has(full);
        if (existed || Object.hasOwn(write, 'expect')) await core.commit([write], limits);
        return { deleted: existed };
      };
    },
    'storage.list'(input) {
      args(input, ['store'], ['prefix', 'cursor', 'limit']);
      const storeName = storeOf(input.store);
      const prefix = input.prefix ?? ''; const cursor = input.cursor ?? null; const count = input.limit ?? LIST_LIMIT_MAX;
      if (typeof prefix !== 'string' || prefix.length > 1024 || (cursor !== null && !validStorageKey(cursor)) || !limit(count, 1, LIST_LIMIT_MAX)) throw localError('invalid-arguments');
      return async () => {
        const usage = await core.load();
        const head = `${storeName}/`;
        const keys = [...usage.keys()].filter((full) => full.startsWith(head)).map((full) => full.slice(head.length))
          .filter((key) => key.startsWith(prefix) && (cursor === null || key > cursor)).sort();
        const page = keys.slice(0, count);
        return {
          entries: page.map((key) => { const entry = usage.get(head + key); return { key, size: entry.size - utf8Length(head + key), modified: entry.modified, version: entry.version }; }),
          cursor: keys.length > count ? page[page.length - 1] : null,
        };
      };
    },
    'storage.clear'(input) {
      args(input, [], ['store']);
      if (!Object.hasOwn(input, 'store')) return async () => { await core.clear(); return { cleared: true }; };
      const head = `${storeOf(input.store)}/`;
      return async () => {
        const usage = await core.load();
        await core.commit([...usage.keys()].filter((full) => full.startsWith(head)).map((key) => ({ delete: { key } })), limits);
        return { cleared: true };
      };
    },
    'storage.batch'(input) {
      args(input, ['ops']);
      if (!Array.isArray(input.ops) || input.ops.length === 0 || input.ops.length > BATCH_OPS_MAX) throw localError('invalid-arguments');
      const steps = [];
      for (const op of input.ops) {
        if (!record(op) || Object.keys(op).length !== 1) throw localError('invalid-arguments');
        if (op.put) {
          args(op.put, ['store', 'key', 'value'], ['ifVersion']);
          steps.push({ put: { key: name(storeOf(op.put.store), keyOf(op.put.key)), value: valueOf(op.put.value) }, ...expectOf(op.put) });
        } else if (op.delete) {
          args(op.delete, ['store', 'key'], ['ifVersion']);
          steps.push({ delete: { key: name(storeOf(op.delete.store), keyOf(op.delete.key)) }, ...expectOf(op.delete) });
        } else if (op.move) {
          args(op.move, ['from', 'to']);
          if (!Array.isArray(op.move.from) || op.move.from.length !== 2 || !Array.isArray(op.move.to) || op.move.to.length !== 2) throw localError('invalid-arguments');
          steps.push({ move: { from: name(storeOf(op.move.from[0]), keyOf(op.move.from[1])), to: name(storeOf(op.move.to[0]), keyOf(op.move.to[1])) } });
        } else throw localError('invalid-arguments');
      }
      return async () => {
        const usage = await core.load();
        // Every byte the batch holds counts, moved values included (finding 4); checked before a value is read.
        const pending = new Map(); let bytes = 0;
        const sizeNow = (full) => (pending.has(full) ? (pending.get(full)?.byteLength ?? null) : (usage.has(full) ? usage.get(full).size - utf8Length(full) : null));
        for (const step of steps) {
          if (step.put) { bytes += step.put.value.byteLength; pending.set(step.put.key, step.put.value); }
          else if (step.delete) pending.set(step.delete.key, null);
          else {
            const size = sizeNow(step.move.from);
            if (size === null) throw localError('not-found');
            bytes += size; pending.set(step.move.to, { byteLength: size }); pending.set(step.move.from, null);
          }
        }
        if (bytes > BATCH_BYTES_MAX) throw localError('too-large');
        const writes = []; const values = new Map();
        for (const step of steps) {
          if (!step.move) { writes.push(step); values.set((step.put ?? step.delete).key, step.put ? step.put.value : null); continue; }
          let value = values.has(step.move.from) ? values.get(step.move.from) : (await core.read(step.move.from))?.value ?? null;
          if (value === null) throw localError('not-found');
          writes.push({ put: { key: step.move.to, value } }, { delete: { key: step.move.from } });
          values.set(step.move.to, value); values.set(step.move.from, null);
        }
        await core.commit(writes, limits);
        return { applied: input.ops.length };
      };
    },
    'storage.usage'(input) {
      args(input, []);
      return async () => {
        const usage = await core.load();
        let bytes = 0; for (const entry of usage.values()) bytes += entry.size;
        return { bytes, entries: usage.size, quotaBytes: limits['quota-bytes'] };
      };
    },
  };
  // storage.watch: change notices (store and keys, never values) for this app's own keys, until the guest closes.
  const watching = new WeakMap();
  function watch(input, emit, signal) {
    args(input, ['store'], ['prefix']);
    const storeName = storeOf(input.store); const prefix = input.prefix ?? '';
    if (typeof prefix !== 'string' || prefix.length > 1024) throw localError('invalid-arguments');
    if (typeof emit !== 'function' || !signal) throw localError('not-declared');
    const mine = watching.get(signal) ?? 0;
    if (mine >= WATCHES_MAX) throw localError('busy');
    const head = `${storeName}/`;
    const watcher = (keys) => {
      const changed = keys.filter((full) => full.startsWith(head)).map((full) => full.slice(head.length)).filter((key) => key.startsWith(prefix));
      if (changed.length) emit({ event: 'storage.changed', store: storeName, keys: changed.slice(0, LIST_LIMIT_MAX) });
    };
    localWatchers.get(partition).add(watcher); watching.set(signal, mine + 1);
    signal.addEventListener('abort', () => localWatchers.get(partition)?.delete(watcher), { once: true });
    return { watching: true };
  }
  function call(method, input, emit, signal) {
    try {
      if (method === 'storage.watch') return Promise.resolve(watch(input, emit, signal));
      if (!Object.hasOwn(prepare, method)) throw localError('not-declared');
      return core.run(prepare[method](input), argumentBytes(input));
    } catch (error) { return Promise.reject(error); }
  }
  return Object.freeze({ call, clearAll: () => core.run(() => core.clear()) });
}

// ---- KOTOBA-974 (KOTOBA-159 PR 2): key handles, crypto, device-local host commands, key approval, OAuth ----
// The host performs every operation. A guest holds only opaque handles: random strings that name an entry in a
// table of its own mount (one table per mount signal, per app), so a handle from another mount or another app
// names nothing. Every derive, unwrap and decapsulate returns a handle, never bytes. Private, secret and
// sealing keys never leave the host; content keys leave only wrapped (wrapKey / aesKwpWrap).
//
// Key classes (the class decides what a key may do; the guest cannot change it):
// - secret: a device secret ('secret-32', HKDF only). From the host key store (platform keystore) or derived.
// - sealing: crypto.hkdf from a secret, as 'aes-256-gcm'. Only wrapKey / unwrapKey, never encrypt or decrypt,
//   and never wrapped. A guest cannot know its value, so it is the only class that may wrap private keys. Its
//   wraps bind the target type in the additional data (CLIENT_KEY_WRAP_TAG), so a wrap of one type never unwraps
//   as another.
// - content: 'aes-256-gcm' / 'xchacha20-poly1305' (generated, unwrapped, or derived from a key agreement whose
//   peer the guest chose). Encrypt, decrypt, wrap content keys, and be wrapped. A guest may know its value
//   (it chose the peer), so it never wraps a private key.
// - private: 'x25519-private', 'ml-kem-768-private'. Key agreement and decapsulation only; wrapped only under a
//   sealing key. Its public key is returned; the private key never is.
// - signing: 'ed25519'. Ephemeral ones sign with crypto.ed25519Sign; a declared, persistent one signs only
//   through keys.sign, after the host shows what is signed (key approval).
// ML-KEM-768, XChaCha20-Poly1305, AES-256-KWP and X25519 run in the host realm from the pinned libraries in
// CLIENT_CRYPTO_LIBRARIES (vendored @noble, loaded on first use); AES-GCM, HKDF, SHA-256, Ed25519 and ES256
// use the host's WebCrypto with non-extractable CryptoKeys.
const vendorUrl = (path) => new URL(`./vendor/${path}`, import.meta.url).href;
/** The pin ledger of the host-realm crypto libraries (vendored, verbatim but for import paths). `integrity` is the npm package SRI (sha512 of the tarball), not a per-file hash; verify-client-keys-20261122 pins the per-file sha512 of the vendored bytes. */
export const CLIENT_CRYPTO_LIBRARIES = Object.freeze([
  Object.freeze({ name: '@noble/post-quantum', version: '0.5.4', use: 'ML-KEM-768 (FIPS 203)', integrity: 'sha512-leww0zzIirrvwaYMPI9fj6aRIlA/c6Y0/lifQQ1YOOyHEr0MNH3yYpjXeiVG+tWdPps4XxGclFWX2INPO3Yo5w==', files: Object.freeze(['post-quantum/ml-kem.js', 'post-quantum/_crystals.js', 'post-quantum/utils.js']) }),
  Object.freeze({ name: '@noble/ciphers', version: '2.0.1', use: 'XChaCha20-Poly1305, AES-256-KWP (RFC 5649)', integrity: 'sha512-xHK3XHPUW8DTAobU+G0XT+/w+JLM7/8k1UFdB5xg/zTFPnFCobhftzw8wl4Lw2aq/Rvir5pxfZV5fEazmeCJ2g==', files: Object.freeze(['ciphers/chacha.js', 'ciphers/_arx.js', 'ciphers/_poly1305.js', 'ciphers/aes.js', 'ciphers/_polyval.js', 'ciphers/utils.js']) }),
  Object.freeze({ name: '@noble/hashes', version: '2.0.1', use: 'SHA-3 / SHAKE for ML-KEM', integrity: 'sha512-XlOlEbQcE9fmuXxrVTXCTlG2nlRXa9Rj3rr5Ue/+tX+nmkgbX720YHh0VR3hBF9xDvwnb8D2shVGOwNx+ulArw==', files: Object.freeze(['hashes-2/sha3.js', 'hashes-2/_u64.js', 'hashes-2/utils.js']) }),
  Object.freeze({ name: '@noble/curves', version: '2.0.1', use: 'NTT for ML-KEM (abstract/fft.js only)', integrity: 'sha512-vs1Az2OOTBiP4q0pwjW5aF0xp9n4MxVrmkFBxc6EKZc6ddYx5gaZiAsZoq0uRRXWbi3AT/sBqn05eRPtn1JCPw==', files: Object.freeze(['curves-2/abstract/fft.js']) }),
  Object.freeze({ name: '@noble/curves', version: '1.9.7', use: 'X25519 (already vendored for actor-host)', integrity: 'see src/vendor/README.md', files: Object.freeze(['curves/ed25519.js']) }),
]);
let cryptoLibraries = null;
function loadCryptoLibraries() {
  cryptoLibraries ??= Promise.all([
    import(vendorUrl('post-quantum/ml-kem.js')), import(vendorUrl('ciphers/chacha.js')), import(vendorUrl('ciphers/aes.js')), import(vendorUrl('curves/ed25519.js')),
  ]).then(([kem, chacha, aes, curves]) => Object.freeze({ mlkem: kem.ml_kem768, xchacha: chacha.xchacha20poly1305, aeskwp: aes.aeskwp, x25519: curves.x25519 }));
  return cryptoLibraries;
}
export const CLIENT_KEY_TYPES = Object.freeze(['secret-32', 'aes-256-gcm', 'xchacha20-poly1305', 'x25519', 'ml-kem-768', 'ed25519']);
// Bounds on every crypto input (KOTOBA-974 "bound every input size").
const CRYPTO_DATA_MAX = CLIENT_PORT_BYTES_MAX;
const CRYPTO_AAD_MAX = 65536;
const CRYPTO_LABEL_MAX = 1024;
const CRYPTO_WRAPPED_MAX = 4096;
const HANDLES_PER_MOUNT = 4096;
const KEY_WRAP_TAG = 'kotoba.key-wrap.v1';
const SIGN_PAYLOAD_MAX = 1048576;
const subtle = () => globalThis.crypto.subtle;
const randomBytes = (n) => globalThis.crypto.getRandomValues(new Uint8Array(n));
const hexOf = (bytes) => Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
const b64url = (bytes) => { let s = ''; for (const b of bytes) s += String.fromCharCode(b); return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, ''); };
const concatBytes = (...parts) => { const out = new Uint8Array(parts.reduce((n, p) => n + p.byteLength, 0)); let at = 0; for (const p of parts) { out.set(p, at); at += p.byteLength; } return out; };
const wipe = (bytes) => { try { bytes?.fill?.(0); } catch { /* frozen */ } };
const PKCS8_X25519 = Uint8Array.from([0x30, 0x2e, 0x02, 0x01, 0x00, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x6e, 0x04, 0x22, 0x04, 0x20]);
// Bytes of exactly `size`, or within [min, max]; a copy the guest cannot change afterwards.
function bytesArg(value, { size = null, min = 0, max = CRYPTO_DATA_MAX } = {}) {
  const bytes = guestBytes(value);
  if (!bytes) throw localError('invalid-arguments');
  if (size !== null ? bytes.byteLength !== size : bytes.byteLength < min || bytes.byteLength > max) throw localError(bytes.byteLength > max ? 'too-large' : 'invalid-arguments');
  return bytes;
}
function cryptoArgs(input, required, optional = []) {
  if (!record(input) || !required.every((key) => Object.hasOwn(input, key)) || Object.keys(input).some((key) => !required.includes(key) && !optional.includes(key))) throw localError('invalid-arguments');
  return input;
}
async function hkdfBits(baseKey, salt, info, bits = 256) {
  return new Uint8Array(await subtle().deriveBits({ name: 'HKDF', hash: 'SHA-256', salt, info }, baseKey, bits));
}
async function importSecret(bytes) { return subtle().importKey('raw', bytes, 'HKDF', false, ['deriveBits']); }
async function importGcm(bytes) { return subtle().importKey('raw', bytes, 'AES-GCM', false, ['encrypt', 'decrypt']); }
const wrapAad = (type, aad) => concatBytes(new TextEncoder().encode(`${KEY_WRAP_TAG}\u0000${type}\u0000`), aad);

/** Host key store: persistent, declared keys (keys.generate / keys.open / keys.delete) for one app partition.
 * Contract: get(partition, id) -> { type, key: CryptoKey, publicKey?: Uint8Array } | null; create(partition, id,
 * type) -> the same (refuses when the id exists); delete(partition, id); clear(partition); conformance: {
 * schema: 'kotoba.host-key-conformance.v1', host, 'key-custody': 'platform-keystore' | 'host-profile',
 * 'no-cloud-backup': true | 'no-os-backup', 'no-logging', 'user-clearable', 'removed-with-app' }. Every key it
 * returns must be a non-extractable CryptoKey (a 'secret-32' is an HKDF key; an 'ed25519' an Ed25519 private key). */
export const CLIENT_KEY_CONFORMANCE_SCHEMA = 'kotoba.host-key-conformance.v1';
export function clientKeyStoreProblems(store) {
  const problems = [];
  for (const method of ['get', 'create', 'delete', 'clear']) if (typeof store?.[method] !== 'function') problems.push(`missing-${method}`);
  const declared = store?.conformance;
  if (!record(declared) || declared.schema !== CLIENT_KEY_CONFORMANCE_SCHEMA || !plainWords(declared.host, 64)) return [...problems, 'missing-conformance-declaration'];
  if (declared['no-cloud-backup'] !== true && declared['no-cloud-backup'] !== 'no-os-backup') problems.push('not-declared:no-cloud-backup');
  for (const must of ['no-logging', 'user-clearable', 'removed-with-app']) if (declared[must] !== true) problems.push(`not-declared:${must}`);
  if (!['platform-keystore', 'host-profile'].includes(declared['key-custody'])) problems.push('not-declared:key-custody');
  // Legal L1/L3 as in PR 1: a Tauri or Android host keeps its keys in the platform keystore.
  else if (declared['key-custody'] === 'host-profile' && declared['no-cloud-backup'] !== 'no-os-backup') problems.push('key-custody-requires-platform-keystore');
  return problems;
}
/** A key store over a host key-value store that keeps CryptoKey objects as they are (IndexedDB does). The keys
 * are created here, non-extractable; acceptable only for a plain browser host (key-custody 'host-profile'). A
 * Tauri or Android host passes its own platform-keystore store. */
export function createClientKeyStore({ kv, conformance }) {
  for (const method of ['get', 'update', 'deletePrefix']) if (typeof kv?.[method] !== 'function') throw new TypeError('invalid key-value store');
  if (!record(conformance)) throw new TypeError('the host must supply its key conformance declaration');
  const name = (partition, id) => `k\u0000${partition}\u0000${id}`;
  return Object.freeze({
    conformance: freezeClone({ schema: CLIENT_KEY_CONFORMANCE_SCHEMA, 'key-custody': 'host-profile', ...conformance }),
    async get(partition, id) { return (await kv.get(name(partition, id))) ?? null; },
    async create(partition, id, type) {
      let entry;
      if (type === 'secret-32') { const bytes = randomBytes(32); entry = { type, key: await importSecret(bytes) }; wipe(bytes); }
      else if (type === 'ed25519') {
        const pair = await subtle().generateKey('Ed25519', false, ['sign', 'verify']);
        entry = { type, key: pair.privateKey, publicKey: new Uint8Array(await subtle().exportKey('raw', pair.publicKey)) };
      } else throw new TypeError('unsupported key type');
      const stored = await kv.update([name(partition, id)], ([current]) => (current ? { abort: true, result: false } : { writes: [['put', name(partition, id), entry]], result: true }));
      return stored === false ? null : entry;
    },
    async delete(partition, id) { await kv.update([name(partition, id)], () => ({ writes: [['delete', name(partition, id)]], result: true })); },
    async clear(partition) { await kv.deletePrefix(`k\u0000${partition}\u0000`); },
  });
}
export function createIndexedDbClientKeyStore({ indexedDB = globalThis.indexedDB, name = 'kotoba-client-host-keys-v1', conformance } = {}) {
  return createClientKeyStore({ kv: indexedDbKv(indexedDB, name), conformance: { ...conformance, 'no-cloud-backup': 'no-os-backup' } });
}

// One handle table per mount (keyed by its lifetime signal) and per app. Cleared when the mount closes.
function createKeyTables() {
  const tables = new WeakMap();
  const tableFor = (signal) => {
    if (!signal) throw localError('unavailable');
    let table = tables.get(signal);
    if (!table) {
      table = new Map(); tables.set(signal, table);
      signal.addEventListener('abort', () => { for (const entry of table.values()) wipe(entry.bytes); table.clear(); }, { once: true });
    }
    return table;
  };
  return Object.freeze({
    add(signal, entry) {
      const table = tableFor(signal);
      if (table.size >= HANDLES_PER_MOUNT) throw localError('busy');
      const handle = `kh.${hexOf(randomBytes(16))}`;
      table.set(handle, entry);
      return handle;
    },
    get(signal, handle, test = () => true) {
      if (typeof handle !== 'string' || !/^kh\.[0-9a-f]{32}$/.test(handle)) throw localError('invalid-key');
      const entry = signal ? tables.get(signal)?.get(handle) : null;
      if (!entry) throw localError('invalid-key');
      if (!test(entry)) throw localError('invalid-arguments');
      return entry;
    },
    release(signal, handle) { const table = tables.get(signal); const entry = table?.get(handle); if (!entry) throw localError('invalid-key'); wipe(entry.bytes); table.delete(handle); },
  });
}

function keyDeclarationProblems(keys) {
  if (!Array.isArray(keys) || keys.length > 16) return ['invalid-keys'];
  const problems = [];
  for (const key of keys) {
    if (record(key) && key.type === 'ed25519') {
      const continuous = key.approval === 'continuous';
      if (!exactKeys(key, ['id', 'type', 'use', 'approval', 'operations', ...(continuous ? ['withdrawal'] : [])]) || !validName(key.id)
          || !Array.isArray(key.use) || key.use.length !== 1 || key.use[0] !== 'sign' || !['each-operation', 'continuous'].includes(key.approval)
          || !plainList(key.operations, 60)) problems.push('invalid-keys');
      // Continuous signing only when declared, with the place the user stops it (revocable).
      else if (continuous && !plainWords(key.withdrawal, 120)) problems.push('continuous-signing-needs-withdrawal');
    } else if (!(exactKeys(key, ['id', 'type', 'use']) && validName(key.id) && key.type === 'secret-32' && Array.isArray(key.use) && key.use.length === 1 && key.use[0] === 'hkdf')) problems.push('invalid-keys');
  }
  if (new Set(keys.map((key) => key?.id)).size !== keys.length) problems.push('invalid-keys');
  return [...new Set(problems)];
}

// Crypto and key calls for one app (createClientHostLocal). `confirm` is the canonical consent host (key approval).
function createKeyCalls({ appId, declaration, keyStore, confirm, profile, appIdentity }) {
  const tables = createKeyTables();
  const declaredKeys = new Map((declaration.keys ?? []).map((key) => [key.id, key]));
  const continuousGrants = new Map();   // key id -> Set of canonical [operation, recipient]; in host memory, revocable
  const store = () => { if (!keyStore) throw localError('unavailable'); return keyStore; };
  const fromStore = (entry, id) => {
    const key = entry?.key;
    // Only non-extractable CryptoKeys from the host key store (T3 of PR 1, KOTOBA-974 "key extraction").
    if (!entry || !(key instanceof globalThis.CryptoKey) || key.extractable !== false) throw localError('unavailable');
    const declared = declaredKeys.get(id);
    if (entry.type !== declared.type) throw localError('unavailable');
    return declared.type === 'secret-32' ? { cls: 'secret', type: 'secret-32', key } : { cls: 'signing', type: 'ed25519', key, publicKey: entry.publicKey, persistent: id };
  };
  const keyId = (id) => { if (typeof id !== 'string' || !declaredKeys.has(id)) throw localError('not-declared'); return id; };
  const publicOf = (entry) => (entry.publicKey ? { publicKey: new Uint8Array(entry.publicKey) } : {});
  async function contentEntry(type, bytes) {
    return { cls: 'content', type, bytes, key: type === 'aes-256-gcm' ? await importGcm(bytes) : null };
  }
  async function privateEntry(type, bytes) {
    const libs = await loadCryptoLibraries();
    if (type === 'x25519-private') {
      if (bytes.byteLength !== 32) throw localError('invalid-arguments');
      return { cls: 'private', type, bytes, publicKey: libs.x25519.getPublicKey(bytes) };
    }
    if (bytes.byteLength === 64) { const pair = libs.mlkem.keygen(bytes); wipe(bytes); return { cls: 'private', type, bytes: pair.secretKey, publicKey: pair.publicKey }; }
    if (bytes.byteLength !== 2400) throw localError('invalid-arguments');
    // FIPS 203 decapsulation key: dk_pke || ek || H(ek) || z. The public key is ek.
    return { cls: 'private', type, bytes, publicKey: bytes.slice(1152, 1152 + 1184) };
  }
  const AS_CONTENT = new Set(['aes-256-gcm', 'xchacha20-poly1305']);
  const AS_PRIVATE = new Set(['x25519-private', 'ml-kem-768-private']);
  const isAesKek = (entry) => (entry.cls === 'content' && entry.type === 'aes-256-gcm');
  const calls = {
    async 'keys.generate'(input, signal) {
      cryptoArgs(input, ['id'], ['type']);
      const id = keyId(input.id);
      if (Object.hasOwn(input, 'type') && input.type !== declaredKeys.get(id).type) throw localError('invalid-arguments');
      let created;
      try { created = await store().create(appId, id, declaredKeys.get(id).type); } catch (error) { if (error instanceof ClientLocalError) throw error; throw localError('unavailable'); }
      if (created === null) throw localError('key-exists');
      const entry = fromStore(created, id);
      return { handle: tables.add(signal, entry), ...publicOf(entry) };
    },
    async 'keys.open'(input, signal) {
      cryptoArgs(input, ['id']);
      const id = keyId(input.id);
      let found;
      try { found = await store().get(appId, id); } catch { throw localError('unavailable'); }
      if (found === null) return null;
      const entry = fromStore(found, id);
      return { handle: tables.add(signal, entry), ...publicOf(entry) };
    },
    async 'keys.delete'(input) {
      cryptoArgs(input, ['id']);
      const id = keyId(input.id);
      try { await store().delete(appId, id); } catch { throw localError('unavailable'); }
      continuousGrants.delete(id);
      return { deleted: true };
    },
    async 'keys.sign'(input, signal) { return sign(input, signal); },
    async 'crypto.release'(input, signal) { cryptoArgs(input, ['handle']); tables.release(signal, input.handle); return {}; },
    async 'crypto.generateKey'(input, signal) {
      cryptoArgs(input, ['as']);
      if (input.as === 'aes-256-gcm' || input.as === 'xchacha20-poly1305') return { handle: tables.add(signal, await contentEntry(input.as, randomBytes(32))) };
      if (input.as === 'x25519' || input.as === 'ml-kem-768') {
        const libs = await loadCryptoLibraries();
        const entry = input.as === 'x25519' ? await privateEntry('x25519-private', randomBytes(32))
          : await privateEntry('ml-kem-768-private', randomBytes(64));
        return { handle: tables.add(signal, entry), publicKey: new Uint8Array(entry.publicKey) };
      }
      if (input.as === 'ed25519') {
        const pair = await subtle().generateKey('Ed25519', false, ['sign', 'verify']);
        const publicKey = new Uint8Array(await subtle().exportKey('raw', pair.publicKey));
        return { handle: tables.add(signal, { cls: 'signing', type: 'ed25519', key: pair.privateKey, publicKey }), publicKey: new Uint8Array(publicKey) };
      }
      throw localError('invalid-arguments');   // a disallowed algorithm
    },
    async 'crypto.hkdf'(input, signal) {
      cryptoArgs(input, ['key', 'salt', 'info', 'length', 'as']);
      const base = tables.get(signal, input.key, (entry) => entry.cls === 'secret');
      if (input.length !== 32 || !['aes-256-gcm', 'secret-32'].includes(input.as)) throw localError('invalid-arguments');
      const bits = await hkdfBits(base.key, bytesArg(input.salt, { max: CRYPTO_LABEL_MAX }), bytesArg(input.info, { max: CRYPTO_LABEL_MAX }));
      try {
        // A key derived from a device secret is a sealing key (wraps only) or another secret (HKDF only).
        const entry = input.as === 'secret-32' ? { cls: 'secret', type: 'secret-32', key: await importSecret(bits) } : { cls: 'sealing', type: 'aes-256-gcm', key: await importGcm(bits) };
        return { handle: tables.add(signal, entry) };
      } finally { wipe(bits); }
    },
    async 'crypto.aesGcmEncrypt'(input, signal) {
      cryptoArgs(input, ['key', 'iv', 'plaintext'], ['aad']);
      const key = tables.get(signal, input.key, (entry) => entry.cls === 'content' && entry.type === 'aes-256-gcm');
      const iv = bytesArg(input.iv, { size: 12 }); const aad = bytesArg(input.aad ?? new Uint8Array(), { max: CRYPTO_AAD_MAX });
      const plaintext = bytesArg(input.plaintext);
      return { ciphertext: new Uint8Array(await subtle().encrypt({ name: 'AES-GCM', iv, additionalData: aad, tagLength: 128 }, key.key, plaintext)) };
    },
    async 'crypto.aesGcmDecrypt'(input, signal) {
      cryptoArgs(input, ['key', 'iv', 'ciphertext'], ['aad']);
      const key = tables.get(signal, input.key, (entry) => entry.cls === 'content' && entry.type === 'aes-256-gcm');
      const iv = bytesArg(input.iv, { size: 12 }); const aad = bytesArg(input.aad ?? new Uint8Array(), { max: CRYPTO_AAD_MAX });
      const ciphertext = bytesArg(input.ciphertext, { min: 16, max: CRYPTO_DATA_MAX + 16 });
      try { return { plaintext: new Uint8Array(await subtle().decrypt({ name: 'AES-GCM', iv, additionalData: aad, tagLength: 128 }, key.key, ciphertext)) }; }
      catch { throw localError('invalid-arguments'); }
    },
    async 'crypto.xchachaEncrypt'(input, signal) {
      cryptoArgs(input, ['key', 'iv', 'plaintext'], ['aad']);
      const key = tables.get(signal, input.key, (entry) => entry.cls === 'content' && entry.type === 'xchacha20-poly1305');
      const iv = bytesArg(input.iv, { size: 24 }); const aad = bytesArg(input.aad ?? new Uint8Array(), { max: CRYPTO_AAD_MAX });
      const plaintext = bytesArg(input.plaintext);
      return { ciphertext: (await loadCryptoLibraries()).xchacha(key.bytes, iv, aad).encrypt(plaintext) };
    },
    async 'crypto.xchachaDecrypt'(input, signal) {
      cryptoArgs(input, ['key', 'iv', 'ciphertext'], ['aad']);
      const key = tables.get(signal, input.key, (entry) => entry.cls === 'content' && entry.type === 'xchacha20-poly1305');
      const iv = bytesArg(input.iv, { size: 24 }); const aad = bytesArg(input.aad ?? new Uint8Array(), { max: CRYPTO_AAD_MAX });
      const ciphertext = bytesArg(input.ciphertext, { min: 16, max: CRYPTO_DATA_MAX + 16 });
      try { return { plaintext: (await loadCryptoLibraries()).xchacha(key.bytes, iv, aad).decrypt(ciphertext) }; }
      catch { throw localError('invalid-arguments'); }
    },
    async 'crypto.wrapKey'(input, signal) {
      cryptoArgs(input, ['key', 'iv', 'target'], ['aad']);
      const kek = tables.get(signal, input.key, (entry) => entry.cls === 'sealing' || isAesKek(entry));
      // A private key is wrapped only under a sealing key; a sealing, secret or signing key never.
      const target = tables.get(signal, input.target, (entry) => entry.cls === 'content' || (entry.cls === 'private' && kek.cls === 'sealing'));
      const iv = bytesArg(input.iv, { size: 12 }); const aad = bytesArg(input.aad ?? new Uint8Array(), { max: CRYPTO_AAD_MAX });
      const additionalData = kek.cls === 'sealing' ? wrapAad(target.type, aad) : aad;
      return { wrapped: new Uint8Array(await subtle().encrypt({ name: 'AES-GCM', iv, additionalData, tagLength: 128 }, kek.key, target.bytes)) };
    },
    async 'crypto.unwrapKey'(input, signal) {
      cryptoArgs(input, ['key', 'iv', 'wrapped', 'as'], ['aad']);
      const kek = tables.get(signal, input.key, (entry) => entry.cls === 'sealing' || isAesKek(entry));
      if (!(AS_CONTENT.has(input.as) || (AS_PRIVATE.has(input.as) && kek.cls === 'sealing'))) throw localError('invalid-arguments');
      const iv = bytesArg(input.iv, { size: 12 }); const aad = bytesArg(input.aad ?? new Uint8Array(), { max: CRYPTO_AAD_MAX });
      const wrapped = bytesArg(input.wrapped, { min: 17, max: CRYPTO_WRAPPED_MAX });
      let bytes;
      try { bytes = new Uint8Array(await subtle().decrypt({ name: 'AES-GCM', iv, additionalData: kek.cls === 'sealing' ? wrapAad(input.as, aad) : aad, tagLength: 128 }, kek.key, wrapped)); }
      catch { throw localError('invalid-arguments'); }
      if (AS_CONTENT.has(input.as)) { if (bytes.byteLength !== 32) { wipe(bytes); throw localError('invalid-arguments'); } return { handle: tables.add(signal, await contentEntry(input.as, bytes)) }; }
      const entry = await privateEntry(input.as, bytes);
      return { handle: tables.add(signal, entry), publicKey: new Uint8Array(entry.publicKey) };
    },
    async 'crypto.aesKwpWrap'(input, signal) {
      cryptoArgs(input, ['key', 'target']);
      const kek = tables.get(signal, input.key, isAesKek);
      const target = tables.get(signal, input.target, (entry) => entry.cls === 'content');
      return { wrapped: (await loadCryptoLibraries()).aeskwp(kek.bytes).encrypt(target.bytes) };
    },
    async 'crypto.aesKwpUnwrap'(input, signal) {
      cryptoArgs(input, ['key', 'wrapped', 'as']);
      const kek = tables.get(signal, input.key, isAesKek);
      if (!AS_CONTENT.has(input.as)) throw localError('invalid-arguments');
      const wrapped = bytesArg(input.wrapped, { min: 16, max: CRYPTO_WRAPPED_MAX });
      let bytes;
      try { bytes = (await loadCryptoLibraries()).aeskwp(kek.bytes).decrypt(wrapped); } catch { throw localError('invalid-arguments'); }
      if (bytes.byteLength !== 32) { wipe(bytes); throw localError('invalid-arguments'); }
      return { handle: tables.add(signal, await contentEntry(input.as, bytes)) };
    },
    async 'crypto.x25519Derive'(input, signal) {
      cryptoArgs(input, ['private', 'peerPublic', 'info', 'as'], ['salt']);
      const own = tables.get(signal, input.private, (entry) => entry.type === 'x25519-private');
      if (input.as !== 'aes-256-gcm') throw localError('invalid-arguments');
      const peer = bytesArg(input.peerPublic, { size: 32 });
      const shared = await x25519Shared(own.bytes, peer);
      try {
        const key = await hkdfFrom(shared, bytesArg(input.salt ?? new Uint8Array(), { max: CRYPTO_LABEL_MAX }), bytesArg(input.info, { max: CRYPTO_LABEL_MAX }));
        return { handle: tables.add(signal, await contentEntry('aes-256-gcm', key)) };
      } finally { wipe(shared); }
    },
    async 'crypto.hybridEncapsulate'(input, signal) {
      cryptoArgs(input, ['recipientX25519', 'recipientMlkem', 'info', 'as']);
      if (input.as !== 'aes-256-gcm') throw localError('invalid-arguments');
      const recipientX = bytesArg(input.recipientX25519, { size: 32 }); const recipientM = bytesArg(input.recipientMlkem, { size: 1184 });
      const info = bytesArg(input.info, { max: CRYPTO_LABEL_MAX });
      const libs = await loadCryptoLibraries();
      const eph = randomBytes(32); const ephemeralPublic = libs.x25519.getPublicKey(eph);
      let xShared; let encapsulated;
      try { xShared = await x25519Shared(eph, recipientX); encapsulated = libs.mlkem.encapsulate(recipientM); } catch (error) { if (error instanceof ClientLocalError) throw error; throw localError('invalid-arguments'); } finally { wipe(eph); }
      const ikm = concatBytes(xShared, encapsulated.sharedSecret);
      try {
        // Yataverse kem.cljs combiner: HKDF(no salt, x25519 || ML-KEM shared, info || eph-pub || recipient-pub || pq-ct).
        const key = await hkdfFrom(ikm, new Uint8Array(), concatBytes(info, ephemeralPublic, recipientX, encapsulated.cipherText));
        return { handle: tables.add(signal, await contentEntry('aes-256-gcm', key)), ephemeralPublic, ciphertext: encapsulated.cipherText };
      } finally { wipe(ikm); wipe(xShared); wipe(encapsulated.sharedSecret); }
    },
    async 'crypto.hybridDecapsulate'(input, signal) {
      cryptoArgs(input, ['x25519', 'mlkem', 'ephemeralPublic', 'ciphertext', 'info', 'as']);
      const x = tables.get(signal, input.x25519, (entry) => entry.type === 'x25519-private');
      const m = tables.get(signal, input.mlkem, (entry) => entry.type === 'ml-kem-768-private');
      if (input.as !== 'aes-256-gcm') throw localError('invalid-arguments');
      const eph = bytesArg(input.ephemeralPublic, { size: 32 }); const ct = bytesArg(input.ciphertext, { size: 1088 });
      const info = bytesArg(input.info, { max: CRYPTO_LABEL_MAX });
      const libs = await loadCryptoLibraries();
      const xShared = await x25519Shared(x.bytes, eph);
      let pqShared;
      try { pqShared = libs.mlkem.decapsulate(ct, m.bytes); } catch { wipe(xShared); throw localError('invalid-arguments'); }
      const ikm = concatBytes(xShared, pqShared);
      try {
        const key = await hkdfFrom(ikm, new Uint8Array(), concatBytes(info, eph, x.publicKey, ct));
        // A handle, never the shared secret or the derived key.
        return { handle: tables.add(signal, await contentEntry('aes-256-gcm', key)) };
      } finally { wipe(ikm); wipe(xShared); wipe(pqShared); }
    },
    async 'crypto.sha256'(input) {
      cryptoArgs(input, ['data']);
      return { digest: new Uint8Array(await subtle().digest('SHA-256', bytesArg(input.data))) };
    },
    async 'crypto.ed25519Sign'(input, signal) {
      cryptoArgs(input, ['key', 'data']);
      // Only an ephemeral key of this mount. A declared (persistent) signing key signs through keys.sign.
      const key = tables.get(signal, input.key, (entry) => entry.cls === 'signing' && !entry.persistent);
      return { signature: new Uint8Array(await subtle().sign('Ed25519', key.key, bytesArg(input.data, { max: SIGN_PAYLOAD_MAX }))) };
    },
    async 'crypto.ed25519Verify'(input) {
      cryptoArgs(input, ['publicKey', 'signature', 'data']);
      try {
        const key = await subtle().importKey('raw', bytesArg(input.publicKey, { size: 32 }), 'Ed25519', false, ['verify']);
        return { valid: await subtle().verify('Ed25519', key, bytesArg(input.signature, { size: 64 }), bytesArg(input.data)) };
      } catch (error) { if (error instanceof ClientLocalError) throw error; return { valid: false }; }
    },
  };
  // Migration only (host-document handle.call; never a guest): bring an existing key into a handle once.
  async function importKey(input, signal) {
    cryptoArgs(input, ['as', 'key']);
    const bytes = bytesArg(input.key, { max: 2400 });
    if (AS_CONTENT.has(input.as)) { if (bytes.byteLength !== 32) throw localError('invalid-arguments'); return { handle: tables.add(signal, await contentEntry(input.as, bytes)) }; }
    if (!AS_PRIVATE.has(input.as)) throw localError('invalid-arguments');
    const entry = await privateEntry(input.as, bytes);
    return { handle: tables.add(signal, entry), publicKey: new Uint8Array(entry.publicKey) };
  }
  async function x25519Shared(privateBytes, peer) {
    const libs = await loadCryptoLibraries();
    let shared;
    try { shared = libs.x25519.getSharedSecret(privateBytes, peer); } catch { throw localError('invalid-arguments'); }
    if (shared.every((b) => b === 0)) throw localError('invalid-arguments');   // a low-order peer point
    return shared;
  }
  // RFC 5869 (extract+expand) over HMAC-SHA-256. The combiner info (info || eph-pub || recipient-pub || pq-ct)
  // can exceed 1024 bytes and Node's subtle HKDF refuses longer info; this computes the same output.
  async function hkdfFrom(ikm, salt, info) {
    const hmacKey = (bytes) => subtle().importKey('raw', bytes, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
    const prk = new Uint8Array(await subtle().sign('HMAC', await hmacKey(salt.byteLength ? salt : new Uint8Array(32)), ikm));
    const key = await hmacKey(prk);
    const out = new Uint8Array(32); let prev = new Uint8Array(); let at = 0; let counter = 1;
    while (at < out.byteLength) {
      prev = new Uint8Array(await subtle().sign('HMAC', key, concatBytes(prev, info, new Uint8Array([counter]))));
      out.set(prev.subarray(0, Math.min(prev.length, out.byteLength - at)), at);
      at += prev.length; counter += 1;
    }
    return out;
  }
  // ---- D. key approval (rodo awai_key_approval): a declared, host-held signing key signs a statement the host
  // builds and shows: operation, recipient, amount (if any) and the payload's SHA-256. The signed bytes are that
  // statement, so what the user saw is exactly what is signed.
  const SUMMARY_KEYS = ['operation', 'recipient', 'amount'];
  async function sign(input, signal) {
    cryptoArgs(input, ['key', 'summary', 'payload']);
    const entry = tables.get(signal, input.key, (candidate) => candidate.cls === 'signing' && candidate.persistent);
    const declared = declaredKeys.get(entry.persistent);
    const summary = input.summary;
    // No summary, no signature: every field is plain words the dialog can show.
    if (!record(summary) || !['operation', 'recipient'].every((key) => Object.hasOwn(summary, key)) || Object.keys(summary).some((key) => !SUMMARY_KEYS.includes(key))
        || !plainWords(summary.operation, 60) || !plainWords(summary.recipient, 120) || (Object.hasOwn(summary, 'amount') && !plainWords(summary.amount, 60))) throw localError('invalid-arguments');
    if (!declared.operations.includes(summary.operation)) throw localError('not-declared');
    const payload = bytesArg(input.payload, { max: SIGN_PAYLOAD_MAX });
    const digest = hexOf(new Uint8Array(await subtle().digest('SHA-256', payload)));
    const statementObject = { schema: 'kotoba.key-approval.v1', app: appId, key: entry.persistent, operation: summary.operation, recipient: summary.recipient,
      ...(Object.hasOwn(summary, 'amount') ? { amount: summary.amount } : {}), 'payload-sha256': digest };
    const statement = new TextEncoder().encode(canonical(statementObject));
    const scope = canonical([summary.operation, summary.recipient]);
    // Continuous approval covers only a declared continuous key, the same operation and recipient, and no amount.
    const granted = declared.approval === 'continuous' && !Object.hasOwn(summary, 'amount') && continuousGrants.get(entry.persistent)?.has(scope);
    if (!granted) {
      const approved = await confirm(Object.freeze({ kind: 'sign', profile, app: appIdentity, payload: null,
        sign: Object.freeze({ key: entry.persistent, operation: summary.operation, recipient: summary.recipient, amount: summary.amount ?? null, sha256: digest,
          bytes: payload.byteLength, continuous: declared.approval === 'continuous' && !Object.hasOwn(summary, 'amount'), withdrawal: declared.withdrawal ?? null }) }), signal).catch(() => { throw localError('busy'); });
      if (approved !== true) throw localError('not-approved');
      if (declared.approval === 'continuous' && !Object.hasOwn(summary, 'amount')) {
        if (!continuousGrants.has(entry.persistent)) continuousGrants.set(entry.persistent, new Set());
        continuousGrants.get(entry.persistent).add(scope);
      }
    }
    const signature = new Uint8Array(await subtle().sign('Ed25519', entry.key, statement));
    return { signature, statement, publicKey: new Uint8Array(entry.publicKey) };
  }
  return Object.freeze({
    calls, importKey, tables,
    revokeSigning(id) { if (id === undefined) continuousGrants.clear(); else continuousGrants.delete(id); },
    signingApprovals() { return [...continuousGrants].map(([key, scopes]) => Object.freeze({ key, scopes: Object.freeze([...scopes].map((s) => Object.freeze(JSON.parse(s)))) })); },
    async clear() { continuousGrants.clear(); if (keyStore) await keyStore.clear(appId); },
  });
}

// ---- C. Device-local host commands (karute / rodo awai_local_inference) ----
// The host registers a fixed allowlist of named commands, each with input and output schemas and byte caps,
// and attests that the command keeps data on the device: no network I/O, no logging, no retention. The guest
// calls only commands its descriptor declares. A call with user data shows Legal's short confirmation (not the
// egress dialog); inputs and outputs are never logged.
export const CLIENT_DEVICE_COMMAND_CONFORMANCE_SCHEMA = 'kotoba.device-command-conformance.v1';
const COMMAND_NAME = /^[a-z][a-z0-9_]{0,63}$/;
const ACTION_NAME = /^[a-z][a-z0-9_-]{0,31}$/;
function schemaProblem(schema) {
  if (!record(schema) || schema.type !== 'object' || !exactKeys(schema, ['type', 'fields', 'required']) || !record(schema.fields) || !Array.isArray(schema.required)) return 'invalid-schema';
  const names = Object.keys(schema.fields);
  if (names.length === 0 || names.length > 32 || !schema.required.every((name) => names.includes(name))) return 'invalid-schema';
  for (const [name, field] of Object.entries(schema.fields)) {
    if (!/^[A-Za-z][A-Za-z0-9_]{0,31}$/.test(name) || !record(field)) return 'invalid-schema';
    if (field.type === 'string' || field.type === 'bytes') { if (!exactKeys(field, ['type', 'max-bytes']) || !limit(field['max-bytes'], 1, CLIENT_PORT_BYTES_MAX)) return 'invalid-schema'; }
    else if (field.type === 'integer') { if (!exactKeys(field, ['type', 'min', 'max']) || !Number.isSafeInteger(field.min) || !Number.isSafeInteger(field.max) || field.min > field.max) return 'invalid-schema'; }
    else if (field.type === 'enum') { if (!exactKeys(field, ['type', 'values']) || !Array.isArray(field.values) || field.values.length === 0 || field.values.length > 64 || !field.values.every((v) => typeof v === 'string' && v.length <= 64)) return 'invalid-schema'; }
    else if (field.type === 'boolean') { if (!exactKeys(field, ['type'])) return 'invalid-schema'; }
    else return 'invalid-schema';
  }
  return null;
}
// Only enums, integers and booleans: no free text and no bytes, so no user data.
const schemaCarriesData = (schema) => Object.values(schema.fields).some((field) => field.type === 'string' || field.type === 'bytes');
function schemaValue(schema, value, maxBytes) {
  if (!record(value) || Object.keys(value).some((key) => !Object.hasOwn(schema.fields, key)) || !schema.required.every((key) => Object.hasOwn(value, key))) return null;
  const out = {}; let total = 0;
  for (const [name, item] of Object.entries(value)) {
    const field = schema.fields[name];
    if (field.type === 'string') { if (typeof item !== 'string') return null; const n = utf8Length(item); if (n > field['max-bytes']) return null; total += n; out[name] = item; }
    else if (field.type === 'bytes') { const bytes = guestBytes(item); if (!bytes || bytes.byteLength > field['max-bytes']) return null; total += bytes.byteLength; out[name] = bytes; }
    else if (field.type === 'integer') { if (!Number.isSafeInteger(item) || item < field.min || item > field.max) return null; out[name] = item; }
    else if (field.type === 'enum') { if (!field.values.includes(item)) return null; out[name] = item; }
    else if (typeof item !== 'boolean') return null; else out[name] = item;
  }
  return total > maxBytes ? null : Object.freeze(out);
}
/** Problems with one registered device-local command. Empty when it may be registered. A command that does
 * network I/O is refused: its attestation must say `network: 'none'`. */
export function clientDeviceCommandProblems(command) {
  const problems = [];
  if (!exactKeys(command, ['name', 'actions', 'run', 'conformance'])) return ['invalid-command-keys'];
  if (typeof command.name !== 'string' || !COMMAND_NAME.test(command.name)) problems.push('invalid-command-name');
  if (typeof command.run !== 'function') problems.push('missing-run');
  const c = command.conformance;
  if (!record(c) || c.schema !== CLIENT_DEVICE_COMMAND_CONFORMANCE_SCHEMA || !plainWords(c.host, 64)) problems.push('missing-conformance-declaration');
  else {
    if (c.network !== 'none') problems.push('command-does-network-io');
    for (const must of ['on-device', 'no-logging', 'no-retention']) if (c[must] !== true) problems.push(`not-declared:${must}`);
  }
  if (!record(command.actions) || Object.keys(command.actions).length === 0 || Object.keys(command.actions).length > 16) problems.push('invalid-actions');
  else for (const [action, spec] of Object.entries(command.actions)) {
    if (!ACTION_NAME.test(action) || !exactKeys(spec, ['input', 'output', 'max-input-bytes', 'max-output-bytes'])
        || !limit(spec['max-input-bytes'], 1, CLIENT_PORT_BYTES_MAX) || !limit(spec['max-output-bytes'], 1, CLIENT_PORT_BYTES_MAX)
        || schemaProblem(spec.input) || schemaProblem(spec.output)) problems.push(`invalid-action:${action}`);
  }
  return problems;
}
const deviceCommandRegistries = new WeakMap();
/** The host's fixed allowlist of device-local commands. Pass it to createClientHostLocal as `deviceCommands`. */
export function createClientDeviceCommands(commands) {
  if (!Array.isArray(commands) || commands.length === 0 || commands.length > 32) throw new TypeError('device commands must be a non-empty list');
  const byName = new Map();
  for (const command of commands) {
    const problems = clientDeviceCommandProblems(command);
    if (problems.length) throw new TypeError(`device command is not registrable: ${problems.join(', ')}`);
    if (byName.has(command.name)) throw new TypeError('duplicate device command');
    byName.set(command.name, Object.freeze({ name: command.name, actions: freezeClone(command.actions), run: command.run.bind(command), conformance: freezeClone(command.conformance) }));
  }
  const registry = Object.freeze({ names: Object.freeze([...byName.keys()]) });
  deviceCommandRegistries.set(registry, byName);
  return registry;
}
function deviceCommandDeclarationProblems(value) {
  if (!Array.isArray(value) || value.length === 0 || value.length > 16) return ['invalid-device-commands'];
  for (const entry of value) {
    if (!exactKeys(entry, ['name', 'actions', 'purpose', 'special-care']) || typeof entry.name !== 'string' || !COMMAND_NAME.test(entry.name)
        || !Array.isArray(entry.actions) || entry.actions.length === 0 || !entry.actions.every((a) => typeof a === 'string' && ACTION_NAME.test(a)) || new Set(entry.actions).size !== entry.actions.length
        || !plainWords(entry.purpose, 120) || typeof entry['special-care'] !== 'boolean') return ['invalid-device-commands'];
  }
  if (new Set(value.map((entry) => entry.name)).size !== value.length) return ['invalid-device-commands'];
  return [];
}
/** Conformance helper for a registry: runs each command's probe input with the network and console trapped.
 * Fails a command that touches fetch, XMLHttpRequest, WebSocket, EventSource, sendBeacon or RTCPeerConnection,
 * that logs anything, or whose output does not match its schema. A native command (Tauri invoke) is invisible to
 * these traps: its host records its own platform evidence, and the result says `native: 'not-observed'`. */
export async function verifyDeviceCommandConformance(registry, probes = {}) {
  const byName = deviceCommandRegistries.get(registry);
  if (!byName) throw new TypeError('a registry from createClientDeviceCommands is required');
  const results = [];
  for (const command of byName.values()) {
    for (const [action, spec] of Object.entries(command.actions)) {
      const probe = probes?.[command.name]?.[action];
      if (!record(probe)) { results.push({ command: command.name, action, ok: false, problems: ['no-probe'] }); continue; }
      const touched = [];
      const saved = {};
      const trap = (name) => function trapped() { touched.push(name); throw new Error('network refused by the device-local conformance probe'); };
      for (const name of ['fetch', 'XMLHttpRequest', 'WebSocket', 'EventSource', 'RTCPeerConnection']) { saved[name] = globalThis[name]; globalThis[name] = trap(name); }
      const beacon = globalThis.navigator?.sendBeacon; if (beacon) globalThis.navigator.sendBeacon = trap('sendBeacon');
      const consoleSaved = {};
      for (const name of ['log', 'info', 'warn', 'error', 'debug', 'trace']) { consoleSaved[name] = console[name]; console[name] = () => { touched.push(`log:${name}`); }; }
      const problems = [];
      try {
        const input = schemaValue(spec.input, probe, spec['max-input-bytes']);
        if (!input) problems.push('probe-does-not-match-input-schema');
        else {
          const output = await command.run({ action, input }, { signal: new AbortController().signal });
          if (!schemaValue(spec.output, output, spec['max-output-bytes'])) problems.push('output-does-not-match-schema');
        }
      } catch { problems.push('run-failed'); }
      finally {
        for (const name of Object.keys(saved)) globalThis[name] = saved[name];
        if (beacon) globalThis.navigator.sendBeacon = beacon;
        for (const name of Object.keys(consoleSaved)) console[name] = consoleSaved[name];
      }
      if (touched.some((name) => !name.startsWith('log:'))) problems.push('network-io');
      if (touched.some((name) => name.startsWith('log:'))) problems.push('logged');
      results.push({ command: command.name, action, ok: problems.length === 0, problems, native: 'not-observed' });
    }
  }
  return Object.freeze({ schema: CLIENT_DEVICE_COMMAND_CONFORMANCE_SCHEMA, ok: results.every((r) => r.ok), results: Object.freeze(results.map(Object.freeze)),
    attested: Object.freeze([...byName.values()].map((c) => Object.freeze({ command: c.name, ...c.conformance }))) });
}
function createDeviceCommandCalls({ declaration, registry, confirm, profile, appIdentity }) {
  const byName = registry ? deviceCommandRegistries.get(registry) : null;
  if (!byName) throw new TypeError('device.command requires a registry from createClientDeviceCommands');
  const declared = new Map(declaration['device-commands'].map((entry) => [entry.name, entry]));
  for (const entry of declared.values()) {
    const command = byName.get(entry.name);
    // The guest may call only what it declared and the host registered.
    if (!command || !entry.actions.every((action) => Object.hasOwn(command.actions, action))) throw new TypeError(`device command is not registered by this host: ${entry.name}`);
  }
  let running = 0;
  return async function deviceCommand(input, signal) {
    cryptoArgs(input, ['command', 'action', 'input']);
    const entry = typeof input.command === 'string' ? declared.get(input.command) : null;
    if (!entry || typeof input.action !== 'string' || !entry.actions.includes(input.action)) throw localError('not-declared');
    const command = byName.get(entry.name); const spec = command.actions[input.action];
    const value = schemaValue(spec.input, input.input, spec['max-input-bytes']);
    if (!value) throw localError(argumentBytes(input.input) > spec['max-input-bytes'] ? 'too-large' : 'invalid-arguments');
    if (running >= 4) throw localError('busy');
    running += 1;
    try {
      if (schemaCarriesData(spec.input)) {
        // Legal 2026-11-22: a short confirmation, each time, with a trusted press after the 600 ms arm.
        const approved = await confirm(Object.freeze({ kind: 'device-local', profile, app: appIdentity, payload: null,
          deviceLocal: Object.freeze({ command: entry.name, action: input.action, purpose: entry.purpose, specialCare: entry['special-care'] }) }), signal).catch(() => { throw localError('busy'); });
        if (approved !== true) throw localError('not-approved');
      }
      if (signal?.aborted) throw localError('unavailable');
      let output;
      try { output = await command.run({ action: input.action, input: value }, { signal }); } catch { throw localError('unavailable'); }   // the command's error is never echoed
      const checked = schemaValue(spec.output, output, spec['max-output-bytes']);
      if (!checked) throw localError('unavailable');
      return { ...checked };
    } finally { running -= 1; }
  };
}

// ---- B. device.pick / device.open ----
export function browserClientPickTarget({ types }) {
  const doc = globalThis.document;
  const field = doc.createElement('input');
  field.type = 'file'; field.accept = types.join(','); field.hidden = true;
  doc.body.append(field);
  const picked = new Promise((resolve) => {
    field.addEventListener('change', async () => { const file = field.files?.[0]; field.remove(); resolve(file ? { name: file.name, type: file.type, bytes: new Uint8Array(await file.arrayBuffer()) } : null); }, { once: true });
    field.addEventListener('cancel', () => { field.remove(); resolve(null); }, { once: true });
  });
  field.click();
  return picked;
}
export function browserClientOpenTarget({ name, type, bytes }) {
  const url = URL.createObjectURL(new File([bytes], name, { type }));
  globalThis.open?.(url, '_blank', 'noopener,noreferrer');
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
const MIME_TYPE = /^[a-z0-9][a-z0-9!#$&^_.+-]{0,63}\/[a-z0-9][a-z0-9!#$&^_.+-]{0,63}$/;
function pickDeclarationProblems(value) {
  if (!exactKeys(value, ['max-bytes', 'mime-types'])) return ['invalid-pick'];
  if (overCap(value['max-bytes'], CLIENT_PORT_BYTES_MAX)) return ['limit-over-global-cap'];
  if (!limit(value['max-bytes'], 1, CLIENT_PORT_BYTES_MAX) || !Array.isArray(value['mime-types']) || value['mime-types'].length === 0 || value['mime-types'].length > 32
      || new Set(value['mime-types']).size !== value['mime-types'].length || !value['mime-types'].every((type) => typeof type === 'string' && MIME_TYPE.test(type))) return ['invalid-pick'];
  return [];
}
function openDeclarationProblems(value) {
  if (!exactKeys(value, ['max-bytes', 'mime-types'])) return ['invalid-open'];
  if (overCap(value['max-bytes'], CLIENT_PORT_BYTES_MAX)) return ['limit-over-global-cap'];
  if (!limit(value['max-bytes'], 1, CLIENT_PORT_BYTES_MAX) || !Array.isArray(value['mime-types']) || value['mime-types'].length === 0
      || new Set(value['mime-types']).size !== value['mime-types'].length) return ['invalid-open'];
  // Opening hands the file to another app on the device: only the save types, and never an opaque file.
  if (!value['mime-types'].every((type) => typeof type === 'string' && Object.hasOwn(CLIENT_SAVE_TYPES, type) && type !== 'application/octet-stream')) return ['open-type-not-allowed'];
  return [];
}

// ---- E. Host-mediated OAuth (ATProto PDS, nagare): PKCE S256, state, PAR, DPoP (ES256, host-held key). ----
function oauthDeclarationProblems(value) {
  if (!Array.isArray(value) || value.length === 0 || value.length > 4) return ['invalid-oauth'];
  const problems = [];
  for (const entry of value) {
    const par = record(entry) && Object.hasOwn(entry, 'par-endpoint');
    if (!exactKeys(entry, ['id', 'issuer', 'authorization-endpoint', 'token-endpoint', 'client-id', 'redirect-uri', 'scope', 'disclosure', ...(par ? ['par-endpoint'] : [])])) { problems.push('invalid-oauth'); continue; }
    if (!validName(entry.id) || !validOrigin(entry.issuer)) { problems.push('invalid-oauth'); continue; }
    // Every endpoint is on the declared authorization server origin; no other origin is reached.
    for (const key of ['authorization-endpoint', 'token-endpoint', ...(par ? ['par-endpoint'] : [])]) {
      if (!validHttpsUrl(entry[key]) || new URL(entry[key]).origin !== entry.issuer || new URL(entry[key]).search || new URL(entry[key]).hash) problems.push('oauth-endpoint-not-on-declared-origin');
    }
    if (!hostAllowed(originHost(entry.issuer), false)) problems.push('internal-address-requires-lan-scope');
    if (!validHttpsUrl(entry['client-id'])) problems.push('invalid-oauth-client-id');
    let redirect = null; try { redirect = new URL(entry['redirect-uri']); } catch { /* invalid */ }
    if (!redirect || redirect.href !== entry['redirect-uri'] || redirect.search || redirect.hash || redirect.username || !/^(https:|[a-z][a-z0-9+.-]*\.[a-z0-9+.-]+:)$/.test(redirect.protocol)) problems.push('invalid-oauth-redirect-uri');
    if (!plainWords(entry.scope, 256) || !/^[\x21-\x7e]+(?: [\x21-\x7e]+)*$/.test(entry.scope)) problems.push('invalid-oauth-scope');
    problems.push(...clientDisclosureProblems(entry.disclosure));
  }
  if (new Set(value.map((entry) => entry?.id)).size !== value.length) problems.push('invalid-oauth');
  return [...new Set(problems)];
}
const OAUTH_RESPONSE_MAX = 65536;
async function dpopProof(session, method, url, accessToken = null) {
  const target = new URL(url);
  const header = { typ: 'dpop+jwt', alg: 'ES256', jwk: session.jwk };
  const claims = { jti: b64url(randomBytes(16)), htm: method, htu: `${target.origin}${target.pathname}`, iat: Math.floor(Date.now() / 1000),
    ...(session.nonces.get(target.origin) ? { nonce: session.nonces.get(target.origin) } : {}),
    ...(accessToken ? { ath: b64url(new Uint8Array(await subtle().digest('SHA-256', new TextEncoder().encode(accessToken)))) } : {}) };
  const signingInput = `${b64url(new TextEncoder().encode(JSON.stringify(header)))}.${b64url(new TextEncoder().encode(JSON.stringify(claims)))}`;
  const signature = new Uint8Array(await subtle().sign({ name: 'ECDSA', hash: 'SHA-256' }, session.dpopKey, new TextEncoder().encode(signingInput)));
  return `${signingInput}.${b64url(signature)}`;
}
const dpopNonceRequested = (response) => /use_dpop_nonce/.test(response.headers.get('www-authenticate') ?? '') || response.status === 400;
async function oauthPost(fetchRequest, session, url, form, signal) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const response = await fetchRequest(new Request(url, { method: 'POST', body: new URLSearchParams(form), credentials: 'omit', referrerPolicy: 'no-referrer', redirect: 'error', mode: 'cors', cache: 'no-store',
      headers: { 'content-type': 'application/x-www-form-urlencoded', DPoP: await dpopProof(session, 'POST', url) }, ...(signal ? { signal } : {}) }));
    const nonce = response.headers.get('dpop-nonce');
    if (nonce && /^[\x21-\x7e]{1,256}$/.test(nonce)) session.nonces.set(new URL(url).origin, nonce);
    const bytes = response.body ? await boundedBytes(response.body, OAUTH_RESPONSE_MAX, 30000, signal) : new Uint8Array();
    let body = null; try { body = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)); } catch { body = null; }
    if (response.ok && record(body)) return body;
    if (attempt === 0 && nonce && dpopNonceRequested(response) && record(body) && body.error === 'use_dpop_nonce') continue;
    throw localError('unavailable');
  }
  throw localError('unavailable');
}
function createOAuthCalls({ declaration, oauthAgent, confirm, profile, appIdentity, tables }) {
  if (typeof oauthAgent !== 'function') throw new TypeError('oauth.authorize requires the host oauthAgent (system browser / Custom Tabs / ASWebAuthenticationSession)');
  const fetchRequest = globalThis.fetch.bind(globalThis);
  const byId = new Map(declaration.oauth.map((entry) => [entry.id, entry]));
  const details = (entry, step) => Object.freeze({ kind: 'oauth', profile, app: appIdentity, disclosure: entry.disclosure, scope: null, payload: null,
    capability: 'host-local', service: 'oauth', operation: step, endpointOrigin: entry.issuer, dataCategories: Object.freeze(['oauth-authorization']), redirectOrigins: Object.freeze([]),
    oauth: Object.freeze({ id: entry.id, issuer: entry.issuer, scope: entry.scope, step, clientId: entry['client-id'], redirectUri: entry['redirect-uri'] }) });
  async function tokens(session, entry, body) {
    // Only a DPoP-bound token for the declared issuer; the tokens stay in the host.
    if (typeof body.access_token !== 'string' || body.access_token.length > 8192 || String(body.token_type).toLowerCase() !== 'dpop') throw localError('unavailable');
    if (Object.hasOwn(body, 'refresh_token') && (typeof body.refresh_token !== 'string' || body.refresh_token.length > 8192)) throw localError('unavailable');
    session.access = body.access_token; session.refresh = body.refresh_token ?? null;
    session.expires = Number.isSafeInteger(body.expires_in) ? Date.now() + body.expires_in * 1000 : null;
    session.sub = typeof body.sub === 'string' && body.sub.length <= 256 ? body.sub : null;
    session.granted = typeof body.scope === 'string' && body.scope.length <= 1024 ? body.scope : entry.scope;
    return { sub: session.sub, scope: session.granted, expiresIn: Number.isSafeInteger(body.expires_in) ? body.expires_in : null };
  }
  return {
    async 'oauth.authorize'(input, signal) {
      cryptoArgs(input, ['id'], ['loginHint']);
      const entry = typeof input.id === 'string' ? byId.get(input.id) : null;
      if (!entry) throw localError('not-declared');
      if (Object.hasOwn(input, 'loginHint') && !plainWords(input.loginHint, 256)) throw localError('invalid-arguments');
      const verifier = b64url(randomBytes(32));
      const challenge = b64url(new Uint8Array(await subtle().digest('SHA-256', new TextEncoder().encode(verifier))));
      const state = b64url(randomBytes(16));
      const pair = await subtle().generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign', 'verify']);
      const jwkFull = await subtle().exportKey('jwk', pair.publicKey);
      const session = { cls: 'oauth', oauth: entry.id, issuer: entry.issuer, dpopKey: pair.privateKey, jwk: Object.freeze({ kty: 'EC', crv: 'P-256', x: jwkFull.x, y: jwkFull.y }), nonces: new Map(), access: null, refresh: null };
      const params = { client_id: entry['client-id'], response_type: 'code', code_challenge: challenge, code_challenge_method: 'S256', state, redirect_uri: entry['redirect-uri'], scope: entry.scope,
        ...(input.loginHint ? { login_hint: input.loginHint } : {}) };
      let browserStarted = null;
      let authorizeUrl;
      if (entry['par-endpoint']) {
        // PAR happens before the browser opens; it is part of the approved request, so consent comes first.
        const approved = await confirm(details(entry, 'authorize'), signal).catch(() => { throw localError('busy'); });
        if (approved !== true) throw localError('not-approved');
        const pushed = await oauthPost(fetchRequest, session, entry['par-endpoint'], params, signal);
        if (typeof pushed.request_uri !== 'string' || pushed.request_uri.length > 1024) throw localError('unavailable');
        authorizeUrl = `${entry['authorization-endpoint']}?${new URLSearchParams({ client_id: entry['client-id'], request_uri: pushed.request_uri })}`;
        browserStarted = Promise.resolve().then(() => oauthAgent({ url: authorizeUrl, redirectUri: entry['redirect-uri'], signal }));
      } else {
        authorizeUrl = `${entry['authorization-endpoint']}?${new URLSearchParams(params)}`;
        // The system browser opens inside the trusted Allow click.
        const approved = await confirm(details(entry, 'authorize'), signal, () => { browserStarted = Promise.resolve(oauthAgent({ url: authorizeUrl, redirectUri: entry['redirect-uri'], signal })); }).catch(() => { throw localError('busy'); });
        if (approved !== true) throw localError('not-approved');
      }
      let redirected;
      try { redirected = new URL(await browserStarted); } catch { throw localError('not-approved'); }
      const expected = new URL(entry['redirect-uri']);
      if (redirected.origin !== expected.origin || redirected.protocol !== expected.protocol || redirected.pathname !== expected.pathname) throw localError('invalid-arguments');
      const query = redirected.searchParams.size ? redirected.searchParams : new URLSearchParams(redirected.hash.slice(1));
      // state must match exactly (CSRF / mix-up); iss, when present, must be the declared issuer (RFC 9207).
      if (query.get('state') !== state || (query.has('iss') && query.get('iss') !== entry.issuer)) throw localError('invalid-arguments');
      if (query.has('error') || !query.get('code') || query.get('code').length > 2048) throw localError('not-approved');
      const body = await oauthPost(fetchRequest, session, entry['token-endpoint'], { grant_type: 'authorization_code', code: query.get('code'), redirect_uri: entry['redirect-uri'], client_id: entry['client-id'], code_verifier: verifier }, signal);
      const shown = await tokens(session, entry, body);
      return { session: tables.add(signal, session), ...shown };
    },
    async 'oauth.refresh'(input, signal) {
      cryptoArgs(input, ['session']);
      const session = tables.get(signal, input.session, (candidate) => candidate.cls === 'oauth');
      if (!session.refresh) throw localError('not-found');
      const entry = byId.get(session.oauth);
      const approved = await confirm(details(entry, 'refresh'), signal).catch(() => { throw localError('busy'); });
      if (approved !== true) throw localError('not-approved');
      const body = await oauthPost(fetchRequest, session, entry['token-endpoint'], { grant_type: 'refresh_token', refresh_token: session.refresh, client_id: entry['client-id'] }, signal);
      return tokens(session, entry, body);
    },
    async 'oauth.release'(input, signal) {
      cryptoArgs(input, ['session']);
      const session = tables.get(signal, input.session, (candidate) => candidate.cls === 'oauth');
      session.access = null; session.refresh = null; tables.release(signal, input.session);
      return {};
    },
  };
}
// For the broker: the OAuth session a guest names in an operation payload, from the same mount and app.
function oauthSessionFor(link, signal, handle, id) {
  return link.tables.get(signal, handle, (entry) => entry.cls === 'oauth' && entry.oauth === id && typeof entry.access === 'string');
}

/** Default link target in the host document: a new top-level browsing context with no opener and no
 * referrer, opened inside the trusted click. A Tauri or Android host passes its own (the system browser). */
export function browserClientLinkTarget(url) {
  globalThis.open?.(url, '_blank', 'noopener,noreferrer');
}

/** A file name the host may save under: the last path segment only, without control, bidi or reserved
 * characters, leading or trailing dots, or a Windows device name, with an extension that matches the type
 * (the type's extension is appended when it does not). null when the type is not an allowed save type. */
export function clientSaveFileName(name, type, declaredExtensions = []) {
  const fixed = typeof type === 'string' && Object.hasOwn(CLIENT_SAVE_TYPES, type) ? CLIENT_SAVE_TYPES[type] : null;
  // An opaque file takes only the extensions its descriptor declared; never an unsafe one.
  const extensions = type === 'application/octet-stream'
    ? (Array.isArray(declaredExtensions) ? declaredExtensions.filter((ext) => typeof ext === 'string' && /^[a-z0-9]{1,8}$/.test(ext) && !UNSAFE_EXTENSIONS.has(ext)) : [])
    : fixed;
  if (!extensions || extensions.length === 0 || typeof name !== 'string' || name.length > 1024) return null;
  const trim = (text) => text.replace(/^[\s.]+|[\s.]+$/g, '');
  let base = trim(name.split(/[\\/]/).pop().replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2066-\u2069\ufeff<>:"|?*%]/g, ''));
  if (!base) base = 'download';
  const dot = base.lastIndexOf('.');
  const extension = dot > 0 ? base.slice(dot + 1).toLowerCase() : '';
  const matches = extensions.includes(extension);
  let stem = trim((matches ? base.slice(0, dot) : base).slice(0, 120)) || 'download';
  if (/^(?:con|prn|aux|nul|com\d|lpt\d)$/i.test(stem.split('.')[0])) stem = `_${stem}`;
  return `${stem}.${matches ? extension : extensions[0]}`;
}

/** Default save target in the host document: a host-origin Blob URL and <a download>, run inside the trusted
 * click. A Tauri or Android host passes its own target (the platform save dialog). */
export function browserClientSaveTarget({ name, type, bytes }) {
  const doc = globalThis.document;
  const url = URL.createObjectURL(new Blob([bytes], { type }));
  const link = doc.createElement('a');
  link.href = url; link.download = name; link.rel = 'noopener';
  doc.body.append(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function validAppIdentity(app) {
  return app === null || (record(app) && Object.keys(app).every((key) => ['name', 'provider', 'privacy-policy'].includes(key))
    && (!Object.hasOwn(app, 'name') || plainWords(app.name, 80)) && (!Object.hasOwn(app, 'provider') || plainWords(app.provider, 120))
    && (!Object.hasOwn(app, 'privacy-policy') || validHttpsUrl(app['privacy-policy'])));
}

/** Host-local calls for one admitted restricted-wasm-v1 app (KOTOBA-968). `admitted` is the result of
 * verifySignedClientDescriptor. `appId` is the host's own id for the app (its registry entry, the Tauri
 * identifier); it must equal the declared `host-local.app-id`, and it is the storage partition, never chosen
 * by the guest. `storage` is a conformant host backend (clientStorageBackendProblems); `consentHost` is the
 * canonical consent host, which shows the save prompt; `saveTarget` writes an approved file. Pass the handle
 * to mountRestrictedClientApp as `hostLocal`; `clearAppData()` deletes all of this app's stored data. */
export function createClientHostLocal({ admitted, appId, storage = null, consentHost = null, saveTarget = browserClientSaveTarget, linkTarget = browserClientLinkTarget, app = null,
  keyStore = null, deviceCommands = null, oauthAgent = null, pickTarget = browserClientPickTarget, openTarget: fileOpenTarget = browserClientOpenTarget } = {}) {
  if (!admittedDescriptors.has(admitted)) throw new TypeError('an admitted descriptor from verifySignedClientDescriptor is required');
  const declaration = admitted.runtime['host-local'];
  if (!record(declaration)) throw new TypeError('the descriptor declares no host-local calls');
  if (typeof appId !== 'string' || appId !== declaration['app-id']) throw new TypeError('the declared app id is not the host app id');
  if (!validAppIdentity(app)) throw new TypeError('invalid app identity');
  const allowed = new Set(declaration.calls.filter((call) => LOCAL_IMPLEMENTED.has(call)));
  let storageCalls = null;
  if (declaration.storage) {
    const problems = clientStorageBackendProblems(storage);
    if (problems.length) throw new TypeError(`storage backend is not conformant: ${problems.join(', ')}`);
    storageCalls = createStorage(storageCore(storage, appId), declaration);
  }
  let confirm = null;
  const signing = (declaration.keys ?? []).some((key) => key.type === 'ed25519');
  if (declaration.save || declaration.links || declaration.pick || declaration.open || declaration['device-commands'] || declaration.oauth || signing) {
    confirm = consentHosts.get(consentHost);
    if (!confirm) throw new TypeError('device.save, device.openLink, device.pick, device.open, device.command, keys.sign and oauth.* require the canonical trusted consent host');
    if (typeof saveTarget !== 'function' || typeof linkTarget !== 'function' || typeof pickTarget !== 'function' || typeof fileOpenTarget !== 'function') throw new TypeError('invalid save, link, pick or open target');
  }
  // KOTOBA-974: persistent keys need a conformant host key store (platform keystore on Tauri / Android).
  if (declaration.keys) {
    const problems = clientKeyStoreProblems(keyStore);
    if (problems.length) throw new TypeError(`key store is not conformant: ${problems.join(', ')}`);
  }
  const profile = admitted.runtime.profile;
  const appIdentityEarly = app === null ? null : freezeClone(app);
  const keyCalls = createKeyCalls({ appId, declaration, keyStore: declaration.keys ? keyStore : null, confirm, profile, appIdentity: appIdentityEarly });
  const deviceCommand = declaration['device-commands'] ? createDeviceCommandCalls({ declaration, registry: deviceCommands, confirm, profile, appIdentity: appIdentityEarly }) : null;
  const oauthCalls = declaration.oauth ? createOAuthCalls({ declaration, oauthAgent, confirm, profile, appIdentity: appIdentityEarly, tables: keyCalls.tables }) : null;
  let picking = false;
  // device.pick: the host prompt, then the OS file chooser opened inside its trusted click; only the chosen file
  // reaches the guest. device.open: hands a file to the device's default app for its type, after the prompt.
  async function pick(input, signal) {
    cryptoArgs(input, [], ['types']);
    const types = input.types ?? declaration.pick['mime-types'];
    if (!Array.isArray(types) || types.length === 0 || !types.every((type) => declaration.pick['mime-types'].includes(type))) throw localError('not-declared');
    if (picking) throw localError('busy');
    picking = true;
    try {
      let chosen = null;
      const approved = await confirm(Object.freeze({ kind: 'pick', profile, app: appIdentityEarly, payload: null, pick: Object.freeze({ types: Object.freeze([...types]), limit: declaration.pick['max-bytes'] }) }),
        signal, () => { chosen = Promise.resolve(pickTarget(Object.freeze({ types: Object.freeze([...types]), maxBytes: declaration.pick['max-bytes'] }))); }).catch(() => { throw localError('busy'); });
      if (approved !== true) throw localError('not-approved');
      let file;
      try { file = await chosen; } catch { throw localError('unavailable'); }
      if (file === null || file === undefined) throw localError('not-approved');
      const bytes = record(file) ? guestBytes(file.bytes) : null;
      if (!bytes || typeof file.name !== 'string' || typeof file.type !== 'string') throw localError('unavailable');
      if (bytes.byteLength > declaration.pick['max-bytes']) throw localError('too-large');
      if (!types.includes(file.type)) throw localError('not-declared');
      const name = file.name.split(/[\\/]/).pop().replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2066-\u2069\ufeff]/g, '').slice(0, 255) || 'file';
      return { name, type: file.type, value: bytes };
    } finally { picking = false; }
  }
  async function openFile(input, signal) {
    if (!exactKeys(input, ['name', 'type', 'value'])) throw localError('invalid-arguments');
    if (!declaration.open['mime-types'].includes(input.type)) throw localError('not-declared');
    const bytes = guestBytes(input.value);
    if (!bytes) throw localError('invalid-arguments');
    if (bytes.byteLength > declaration.open['max-bytes']) throw localError('too-large');
    const name = clientSaveFileName(input.name, input.type);
    if (!name) throw localError('invalid-arguments');
    if (picking) throw localError('busy');
    picking = true;
    try {
      const file = Object.freeze({ name, type: input.type, bytes });
      const approved = await confirm(Object.freeze({ kind: 'open', profile, app: appIdentityEarly, payload: payloadSummary(bytes, input.type),
        open: Object.freeze({ name, type: input.type, bytes: bytes.byteLength, limit: declaration.open['max-bytes'] }) }), signal, () => fileOpenTarget(file)).catch(() => { throw localError('busy'); });
      if (approved !== true) throw localError('not-approved');
      return { opened: true, name };
    } finally { picking = false; }
  }
  const openTarget = linkTarget;
  const appIdentity = app === null ? null : freezeClone(app);
  const target = saveTarget;
  let saving = false;
  async function save(input, signal) {
    if (!exactKeys(input, ['name', 'type', 'value'])) throw localError('invalid-arguments');
    if (!declaration.save['mime-types'].includes(input.type)) throw localError('not-declared');
    const bytes = guestBytes(input.value);
    if (!bytes) throw localError('invalid-arguments');
    if (bytes.byteLength > declaration.save['max-bytes']) throw localError('too-large');
    const name = clientSaveFileName(input.name, input.type, declaration.save['octet-stream-extensions'] ?? []);
    if (!name) throw localError('invalid-arguments');
    if (saving) throw localError('busy');
    saving = true;
    try {
      const file = Object.freeze({ name, type: input.type, bytes });
      let approved;
      try {
        approved = await confirm(Object.freeze({
          kind: 'save', profile: admitted.runtime.profile, app: appIdentity, payload: payloadSummary(bytes, input.type),
          save: Object.freeze({ name, type: input.type, bytes: bytes.byteLength, limit: declaration.save['max-bytes'] }),
        }), signal, () => target(file));
      } catch { throw localError('busy'); }
      if (approved !== true) throw localError('not-approved');
      return { saved: true, name };
    } finally { saving = false; }
  }
  // device.openLink is egress: the URL (its path and query) reaches the destination. Only https, only a declared
  // origin, no credentials, within the declared length; the prompt names the origin and shows the whole URL.
  async function openLink(input, signal) {
    if (!exactKeys(input, ['url']) || typeof input.url !== 'string' || input.url.length > declaration.links['max-url-length']) throw localError('invalid-arguments');
    let url;
    try { url = new URL(input.url); } catch { throw localError('invalid-arguments'); }
    if (url.protocol !== 'https:' || url.username || url.password || url.href.length > declaration.links['max-url-length']) throw localError('invalid-arguments');
    if (!declaration.links.targets.some((target) => linkTargetAllows(target, url))) throw localError('not-declared');
    if (saving) throw localError('busy');
    saving = true;
    try {
      const href = url.href;
      let approved;
      try {
        approved = await confirm(Object.freeze({ kind: 'link', profile: admitted.runtime.profile, app: appIdentity, payload: null,
          link: Object.freeze({ origin: url.origin, url: href }) }), signal, () => openTarget(href));
      } catch { throw localError('busy'); }
      if (approved !== true) throw localError('not-approved');
      return { opened: true };
    } finally { saving = false; }
  }
  async function dispatch(call, input, signal, emit, direct = false) {
    if (typeof call !== 'string' || !allowed.has(call)) throw localError('not-declared');
    if (!record(input) || !plainLocalData(input)) throw localError('invalid-arguments');
    // The bytes a call carries are counted before it waits for anything (finding 5).
    if (argumentBytes(input) > BATCH_BYTES_MAX) throw localError('too-large');
    if (call === 'device.save') return save(input, signal);
    if (call === 'device.openLink') return openLink(input, signal);
    if (call === 'device.pick') return pick(input, signal);
    if (call === 'device.open') return openFile(input, signal);
    if (call === 'device.command') return deviceCommand(input, signal);
    if (call.startsWith('oauth.')) return oauthCalls[call](input, signal);
    // crypto.importKey brings an existing key in once, for migration: host-document code only (handle.call).
    if (call === 'crypto.importKey') { if (!direct) throw localError('not-declared'); return keyCalls.importKey(input, signal); }
    if (KEY_CALL(call)) return keyCalls.calls[call](input, signal);
    return storageCalls.call(call, input, emit, signal);
  }
  const lifetime = new AbortController();
  const handle = Object.freeze({
    // Clearing deletes the stored data and this app's persistent keys (crypto-shred, Legal L4).
    async clearAppData() { if (storageCalls) await storageCalls.clearAll(); await keyCalls.clear(); },
    // KOTOBA-974 D: continuous signing approvals are revocable from the host's settings at any time.
    revokeSigningApproval(id) { keyCalls.revokeSigning(id); },
    signingApprovals() { return keyCalls.signingApprovals(); },
    // Direct calls from host-document code: a trusted-page-v1 app's last release copies its IndexedDB data into
    // host-local storage before it moves to restricted-wasm-v1 (migration). Results and errors match the guest's.
    async call(call, args) {
      try { return { ok: true, result: (await dispatch(call, args, lifetime.signal, () => {}, true)) ?? null }; }
      catch (error) { return { ok: false, error: error instanceof ClientLocalError ? error.message : 'unavailable' }; }
    },
  });
  canonicalHostLocals.set(handle, Object.freeze({ dispatch, descriptor: canonical(admitted.runtime), keys: keyCalls,
    storage: storageCalls ? Object.freeze({ core: storageCore(storage, appId), declaration }) : null }));
  return handle;
}

/** Delete an app's host-local data, for example when the user removes the app (Legal condition 4). */
export async function clearClientAppData({ appId, storage = null, keyStore = null }) {
  if (typeof appId !== 'string' || !APP_ID.test(appId)) throw new TypeError('invalid app id');
  if (storage === null && keyStore === null) throw new TypeError('storage or keyStore is required');
  if (storage !== null) {
    const problems = clientStorageBackendProblems(storage);
    if (problems.length) throw new TypeError(`storage backend is not conformant: ${problems.join(', ')}`);
    const core = storageCore(storage, appId);
    try { await core.run(() => core.clear()); } catch { throw new Error('unavailable'); }
  }
  // KOTOBA-974: the app's persistent keys go with it.
  if (keyStore !== null) {
    const problems = clientKeyStoreProblems(keyStore);
    if (problems.length) throw new TypeError(`key store is not conformant: ${problems.join(', ')}`);
    try { await keyStore.clear(appId); } catch { throw new Error('unavailable'); }
  }
}

/** Wrap a raw host key-value store as a storage backend that encrypts at rest (Legal L3, Yataverse review
 * finding 3):
 * - values: AES-GCM-256, padded to a multiple of 4 KiB so the stored size shows only a bucket;
 * - names: a record is filed under HMAC-SHA256(index key, name); the name, size and time are inside an
 *   encrypted meta record, so neither file names nor exact sizes are readable at rest;
 * - the additional data binds every ciphertext to its partition and index, so a record copied elsewhere does
 *   not decrypt;
 * - keys: a non-extractable AES-GCM key and HMAC key per partition. They come from `keyProvider`
 *   ({ keys(partition, { create }) -> { encryption, index } | null, delete(partition) }), which a Tauri or
 *   Android host backs with the platform keystore. Without one they are kept in `kv`, which is acceptable
 *   only for a plain browser host with no OS backup (key-custody 'host-profile').
 * `kv`: async get(k), entries(prefix) -> [[k, v]], deletePrefix(prefix), and update(keys, decide): read `keys`
 * and apply decide(currentValues) -> { writes: [['put', k, v] | ['delete', k]], result } in one transaction
 * (abort when decide returns { abort }). It must keep CryptoKey objects as they are (IndexedDB does).
 * `conformance` is the host's attested declaration of the other MUSTs; it is required. */
export function createEncryptedClientStorageBackend({ kv, conformance, keyProvider = null }) {
  for (const method of ['get', 'entries', 'update', 'deletePrefix']) if (typeof kv?.[method] !== 'function') throw new TypeError('invalid key-value store');
  if (!record(conformance)) throw new TypeError('the host must supply its storage conformance declaration');
  if (keyProvider !== null && (typeof keyProvider.keys !== 'function' || typeof keyProvider.delete !== 'function')) throw new TypeError('invalid key provider');
  const subtle = globalThis.crypto.subtle;
  const text = new TextEncoder();
  const keyName = (partition) => `k\u0000${partition}`;
  const metaPrefix = (partition) => `m\u0000${partition}\u0000`;
  const dataPrefix = (partition) => `d\u0000${partition}\u0000`;
  const aad = (kind, partition, index) => text.encode(`kotoba.client-storage.v2\n${kind}\n${partition}\n${index}`);
  const PAD = 4096;
  const pending = new Map();
  const usable = (keys) => record(keys) && keys.encryption instanceof CryptoKey && keys.index instanceof CryptoKey
    && keys.encryption.extractable === false && keys.index.extractable === false;
  async function partitionKeys(partition, create) {
    if (keyProvider) {
      const keys = await keyProvider.keys(partition, { create });
      if (keys === null && !create) return null;
      if (!usable(keys)) throw new Error('key provider returned unusable keys');
      return keys;
    }
    const existing = await kv.get(keyName(partition));
    if (existing || !create) return existing ?? null;
    if (!pending.has(partition)) {
      pending.set(partition, (async () => {
        const encryption = await subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
        const index = await subtle.generateKey({ name: 'HMAC', hash: 'SHA-256', length: 256 }, false, ['sign']);
        return kv.update([keyName(partition)], ([current]) => (current ? { writes: [], result: current }
          : { writes: [['put', keyName(partition), { encryption, index }]], result: { encryption, index } }));
      })().finally(() => pending.delete(partition)));
    }
    return pending.get(partition);
  }
  const indexOf = async (keys, partition, name) => hexBytes(new Uint8Array(await subtle.sign('HMAC', keys.index, text.encode(`${partition}\n${name}`))));
  const seal = async (keys, kind, partition, index, bytes) => {
    const iv = globalThis.crypto.getRandomValues(new Uint8Array(12));
    return { iv, data: new Uint8Array(await subtle.encrypt({ name: 'AES-GCM', iv, additionalData: aad(kind, partition, index) }, keys.encryption, bytes)) };
  };
  const open = async (keys, kind, partition, index, sealed) => new Uint8Array(await subtle.decrypt({ name: 'AES-GCM', iv: sealed.iv, additionalData: aad(kind, partition, index) }, keys.encryption, sealed.data));
  const padded = (bytes) => { const out = new Uint8Array(Math.ceil(Math.max(bytes.byteLength, 1) / PAD) * PAD); out.set(bytes); return out; };
  // The meta plaintext is padded too, so the name's length is not readable either.
  const metaBytes = (meta) => { const body = text.encode(JSON.stringify(meta)); const out = new Uint8Array(Math.ceil((body.byteLength + 4) / 256) * 256); new DataView(out.buffer).setUint32(0, body.byteLength); out.set(body, 4); return out; };
  const metaOf = (bytes) => JSON.parse(new TextDecoder().decode(bytes.subarray(4, 4 + new DataView(bytes.buffer, bytes.byteOffset).getUint32(0))));
  const declared = Object.freeze({ ...conformance, schema: CLIENT_STORAGE_CONFORMANCE_SCHEMA, 'encrypted-at-rest': true, 'encrypted-names': true,
    'key-custody': keyProvider ? 'platform-keystore' : 'host-profile' });
  return Object.freeze({
    conformance: declared,
    async get(partition, name) {
      const keys = await partitionKeys(partition, false);
      if (!keys) return null;
      const index = await indexOf(keys, partition, name);
      const meta = await kv.get(`${metaPrefix(partition)}${index}`);
      if (!meta) return null;
      const info = metaOf(await open(keys, 'meta', partition, index, meta));
      const data = await kv.get(`${dataPrefix(partition)}${index}`);
      if (info.name !== name || !data) throw new Error('storage record mismatch');
      return { value: (await open(keys, 'data', partition, index, data)).slice(0, info.bytes), version: meta.version };
    },
    async list(partition) {
      const keys = await partitionKeys(partition, false);
      if (!keys) return [];
      const prefix = metaPrefix(partition);
      const out = [];
      for (const [stored, meta] of await kv.entries(prefix)) {
        const info = metaOf(await open(keys, 'meta', partition, stored.slice(prefix.length), meta));
        out.push({ key: info.name, bytes: info.bytes, modified: info.modified, version: meta.version });
      }
      return out;
    },
    // Encrypt every value first; then one transaction checks each expected version, assigns versions and writes.
    async batch(partition, ops) {
      const keys = await partitionKeys(partition, ops.some((op) => op.put));
      if (!keys) return ops.every((op) => !Object.hasOwn(op, 'expect') || op.expect === 0) ? { versions: Object.fromEntries(ops.map((op) => [op.delete.key, 0])) } : { conflict: true };
      const now = Date.now();
      const prepared = [];
      for (const op of ops) {
        const name = (op.put ?? op.delete).key;
        const index = await indexOf(keys, partition, name);
        const entry = { name, index, expect: op.expect, put: null };
        if (op.put) {
          entry.put = {
            meta: await seal(keys, 'meta', partition, index, metaBytes({ name, bytes: op.put.value.byteLength, modified: now })),
            data: await seal(keys, 'data', partition, index, padded(op.put.value)),
          };
        }
        prepared.push(entry);
      }
      const metaKeys = [...new Set(prepared.map((entry) => `${metaPrefix(partition)}${entry.index}`))];
      return kv.update(metaKeys, (current) => {
        const versions = new Map(metaKeys.map((key, i) => [key, current[i]?.version ?? 0]));
        const writes = []; const result = {};
        for (const entry of prepared) {
          const metaKey = `${metaPrefix(partition)}${entry.index}`; const dataKey = `${dataPrefix(partition)}${entry.index}`;
          const version = versions.get(metaKey);
          if (entry.expect !== undefined && entry.expect !== version) return { abort: true, result: { conflict: true } };
          if (entry.put) {
            versions.set(metaKey, version + 1);
            writes.push(['put', metaKey, { ...entry.put.meta, version: version + 1 }], ['put', dataKey, entry.put.data]);
            result[entry.name] = version + 1;
          } else {
            versions.set(metaKey, 0);
            writes.push(['delete', metaKey], ['delete', dataKey]);
            result[entry.name] = 0;
          }
        }
        return { writes, result: { versions: result } };
      });
    },
    // Deleting the partition keys as well makes any leftover copy of the ciphertext unreadable.
    async clear(partition) {
      await kv.deletePrefix(metaPrefix(partition)); await kv.deletePrefix(dataPrefix(partition));
      if (keyProvider) await keyProvider.delete(partition);
      else await kv.update([keyName(partition)], () => ({ writes: [['delete', keyName(partition)]], result: null }));
    },
  });
}

function indexedDbKv(idb, name) {
  let opened = null;
  const open = () => (opened ??= new Promise((resolve, reject) => {
    const request = idb.open(name, 1);
    request.onupgradeneeded = () => request.result.createObjectStore('kv');
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => { opened = null; reject(new Error('storage open failed')); };
  }));
  const transaction = async (mode, body) => {
    const db = await open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('kv', mode); let result; let aborted = false;
      body(tx.objectStore('kv'), (value) => { result = value; }, () => { aborted = true; tx.abort(); });
      tx.oncomplete = () => resolve(result);
      tx.onerror = () => { if (!aborted) reject(new Error('storage transaction failed')); };
      tx.onabort = () => (aborted ? resolve(result) : reject(new Error('storage transaction aborted')));
    });
  };
  const range = (prefix) => globalThis.IDBKeyRange.bound(prefix, `${prefix}￿`);
  return Object.freeze({
    get: (key) => transaction('readonly', (store, done) => { const r = store.get(key); r.onsuccess = () => done(r.result ?? null); }),
    // Read the keys, decide synchronously and write, all inside one readwrite transaction.
    update: (keys, decide) => transaction('readwrite', (store, done, abort) => {
      const current = new Array(keys.length); let left = keys.length;
      const apply = () => {
        const decision = decide(current);
        done(decision.result);
        if (decision.abort) { abort(); return; }
        for (const [kind, key, value] of decision.writes) { if (kind === 'put') store.put(value, key); else store.delete(key); }
      };
      if (left === 0) { apply(); return; }
      keys.forEach((key, i) => { const r = store.get(key); r.onsuccess = () => { current[i] = r.result ?? null; left -= 1; if (left === 0) apply(); }; });
    }),
    deletePrefix: (prefix) => transaction('readwrite', (store) => { store.delete(range(prefix)); }),
    entries: (prefix) => transaction('readonly', (store, done) => {
      const keys = store.getAllKeys(range(prefix)); const values = store.getAll(range(prefix));
      values.onsuccess = () => done(keys.result.map((key, i) => [key, values.result[i]]));
    }),
  });
}

/** A storage backend on IndexedDB in the trusted host origin, encrypted at rest with encrypted names. The host
 * supplies `conformance`, its attested declaration (there is no default). A plain browser host declares
 * 'no-cloud-backup': 'no-os-backup' (browsers do not back site data up to an OS cloud), may keep its keys in
 * IndexedDB and calls clearAppData / clearClientAppData from its settings and when the user removes the app.
 * A host whose data directory an OS backs up (a Tauri WebView on Android or macOS) declares true only with
 * backup disabled (allowBackup="false" with dataExtractionRules, or excludedFromBackup) and must pass a
 * `keyProvider` backed by the platform keystore (docs/client-runtime-review-20261122-host-local.md, T4, T6). */
export function createIndexedDbClientStorageBackend({ indexedDB = globalThis.indexedDB, name = 'kotoba-client-host-storage-v2', conformance, keyProvider = null } = {}) {
  if (!indexedDB || typeof indexedDB.open !== 'function') throw new TypeError('IndexedDB is required');
  return createEncryptedClientStorageBackend({ kv: indexedDbKv(indexedDB, name), conformance, keyProvider });
}

/** Host-adapter conformance check for host-local storage (Legal's MUSTs, 2026-11-22). Every host (browser,
 * Tauri, Android) runs it against its real backend in its own test suite and records the report with the
 * runtime digest it vendors. Behaviour it can observe is tested (isolation, round trip, versions and
 * compare-and-swap inside the backend, all-or-nothing batch, clear); the MUSTs it cannot (OS cloud backup, key
 * custody, encryption on disk, removal with the app, no logging) are reported as declared, `verified: false`, and
 * the host attaches its own evidence (Android allowBackup=false plus dataExtractionRules or noBackupFilesDir;
 * Keystore / Keychain keys with kSecAttrSynchronizable=false and a ThisDeviceOnly accessibility; files
 * excludedFromBackup). */
export async function verifyHostStorageConformance(backend) {
  const results = [];
  const add = (name, passed, message, verified = true) => results.push(Object.freeze({ case: name, passed, verified, message }));
  const problems = clientStorageBackendProblems(backend);
  add('declaration', problems.length === 0, problems.join(', ') || 'declared');
  if (problems.length === 0) {
    const nonce = hexBytes(globalThis.crypto.getRandomValues(new Uint8Array(8)));
    const a = `conformance.a${nonce}.test`; const b = `conformance.b${nonce}.test`;
    const value = globalThis.crypto.getRandomValues(new Uint8Array(64));
    try {
      const first = await backend.batch(a, [{ put: { key: 'files/probe', value }, expect: 0 }]);
      add('version-assigned', first?.versions?.['files/probe'] === 1, 'the backend assigns version 1 to a new key');
      const back = await backend.get(a, 'files/probe');
      add('round-trip', back?.value instanceof Uint8Array && hexBytes(back.value) === hexBytes(value) && back.version === 1, 'stored bytes and version come back unchanged');
      add('compare-and-swap', (await backend.batch(a, [{ put: { key: 'files/probe', value }, expect: 0 }]))?.conflict === true
        && (await backend.get(a, 'files/probe'))?.version === 1, 'a stale expected version is refused inside the backend and changes nothing');
      add('isolation-get', (await backend.get(b, 'files/probe')) === null, 'another partition cannot read the value');
      add('isolation-list', !(await backend.list(b)).some((entry) => entry.key === 'files/probe'), 'another partition does not list the key');
      add('list', (await backend.list(a)).some((entry) => entry.key === 'files/probe' && entry.bytes === 64 && Number.isFinite(entry.modified) && entry.version === 1), 'list reports name, size, time and version');
      const atomic = await backend.batch(a, [{ put: { key: 'files/second', value } }, { delete: { key: 'files/probe' }, expect: 9 }]);
      add('atomic', atomic?.conflict === true && (await backend.get(a, 'files/second')) === null && (await backend.get(a, 'files/probe')) !== null, 'a batch with one conflict applies nothing');
      await backend.batch(a, [{ put: { key: 'files/second', value } }, { delete: { key: 'files/probe' } }]);
      add('batch', (await backend.get(a, 'files/probe')) === null && (await backend.get(a, 'files/second')) !== null, 'a batch applies its puts and deletes');
      await backend.clear(a);
      add('clear', (await backend.get(a, 'files/second')) === null && (await backend.list(a)).length === 0, 'clear removes the partition');
    } catch { add('behaviour', false, 'the backend failed during the probe'); }
    finally { try { await backend.clear(a); await backend.clear(b); } catch { /* reported above */ } }
    for (const must of ['no-cloud-backup', 'key-custody', 'encrypted-at-rest', 'encrypted-names', 'removed-with-app', 'no-logging']) {
      add(must, true, `declared by the host as ${JSON.stringify(backend.conformance[must])}; attach the host evidence`, false);
    }
  }
  return Object.freeze({ schema: 'kotoba.host-storage-conformance-report.v1', conformant: results.length > 0 && results.every((r) => r.passed), results: Object.freeze(results) });
}
