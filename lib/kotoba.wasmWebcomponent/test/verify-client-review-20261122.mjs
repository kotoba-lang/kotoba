// KOTOBA-159 owner decisions of 2026-11-22: findings 1, 7, 8 (+ P1, D1), 9, R3, R4, R5 (+ D4) and D2.
// Each block is a negative control: it fails on the runtime at kotoba-lang/kotoba main e7a264839
// (sha256 f8e5336d…d5ed) and passes with this change. Fake DOM and stubbed fetch; no network.
import assert from 'node:assert/strict';
import { DISCLOSURE } from './client-runtime-fixtures.mjs';

class Mouse { constructor(type) { this.type = type; this.isTrusted = true; } }
class Element {
  constructor(tag) { this.tagName = tag; this.listeners = new Map(); this.isConnected = true; this.open = false; this.textContent = ''; this.hidden = false; }
  append() {} setAttribute() {} focus() { focusedElement = this; } remove() { this.isConnected = false; }
  addEventListener(type, fn) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn]); }
  dispatch(type, event = {}) { event.currentTarget = this; for (const fn of this.listeners.get(type) ?? []) fn(event); }
  showModal() { this.open = true; } close() { this.open = false; }
}
let now = 0; let focusedElement = null;
const made = [];
globalThis.document = {
  body: new Element('body'), defaultView: { MouseEvent: Mouse, performance: { now: () => now } },
  createElement(tag) { const el = new Element(tag); made.push(el); return el; },
};
// KOTOBA_CLIENT_RUNTIME=<path> runs the same cases against another copy (for example main's file);
// KOTOBA_NEGATIVE_CONTROL=1 then reports each section instead of stopping at the first failure.
const runtimeModule = await import(process.env.KOTOBA_CLIENT_RUNTIME ?? '../src/kotoba-client-runtime.js');
const negativeControl = process.env.KOTOBA_NEGATIVE_CONTROL === '1';
const outcomes = [];
async function section(name, body) {
  if (!negativeControl) return body();
  // A rule that is missing can leave a consent pending forever; that counts as a failure here.
  try { await Promise.race([body(), new Promise((_, reject) => setTimeout(() => reject(new Error('timed out: the expected refusal never came')), 3000))]); outcomes.push([name, 'pass']); } catch (error) { outcomes.push([name, `fail: ${String(error?.message).split('\n')[0].slice(0, 100)}`]); }
}
const {
  clientRuntimeProblems, clientPeerEndpointProblems, clientAddressScope, clientEndpointAllowsRequest,
  createClientConsentHost, createClientOperationBroker, verifyClientArtifact, mountRestrictedClientApp,
  verifyPeerAdapterScopeConformance, CLIENT_CONSENT_TEXT, PEER_TRANSFER_MAX_BYTES,
} = runtimeModule;
// Against a runtime without finding 9, strip the new keys so the other sections exercise their own rule.
const legacy = typeof runtimeModule.clientDisclosureProblems !== 'function';
const strip = (op) => { if (!legacy) return op; const { disclosure: _d, scope: _s, ...rest } = op; return rest; };
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const descriptor = (operations, profile = 'restricted-wasm-v1') => ({
  schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile, entry: 'index.html',
  'local-state': { adapter: 'memory', schema: 's', version: 1 }, operations: operations.map(strip),
});
const http = (endpoint, extra = {}) => ({
  capability: 'net/fetch', service: 'svc', operation: 'op', consent: 'each-operation', disclosure: DISCLOSURE,
  'data-categories': ['x'], endpoint, ...extra,
});
const errors = (ops, profile) => clientRuntimeProblems(descriptor(ops, profile), ['net/fetch', 'peer/sync'], 'https://app.example').map((p) => p.error);

function harness(operation, { profile = 'restricted-wasm-v1', fetchStub, peerAdapters, locale, app } = {}) {
  const before = made.length;
  const consentHost = legacy ? createClientConsentHost() : createClientConsentHost({ locale });
  const mine = made.slice(before);
  const dialog = mine.find((el) => el.tagName === 'dialog');
  const [deny, allow] = mine.filter((el) => el.tagName === 'button');
  const byClass = (name) => mine.find((el) => el.className === name);
  const saved = globalThis.fetch;
  if (fetchStub) globalThis.fetch = fetchStub;
  const broker = createClientOperationBroker({
    runtime: descriptor([operation], profile), requestedCapabilities: [operation.capability], approvedOperations: [strip(operation)],
    hostSupportedOperations: [[operation.capability, operation.service, operation.operation]], consentHost, peerAdapters,
    ...(app && !legacy ? { app } : {}),
  });
  globalThis.fetch = saved;
  const approve = () => { now += 600; allow.dispatch('pointerdown', new Mouse('pointerdown')); allow.dispatch('click', new Mouse('click')); };
  return {
    broker, dialog, deny, allow, approve, consentHost, title: mine.find((el) => el.tagName === 'h2'), focused: () => focusedElement,
    summary: byClass('kotoba-client-consent-summary'), note: byClass('kotoba-client-consent-note') ?? mine.find((el) => el.tagName === 'p'),
    scope: byClass('kotoba-client-consent-scope'), payload: byClass('kotoba-client-consent-payload'),
    fullToggle: byClass('kotoba-client-consent-full'), details: byClass('kotoba-client-consent-details'),
    selector: { capability: operation.capability, service: operation.service, operation: operation.operation },
  };
}
const okFetch = async () => ({ ok: true, status: 200, type: 'cors', url: 'https://svc.example/x', body: null });

// ---- Finding 7: a generic network rail is refused by its shape, not by its capability name.
await section('Finding 7', async () => {
  for (const endpoint of [
    { origin: 'https://svc.example', method: 'GET', path: '/:anything' },
    { origin: 'https://svc.example', method: 'POST', path: '/:a/:b' },
    { origin: 'https://svc.example', routes: [{ method: 'GET', path: '/:host', 'query-params': ['u'] }] },
    { origin: 'https://*.svc.example', method: 'GET', path: '/x' },
  ]) assert.deepEqual(errors([http(endpoint)]), ['generic-network-endpoint'], JSON.stringify(endpoint));
  assert.deepEqual(errors([http({ origin: 'https://svc.example', method: 'GET', path: '/items/:id' })]), [], 'a fixed segment restricts the path');
  assert.deepEqual(errors([http({ origin: 'https://svc.example', method: 'GET', path: '/' })]), [], 'the root path is one fixed path');
});

// ---- Findings 8, P1, D1: internal addresses need `scope: "lan"`, which the dialog prints.
await section('Findings 8, P1, D1', async () => {
  for (const origin of ['https://127.0.0.1', 'https://10.0.0.5', 'https://192.168.1.1:8443', 'https://169.254.169.254', 'https://100.64.0.1', 'https://0.1.2.3', 'https://localhost', 'https://nas.local']) {
    const endpoint = { origin, method: 'GET', path: '/x' };
    assert.deepEqual(errors([http(endpoint)]), ['internal-address-requires-lan-scope'], origin);
    assert.deepEqual(errors([http(endpoint, { scope: 'lan' })]), [], `${origin} with scope lan`);
    assert.equal(clientEndpointAllowsRequest(endpoint, `${origin}/x`), false, `${origin} preflight`);
    assert.equal(clientEndpointAllowsRequest(endpoint, `${origin}/x`, 'GET', { scope: 'lan' }), true, `${origin} preflight with lan`);
  }
  // Browser-action origins and redirect origins are covered too.
  assert.deepEqual(errors([http({ origin: 'https://10.0.0.5', 'browser-action': 'open' })]), ['internal-address-requires-lan-scope']);
  assert.deepEqual(errors([http({ origin: 'https://svc.example', method: 'GET', path: '/x' }, { 'redirect-origins': ['https://169.254.169.254'] })]), ['internal-address-requires-lan-scope']);
  // A LAN scope must not cover a public host, and only "lan" is a scope.
  assert.deepEqual(errors([http({ origin: 'https://svc.example', method: 'GET', path: '/x' }, { scope: 'lan' })]), ['lan-scope-requires-internal-addresses']);
  assert.deepEqual(errors([http({ origin: 'https://10.0.0.5', method: 'GET', path: '/x' }, { scope: 'internet' })]), ['invalid-scope']);
  // Peer endpoints, relay hops and the receive listener (P1, D1).
  const peer = '12D3KooWJxXy9juQKbQW8wSCuW7oGiNTJWmfg3ZkCqfaRoiLBM4P';
  const relay = '12D3KooWQjhcGAFVLzNAnA5wmt15oT6Jz6m9LqE6vSQH2FnR1aVB';
  const base = { transport: 'libp2p', 'peer-id': peer, protocol: '/ipfs/bitswap/1.2.0', action: 'get', 'max-request-bytes': 1024, 'max-response-bytes': 1024, 'timeout-ms': 1000 };
  for (const ip of ['127.0.0.1', '10.0.0.5', '192.168.1.1', '172.16.0.9', '169.254.169.254', '100.64.0.1', '0.1.2.3']) {
    const direct = { ...base, addresses: [`/ip4/${ip}/udp/4001/quic-v1/p2p/${peer}`] };
    assert.deepEqual(clientPeerEndpointProblems(direct), ['invalid-peer-endpoint'], `direct ${ip}`);
    assert.deepEqual(clientPeerEndpointProblems(direct, { scope: 'lan' }), [], `direct ${ip} with lan`);
    const hop = { ...base, addresses: [`/ip4/${ip}/tcp/4001/p2p/${relay}/p2p-circuit/p2p/${peer}`] };
    assert.deepEqual(clientPeerEndpointProblems(hop), ['invalid-peer-endpoint'], `relay ${ip}`);
    const op = { capability: 'peer/sync', service: 'p', operation: 'get', consent: 'each-operation', disclosure: DISCLOSURE, 'data-categories': ['x'], endpoint: direct };
    assert.deepEqual(errors([op]), ['internal-address-requires-lan-scope'], `operation ${ip}`);
    assert.deepEqual(errors([{ ...op, scope: 'lan' }]), [], `operation ${ip} with lan`);
  }
  const snapshot = 'bafyreifxwjkaji62sdkwexji2cwtqqzqtim4yusgmc33zal2kbemqxdtja';
  const receive = { ...base, protocol: '/awai/yataverse/1.0.0', action: 'receive-snapshot', addresses: [],
    scope: { 'snapshot-cid': snapshot, 'max-transfer-bytes': 1024, 'listen-address': '/ip4/192.168.1.20/tcp/40213', 'receive-ms': 1000, 'allow-read-back': false } };
  assert.deepEqual(clientPeerEndpointProblems(receive), ['invalid-peer-endpoint'], 'private listener');
  assert.deepEqual(clientPeerEndpointProblems(receive, { scope: 'lan' }), [], 'private listener with lan');
  assert.deepEqual(clientPeerEndpointProblems({ ...receive, scope: { ...receive.scope, 'listen-address': '/ip4/0.0.0.0/tcp/40213' } }, { scope: 'lan' }), ['invalid-peer-endpoint'], '0.0.0.0 stays refused');

  // The dialog prints the LAN scope on its first screen.
  const lanOp = http({ origin: 'https://192.168.1.10', method: 'GET', path: '/x' }, { scope: 'lan' });
  const h = harness(lanOp, { fetchStub: async () => ({ ok: true, status: 200, type: 'cors', url: 'https://192.168.1.10/x', body: null }) });
  const call = h.broker.invoke(h.selector, { input: 'https://192.168.1.10/x' });
  await tick();
  assert.ok(h.note.textContent.includes(CLIENT_CONSENT_TEXT.ja.lan), 'LAN scope is on the first screen');
  assert.match(h.scope.textContent, /Network scope: lan/);
  h.approve(); assert.equal((await call).status, 200);
  h.consentHost.destroy();
  for (const host of ['127.0.0.1', '10.1.2.3', '172.16.0.9', '172.31.255.1', '192.168.1.1', '169.254.169.254', '100.64.0.1', '100.127.255.254',
    '0.1.2.3', 'localhost', 'api.localhost', 'printer.local', 'router.home.arpa', 'db.internal',
    '::1', '[::1]', '::', 'fc00::1', 'fd12:3456::1', 'fe80::1', 'fe80::1%en0', 'febf::1', '::ffff:127.0.0.1', '::ffff:7f00:1',
    '::ffff:a9fe:a9fe', '::ffff:10.0.0.1', '::127.0.0.1', '64:ff9b::a00:1', '[::ffff:192.168.0.1]']) {
    assert.notEqual(clientAddressScope(host), 'public', host);
  }
  for (const host of ['8.8.8.8', '203.0.113.7', '172.32.0.1', '100.128.0.1', 'svc.example', '2606:4700::1111', '::ffff:8.8.8.8']) {
    assert.equal(clientAddressScope(host), 'public', host);
  }
  assert.equal(clientAddressScope('224.0.0.1'), 'reserved');
});

// ---- Finding 9: the declared disclosure is required and is the first screen, in the draft wording.
await section('Finding 9', async () => {
  const ep = { origin: 'https://svc.example', method: 'POST', path: '/x' };
  const { disclosure: _omit, ...bare } = http(ep);
  assert.ok(errors([bare]).includes('invalid-disclosure'), 'missing disclosure');
  for (const key of Object.keys(DISCLOSURE).filter((key) => key !== 'withdrawal')) {
    const { [key]: _gone, ...partial } = DISCLOSURE;
    assert.ok(errors([http(ep, { disclosure: partial })]).includes('invalid-disclosure'), `missing ${key}`);
  }
  // Legal 2026-11-22: withdrawal is required for a continuous operation only; a one-time one may omit it.
  if (!legacy) {
    const { withdrawal: _w, ...onceOnly } = DISCLOSURE;
    assert.deepEqual(errors([http(ep, { disclosure: onceOnly })]), [], 'one-time without withdrawal');
    assert.ok(errors([http(ep, { disclosure: { ...onceOnly, frequency: 'continuous' } })]).includes('invalid-disclosure'), 'continuous without withdrawal');
    assert.deepEqual(errors([http(ep, { disclosure: { ...DISCLOSURE, frequency: 'continuous' } })]), [], 'continuous with withdrawal');
  }
  for (const patch of [{ 'special-care': 'no' }, { data: [] }, { frequency: 'sometimes' }, { purpose: 'a\nb' }, { recipient: 'x‮y' },
    { country: 'jp' }, { purpose: 'x'.repeat(121) }, { 'special-care': true }, { 'special-care': true, 'special-care-kinds': [] }]) {
    assert.ok(errors([http(ep, { disclosure: { ...DISCLOSURE, ...patch } })]).includes('invalid-disclosure'), JSON.stringify(patch));
  }
  assert.deepEqual(errors([http(ep, { disclosure: { ...DISCLOSURE, 'special-care': true, 'special-care-kinds': ['病歴'] } })]), []);
  // A foreign recipient needs the country name and a page with the 施行規則 17 条 2 項 information.
  const foreign = { ...DISCLOSURE, country: 'US' };
  assert.ok(errors([http(ep, { disclosure: foreign })]).includes('invalid-disclosure'), 'foreign without country name and page');
  assert.ok(errors([http(ep, { disclosure: { ...foreign, 'country-name': 'アメリカ合衆国' } })]).includes('invalid-disclosure'), 'foreign without the information page');
  assert.ok(errors([http(ep, { disclosure: { ...foreign, 'country-name': 'アメリカ合衆国', 'foreign-info-url': 'http://x.example/' } })]).includes('invalid-disclosure'), 'page must be https');
  assert.deepEqual(errors([http(ep, { disclosure: { ...foreign, 'country-name': 'アメリカ合衆国', 'foreign-info-url': 'https://svc.example/privacy#transfer' } })]), []);
  assert.ok(errors([http(ep, { disclosure: { ...DISCLOSURE, 'foreign-info-url': 'https://svc.example/' } })]).includes('invalid-disclosure'), 'JP recipient carries no foreign fields');

  const declared = { recipient: '株式会社テスト法律事務所', country: 'US', 'country-name': 'アメリカ合衆国',
    'foreign-info-url': 'https://svc.example/transfer', data: ['氏名', '相談内容'], 'special-care': true, 'special-care-kinds': ['病歴'],
    purpose: '選んだ弁護士に相談内容を届けるため', frequency: 'one-time', withdrawal: '設定 › 許可した送信' };
  const h = harness(http(ep, { disclosure: declared }), { fetchStub: okFetch, app: { name: '相談アプリ' } });
  const body = JSON.stringify({ name: '合成 太郎', diagnosis: 'synthetic', note: 'n'.repeat(300) });
  const call = h.broker.invoke(h.selector, { input: 'https://svc.example/x', init: { method: 'POST', body, headers: { 'content-type': 'application/json' } } });
  await tick();
  assert.equal(h.dialog.open, true);
  assert.equal(h.title.textContent, '相談アプリ が、次の情報を送ろうとしています');
  assert.deepEqual(h.summary.textContent.split('\n'), [
    '送り先: 株式会社テスト法律事務所（アメリカ合衆国）',
    '送る情報: 氏名、相談内容',
    '目的: 選んだ弁護士に相談内容を届けるため',
    '送る回数: 1 回だけ',
  ], 'first screen lists the declared disclosure');
  assert.deepEqual(h.note.textContent.split('\n\n'), [
    'この中には、病歴 が含まれます。',
    '許可しない場合、この情報は送られません。この許可は今回の 1 回だけです。保存しません。',
    '送り先は日本の外（アメリカ合衆国）にあります。アメリカ合衆国 の個人情報の保護に関する制度と、送り先が講じている保護の措置は、こちら（https://svc.example/transfer） で確かめられます。日本と同じ水準の保護が受けられないことがあります。',
  ]);
  assert.doesNotMatch(h.summary.textContent + h.note.textContent, /diagnosis|svc\.example\/x|SHA-256/, 'no payload or inferred category on the first screen');
  assert.equal(h.details.open, false, '詳細 starts closed');
  const bytes = new TextEncoder().encode(body);
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), (b) => b.toString(16).padStart(2, '0')).join('');
  const T = CLIENT_CONSENT_TEXT.ja;
  assert.ok(h.payload.textContent.includes(`${T.payloadDigest}: ${digest}`));
  assert.ok(h.payload.textContent.includes(T.payloadSize(bytes.byteLength)));
  assert.ok(h.payload.textContent.includes(`${T.payloadFields}: name, diagnosis, note`));
  assert.ok(h.payload.textContent.includes('application/json'));
  assert.match(h.scope.textContent, /Endpoint: https:\/\/svc\.example/, 'the recipient URL is in the details');
  assert.ok(!h.payload.textContent.includes('n'.repeat(300)), 'long payload is cut until 全文');
  assert.equal(h.fullToggle.hidden, false);
  h.fullToggle.dispatch('click');
  assert.ok(h.payload.textContent.includes(body), '全文 shows the whole payload');
  assert.equal(h.fullToggle.textContent, T.shortText);
  h.deny.dispatch('click');
  await assert.rejects(call, /not approved/);
  h.consentHost.destroy();
  assert.equal(CLIENT_CONSENT_TEXT.status, 'draft', 'the wording is marked as a draft');
  assert.ok(Object.isFrozen(CLIENT_CONSENT_TEXT) && Object.isFrozen(T));

  // Omitted lines: no app name falls back to "この app"; Japan shows 日本; no special care, no foreign
  // paragraph and (trusted) no provider sentence when their values are missing. Nothing is left blank.
  const plain = harness(http(ep), { fetchStub: okFetch });
  const plainCall = plain.broker.invoke(plain.selector, { input: 'https://svc.example/x', init: { method: 'POST', body: 'x' } });
  await tick();
  assert.equal(plain.title.textContent, 'この app が、次の情報を送ろうとしています');
  assert.equal(plain.summary.textContent.split('\n')[0], `送り先: ${DISCLOSURE.recipient}（日本）`);
  assert.deepEqual(plain.note.textContent.split('\n\n'), ['許可しない場合、この情報は送られません。この許可は今回の 1 回だけです。保存しません。'], 'one-time: no withdrawal line, even when declared');
  assert.ok(!plain.note.textContent.includes(DISCLOSURE.withdrawal));
  assert.doesNotMatch(plain.summary.textContent + plain.note.textContent + plain.title.textContent, /undefined|null|（）|: \n|: $/m);
  plain.deny.dispatch('click'); await assert.rejects(plainCall, /not approved/); plain.consentHost.destroy();

  // English draft wording.
  const en = harness(http(ep, { disclosure: declared }), { fetchStub: okFetch, locale: 'en', app: { name: 'Advice' } });
  const enCall = en.broker.invoke(en.selector, { input: 'https://svc.example/x', init: { method: 'POST', body: 'x' } });
  await tick();
  assert.equal(en.title.textContent, 'Advice wants to send the following information');
  assert.equal(en.summary.textContent.split('\n')[0], 'Recipient: 株式会社テスト法律事務所 (アメリカ合衆国)');
  assert.match(en.note.textContent, /If you do not allow it, this information will not be sent\./);
  assert.equal(en.deny.textContent, "Don't allow"); assert.equal(en.allow.textContent, 'Allow');
  en.deny.dispatch('click'); await assert.rejects(enCall, /not approved/); en.consentHost.destroy();
});

// ---- Finding 1: trusted-page-v1 shows a notice that does not claim sending is restricted; equal choices.
await section('Finding 1', async () => {
  const op = http({ origin: 'https://svc.example', method: 'GET', path: '/x' });
  const trusted = harness(op, { profile: 'trusted-page-v1', fetchStub: okFetch,
    app: { name: 'メモ', provider: 'Kotoba Labs 株式会社', 'privacy-policy': 'https://kotoba.example/privacy' } });
  let call = trusted.broker.invoke(trusted.selector, { input: 'https://svc.example/x' });
  await tick();
  assert.equal(trusted.note.textContent, `この許可は今回の 1 回だけです。保存しません。\n\nこの app は Kotoba Labs 株式会社 が提供する app です。通信は Kotoba Labs 株式会社 のプライバシーポリシー（https://kotoba.example/privacy） に従います。\n\nこの画面は送信の確認で、送信の制限を保証するものではありません。`);
  assert.equal(trusted.title?.textContent, 'メモ が、次の情報を送ります');
  assert.doesNotMatch(trusted.note.textContent + trusted.summary.textContent, /送られません|送信されません|許可しない限り|同意なし/, 'no claim that sending is prevented');
  assert.equal(trusted.deny.textContent, '閉じる'); assert.equal(trusted.allow.textContent, '続ける');
  assert.ok(trusted.summary.textContent.includes('送る回数: 1 回だけ'), 'trusted-page-v1 shows the frequency too (AWAI-3819)');
  trusted.deny.dispatch('click'); await assert.rejects(call, /not approved/); trusted.consentHost.destroy();
  // English trusted wording, and the provider sentence is left out when the host gives no provider.
  const enTrusted = harness(op, { profile: 'trusted-page-v1', fetchStub: okFetch, locale: 'en' });
  call = enTrusted.broker.invoke(enTrusted.selector, { input: 'https://svc.example/x' });
  await tick();
  assert.equal(enTrusted.note.textContent, `This permission is for this one time only and is not saved.\n\nThis screen is a notice. It does not guarantee that sending is restricted.`);
  assert.doesNotMatch(enTrusted.note.textContent, /without your permission|will not be sent/i);
  enTrusted.deny.dispatch('click'); await assert.rejects(call, /not approved/); enTrusted.consentHost.destroy();
  // restricted-wasm-v1 is the only profile that says a refusal sends nothing.
  const restricted = harness(op, { fetchStub: okFetch });
  call = restricted.broker.invoke(restricted.selector, { input: 'https://svc.example/x' });
  await tick();
  assert.match(restricted.note.textContent, /許可しない場合、この情報は送られません/);
  // Equal weight: same class on both choices, no default, and focus is on neither choice.
  assert.equal(restricted.allow.className, restricted.deny.className, 'both choices share one style');
  assert.notEqual(restricted.focused(), restricted.allow, 'Allow is not focused by default');
  assert.notEqual(restricted.focused(), restricted.deny, 'Deny is not focused by default');
  assert.equal(restricted.allow.autofocus ?? false, false); assert.equal(restricted.deny.autofocus ?? false, false);
  restricted.deny.dispatch('click'); await assert.rejects(call, /not approved/); restricted.consentHost.destroy();
  // Legal 2026-11-22: a continuous operation keeps the withdrawal line, in both profiles.
  const continuous = http({ origin: 'https://svc.example', method: 'GET', path: '/x' }, { disclosure: { ...DISCLOSURE, frequency: 'continuous' } });
  for (const [profile, expected] of [['restricted-wasm-v1', `許可しない場合、この情報は送られません。許可は、あとで ${DISCLOSURE.withdrawal} から取り消せます。`],
    ['trusted-page-v1', `許可は、あとで ${DISCLOSURE.withdrawal} から取り消せます。`]]) {
    const c = harness(continuous, { profile, fetchStub: okFetch });
    call = c.broker.invoke(c.selector, { input: 'https://svc.example/x' });
    await tick();
    assert.equal(c.note.textContent.split('\n\n')[0], expected, `${profile} continuous shows where to withdraw`);
    assert.ok(!c.note.textContent.includes('1 回だけ'), `${profile} continuous does not say one time`);
    c.deny.dispatch('click'); await assert.rejects(call, /not approved/); c.consentHost.destroy();
  }
});

// ---- R3: one slot per broker, taken before the body is read; a concurrent call is refused at once.
await section('R3', async () => {
  const op = http({ origin: 'https://svc.example', method: 'POST', path: '/x' });
  const h = harness(op, { fetchStub: okFetch });
  const first = h.broker.invoke(h.selector, { input: 'https://svc.example/x', init: { method: 'POST', body: 'one' } });
  let pulled = false;
  const stream = new ReadableStream({ pull(controller) { pulled = true; controller.enqueue(new Uint8Array(1024)); controller.close(); } }, { highWaterMark: 0 });
  await assert.rejects(h.broker.invoke(h.selector, { input: 'https://svc.example/x', init: { method: 'POST', body: stream, duplex: 'half' } }), /awaiting consent/);
  await tick();
  assert.equal(pulled, false, 'the refused call never read its body');
  assert.equal(h.dialog.open, true);
  h.deny.dispatch('click'); await assert.rejects(first, /not approved/);
  const third = h.broker.invoke(h.selector, { input: 'https://svc.example/x', init: { method: 'POST', body: 'three' } });
  await tick();
  assert.equal(h.dialog.open, true, 'the slot is released when consent resolves');
  h.approve(); assert.equal((await third).status, 200);
  h.consentHost.destroy();
});

// ---- R4: only a canonical broker is mounted; there is no exported registration.
await section('R4', async () => {
  assert.equal(Object.keys(runtimeModule).some((name) => /broker/i.test(name) && name !== 'createClientOperationBroker'), false, 'no escape is exported');
  class Container { constructor() { this.isConnected = true; this.ownerDocument = globalThis.document; } getRootNode() { return globalThis.document; } append() {} }
  globalThis.HTMLElement = Container;
  globalThis.MutationObserver = class { observe() {} disconnect() {} };
  const bytes = new TextEncoder().encode('<p>guest</p>');
  const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), (b) => b.toString(16).padStart(2, '0')).join('');
  const artifact = await verifyClientArtifact(bytes, { revision: '1'.repeat(40), sha256: digest, 'max-bytes': 1024 });
  await assert.rejects(() => mountRestrictedClientApp({ artifact, container: new Container(), broker: { invoke: async () => true } }), /trusted host broker required/);
});

// ---- R5, D4: fixed fields come before Action; long values are cut with their length and a 全文 toggle.
await section('R5, D4', async () => {
  const op = http({ origin: 'https://svc.example', routes: [{ method: 'GET', path: '/search', 'query-params': ['q'] }] }, { 'redirect-origins': [] });
  const h = harness(op, { fetchStub: okFetch });
  const q = 'z'.repeat(900);
  const call = h.broker.invoke(h.selector, { input: `https://svc.example/search?q=${q}` });
  await tick();
  const text = h.scope.textContent;
  for (const label of ['Data categories:', 'Delivery redirects:', 'Network scope:']) {
    assert.ok(text.indexOf(label) >= 0 && text.indexOf(label) < text.indexOf('Action:'), `${label} above Action`);
  }
  assert.match(text, /Query length: 902 characters/);
  assert.ok(!text.includes(q), 'the long query is cut');
  assert.ok(text.includes(CLIENT_CONSENT_TEXT.ja.truncated(`GET /search?q=${q}`.length)));
  assert.equal(h.fullToggle.hidden, false, '全文 is visible');
  h.fullToggle.dispatch('click');
  assert.ok(h.scope.textContent.includes(q), '全文 shows the whole value');
  h.deny.dispatch('click'); await assert.rejects(call, /not approved/);
  h.consentHost.destroy();
});

// ---- D2: scoped peer adapters declare enforcement; the broker checks the bound; hosts run the conformance helper.
await section('D2', async () => {
  const peer = '12D3KooWJxXy9juQKbQW8wSCuW7oGiNTJWmfg3ZkCqfaRoiLBM4P';
  const snapshot = 'bafyreifxwjkaji62sdkwexji2cwtqqzqtim4yusgmc33zal2kbemqxdtja';
  const endpoint = { transport: 'libp2p', 'peer-id': peer, addresses: [`/ip4/203.0.113.7/tcp/4001/p2p/${peer}`], protocol: '/awai/yataverse/1.0.0',
    action: 'sync-push', 'max-request-bytes': 1024, 'max-response-bytes': 1024, 'timeout-ms': 1000, scope: { 'snapshot-cid': snapshot, 'max-transfer-bytes': 16777216 } };
  const op = { capability: 'peer/sync', service: 'drive', operation: 'push', consent: 'each-operation', disclosure: DISCLOSURE, 'data-categories': ['snapshot'], endpoint };
  const declaration = (max) => ({ schema: 'kotoba.peer-scope-enforcement.v1', enforces: ['snapshot-cid', 'max-transfer-bytes'], 'max-transfer-bytes': max });
  const strict = {
    scopeEnforcement: declaration(16777216),
    handle({ operation, payload }) {
      if (payload.cid !== operation.endpoint.scope['snapshot-cid']) throw new Error('snapshot outside scope');
      if (payload.bytes > operation.endpoint.scope['max-transfer-bytes']) throw new Error('transfer over bound');
      return { ok: true };
    },
  };
  // A plain function for a scoped operation (accepted on main) is refused before consent.
  let h = harness(op, { peerAdapters: { drive: { push: () => ({ ok: true }) } } });
  await assert.rejects(h.broker.invoke(h.selector, {}), /scoped peer adapter must be/);
  assert.equal(h.dialog.open, false); h.consentHost.destroy();
  // An adapter that enforces less than the operation's transfer scope is refused.
  h = harness(op, { peerAdapters: { drive: { push: { ...strict, scopeEnforcement: declaration(8388608) } } } });
  await assert.rejects(h.broker.invoke(h.selector, {}), /exceeds what the peer adapter enforces/); h.consentHost.destroy();
  h = harness(op, { peerAdapters: { drive: { push: { ...strict, scopeEnforcement: declaration(PEER_TRANSFER_MAX_BYTES + 1) } } } });
  await assert.rejects(h.broker.invoke(h.selector, {}), /transfer bound is invalid/); h.consentHost.destroy();
  // A declared adapter runs after consent.
  h = harness(op, { peerAdapters: { drive: { push: strict } } });
  const call = h.broker.invoke(h.selector, { cid: snapshot, bytes: 1 });
  await tick(); h.approve(); assert.deepEqual(await call, { ok: true }); h.consentHost.destroy();
  // Conformance helper: the strict adapter passes; one that trusts its payload fails.
  const cases = { operation: op, inScope: { cid: snapshot, bytes: 1 }, violations: { 'snapshot-cid': { cid: 'bafyother', bytes: 1 }, 'max-transfer-bytes': { cid: snapshot, bytes: 16777217 } } };
  const pass = await verifyPeerAdapterScopeConformance(strict, cases);
  assert.equal(pass.conformant, true, JSON.stringify(pass));
  const lax = { scopeEnforcement: declaration(16777216), handle: () => ({ ok: true }) };
  const failed = await verifyPeerAdapterScopeConformance(lax, cases);
  assert.equal(failed.conformant, false);
  assert.deepEqual(failed.results.filter((r) => !r.passed).map((r) => r.case).sort(), ['max-transfer-bytes', 'snapshot-cid']);
  const missing = await verifyPeerAdapterScopeConformance(strict, { ...cases, violations: {} });
  assert.equal(missing.conformant, false, 'every required violation case must be supplied');
});

if (negativeControl) { for (const [name, outcome] of outcomes) console.log(`${name}\t${outcome}`); process.exit(0); }
console.log('PASS: KOTOBA-159 2026-11-22 decisions: 7 structural generic-network refusal; 8/P1/D1 internal addresses need scope lan; 9 disclosure required and shown first, payload behind 詳細; 1 profile notice; R3 single slot; R4 canonical broker only; R5/D4 order and 全文; D2 declared scope enforcement and conformance helper');
