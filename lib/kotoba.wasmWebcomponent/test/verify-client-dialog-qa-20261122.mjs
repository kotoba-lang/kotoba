// KOTOBA-159 App QA findings on the consent dialog (2026-11-22, Chrome 158 and Safari 26.4 on desktop):
//   A  notice paragraphs joined by "\n\n" collapsed into one paragraph inside one <p>;
//   B  the details <pre> (SHA-256, full payload) overflowed the dialog width at 390 px;
//   C  Safari's default Tab order skipped the buttons (h2 → summary → out of the dialog).
// App QA r2 (ee75001ee): Tab must reach the links in the dialog too, in DOM order.
// Itonami (AWAI-3819, kumade#37): trusted-page-v1 must show the same declared facts (frequency,
// withdrawal, foreign recipient with a safe link), and descriptors may add a plain-text `note`.
// Each block fails on main 681cb85c7 (runtime sha256 d6f67c05…0a75) and passes with the fix.
// KOTOBA_CLIENT_RUNTIME=<file> runs it against another copy. Fake DOM with style, replaceChildren and
// activeElement; layout itself is checked in real browsers by App QA, not here.
import assert from 'node:assert/strict';
import { DISCLOSURE } from './client-runtime-fixtures.mjs';

class Mouse { constructor(type) { this.type = type; this.isTrusted = true; } }
let now = 0;
const made = [];
class Element {
  constructor(tag) { this.tagName = tag; this.listeners = new Map(); this.isConnected = true; this.open = false; this.textContent = ''; this.hidden = false; this.style = {}; this.attributes = {}; this.children = []; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; this.textContent = children.map((c) => c.textContent).join(''); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  focus() { doc.activeElement = this; }
  remove() { this.isConnected = false; }
  addEventListener(type, fn) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn]); }
  dispatch(type, event = {}) { event.currentTarget = this; for (const fn of this.listeners.get(type) ?? []) fn(event); }
  showModal() { this.open = true; } close() { this.open = false; }
}
const doc = {
  body: new Element('body'), activeElement: null, defaultView: { MouseEvent: Mouse, performance: { now: () => now } },
  createElement(tag) { const el = new Element(tag); made.push(el); return el; },
};
globalThis.document = doc;
const { createClientConsentHost, createClientOperationBroker } = await import(process.env.KOTOBA_CLIENT_RUNTIME ?? '../src/kotoba-client-runtime.js');
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const text = (el) => (el.children.length ? el.children.map(text).join('') : el.textContent);

const declared = { ...DISCLOSURE, country: 'US', 'country-name': 'アメリカ合衆国', 'foreign-info-url': 'https://svc.example/transfer',
  'special-care': true, 'special-care-kinds': ['病歴'] };
const op = { capability: 'net/fetch', service: 'svc', operation: 'send', consent: 'each-operation', disclosure: declared,
  'data-categories': ['x'], endpoint: { origin: 'https://svc.example', method: 'POST', path: '/x' } };
const consentHost = createClientConsentHost();
const dialog = made.find((el) => el.tagName === 'dialog');
const byClass = (name) => made.find((el) => el.className === name);
const note = byClass('kotoba-client-consent-note');
const [deny, allow] = made.filter((el) => el.className === 'kotoba-client-consent-choice');
const details = byClass('kotoba-client-consent-details');
const summaryToggle = made.find((el) => el.tagName === 'summary');
const fullToggle = byClass('kotoba-client-consent-full');
const broker = createClientOperationBroker({
  runtime: { schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile: 'restricted-wasm-v1', entry: 'index.html',
    'local-state': { adapter: 'memory', schema: 's', version: 1 }, operations: [op] },
  requestedCapabilities: [op.capability], approvedOperations: [op], hostSupportedOperations: [[op.capability, op.service, op.operation]], consentHost,
});
const call = broker.invoke({ capability: op.capability, service: op.service, operation: op.operation },
  { input: 'https://svc.example/x', init: { method: 'POST', body: JSON.stringify({ note: 'n'.repeat(400) }), headers: { 'content-type': 'application/json' } } });
await tick();
assert.equal(dialog.open, true);

// A: three notice paragraphs (special care, refusal and withdrawal, foreign recipient) are three <p>.
const paragraphs = note.children.filter((child) => child.tagName === 'p');
assert.equal(paragraphs.length, 3, 'each notice paragraph is its own <p>');
assert.match(text(paragraphs[0]), /病歴/);
assert.match(text(paragraphs[1]), /許可しない場合、この情報は送られません/);
assert.match(text(paragraphs[2]), /送り先は日本の外/);
assert.ok(paragraphs.every((p) => !text(p).includes('\n\n')));

// B: both details blocks wrap and stay within the dialog even without the stylesheet.
for (const name of ['kotoba-client-consent-scope', 'kotoba-client-consent-payload']) {
  const block = byClass(name);
  assert.equal(block.style.whiteSpace, 'pre-wrap', `${name} wraps`);
  assert.equal(block.style.overflowWrap, 'anywhere', `${name} breaks long digests`);
  assert.equal(block.style.maxWidth, '100%', `${name} is no wider than the dialog`);
  assert.equal(block.style.overflow, 'auto', `${name} scrolls instead of overflowing`);
}

// C: controls are explicitly tabbable and Tab / Shift+Tab cycle inside the dialog.
for (const control of [summaryToggle, deny, allow, fullToggle]) assert.equal(control.attributes.tabindex, '0', 'explicit tabindex="0"');
assert.notEqual(doc.activeElement, allow, 'Allow is not focused when the dialog opens');
assert.notEqual(doc.activeElement, deny, 'Deny is not focused when the dialog opens');
const tab = (shiftKey = false) => { let prevented = false; dialog.dispatch('keydown', { key: 'Tab', shiftKey, preventDefault() { prevented = true; } }); return prevented; };
// App QA r2: the cycle is DOM order, so the foreign-recipient link in the notice comes first.
const foreignLink = made.find((el) => el.tagName === 'a' && el.href === 'https://svc.example/transfer');
assert.ok(foreignLink, 'the restricted dialog has the foreign-recipient link');
assert.equal(tab(), true, 'the dialog handles Tab itself');
assert.equal(doc.activeElement, foreignLink, 'Tab from the heading reaches the こちら link (App QA r2)');
tab(); assert.equal(doc.activeElement, summaryToggle, 'then 詳細を見る');
tab(); assert.equal(doc.activeElement, deny, 'then the refusal button');
tab(); assert.equal(doc.activeElement, foreignLink, 'Allow is skipped while disabled; focus wraps inside the dialog');
now += 600; await new Promise((resolve) => setTimeout(resolve, 650));
assert.equal(allow.disabled, false, 'Allow is armed after 600 ms');
tab(); tab(); tab(); assert.equal(doc.activeElement, allow, 'once armed, Tab reaches Allow');
tab(); assert.equal(doc.activeElement, foreignLink, 'Tab after the last control wraps to the first');
tab(true); assert.equal(doc.activeElement, allow, 'Shift+Tab wraps backwards');
details.open = true; fullToggle.hidden = false;
doc.activeElement = summaryToggle; tab(); assert.equal(doc.activeElement, fullToggle, 'the 全文 toggle is in the cycle when details are open');
fullToggle.hidden = true;
doc.activeElement = summaryToggle; tab(); assert.equal(doc.activeElement, deny, 'a hidden control is skipped');
deny.dispatch('click');
await assert.rejects(call, /not approved/);
consentHost.destroy();

// Trusted-page-v1 shows frequency, withdrawal and the foreign line; links are plain <a> with noopener.
async function open(operation, profile, app = null) {
  const before = made.length;
  const host = createClientConsentHost();
  const mine = made.slice(before);
  const b = createClientOperationBroker({
    runtime: { schema: 'kotoba.app.client-runtime.v1', target: 'browser', profile, entry: 'index.html',
      'local-state': { adapter: 'memory', schema: 's', version: 1 }, operations: [operation] },
    requestedCapabilities: [operation.capability], approvedOperations: [operation],
    hostSupportedOperations: [[operation.capability, operation.service, operation.operation]], consentHost: host,
    ...(app ? { app } : {}),
  });
  const pending = b.invoke({ capability: operation.capability, service: operation.service, operation: operation.operation }, { input: 'https://svc.example/x', init: { method: 'POST', body: 'x' } });
  await tick();
  const noteEl = mine.find((el) => el.className === 'kotoba-client-consent-note');
  const list = mine.find((el) => el.className === 'kotoba-client-consent-summary');
  const [no] = mine.filter((el) => el.className === 'kotoba-client-consent-choice');
  return { noteEl, list, all: () => made.slice(before), close: async () => { no.dispatch('click'); await assert.rejects(pending, /not approved/); host.destroy(); } };
}
{
  const t = await open({ ...op, disclosure: { ...declared, frequency: 'continuous' } }, 'trusted-page-v1',
    { name: 'メモ', provider: 'Kotoba Labs 株式会社', 'privacy-policy': 'https://kotoba.example/privacy' });
  assert.ok(text(t.list).includes('送る回数: 許可を取り消すまで続けて'), 'trusted-page-v1 shows the frequency');
  const paras = t.noteEl.children.map(text);
  assert.ok(paras.includes(`許可は、あとで ${declared.withdrawal} から取り消せます。`), 'trusted-page-v1 shows where to withdraw');
  assert.ok(paras.includes('送り先は日本の外（アメリカ合衆国）にあります。制度と送り先の措置は こちら。'), 'trusted-page-v1 shows the foreign line');
  const link = t.all().find((el) => el.tagName === 'a');
  assert.equal(link.href, 'https://svc.example/transfer');
  assert.equal(link.rel, 'noopener noreferrer');
  assert.equal(link.textContent, 'こちら');
  assert.ok(!paras.some((p) => /送られません|送信されません|許可しない限り/.test(p)), 'no claim that sending is prevented');
  // App QA r2: keyboard users reach every link (foreign page and privacy policy), which keep target/rel.
  const links = t.all().filter((el) => el.tagName === 'a');
  assert.deepEqual(links.map((el) => el.href), ['https://svc.example/transfer', 'https://kotoba.example/privacy']);
  for (const el of links) { assert.equal(el.target, '_blank'); assert.equal(el.rel, 'noopener noreferrer'); }
  const dlg = t.all().find((el) => el.tagName === 'dialog');
  const reached = [];
  doc.activeElement = t.all().find((el) => el.tagName === 'h2');
  for (let n = 0; n < 6; n++) { dlg.dispatch('keydown', { key: 'Tab', shiftKey: false, preventDefault() {} }); reached.push(doc.activeElement); }
  for (const el of links) assert.ok(reached.includes(el), `Tab reaches ${el.href}`);
  assert.equal(reached[0], links[0], 'the first Tab goes to the first link in DOM order');
  await t.close();
}

// The optional note is plain text: validated, capped at 200 characters and shown escaped.
{
  const { clientDisclosureProblems } = await import(process.env.KOTOBA_CLIENT_RUNTIME ?? '../src/kotoba-client-runtime.js');
  assert.deepEqual(clientDisclosureProblems({ ...DISCLOSURE, note: 'メモ' }), []);
  assert.deepEqual(clientDisclosureProblems({ ...DISCLOSURE, note: 'x'.repeat(200) }), []);
  for (const bad of ['x'.repeat(201), 'a\nb', 'a\u0007b', '', ' padded', 42]) {
    assert.ok(clientDisclosureProblems({ ...DISCLOSURE, note: bad }).includes('invalid-note'), JSON.stringify(bad));
  }
  const hostile = '<script>alert(1)</script><b onclick="x()">太字</b> [link](https://evil.example)';
  const before = made.length;
  const t = await open({ ...op, disclosure: { ...DISCLOSURE, note: hostile } }, 'restricted-wasm-v1');
  const span = t.noteEl.children.flatMap((p) => p.children).find((el) => el.textContent === hostile);
  assert.ok(span, 'the note is one text node with the exact characters');
  assert.equal(span.tagName, 'span');
  assert.ok(!made.slice(before).some((el) => ['script', 'b'].includes(el.tagName)), 'no element is created from the note');
  assert.ok(!made.slice(before).some((el) => el.tagName === 'a' && el.href === 'https://evil.example'), 'markdown in the note is not a link');
  await t.close();
}
console.log('PASS: Itonami trusted-page-v1 frequency, withdrawal and foreign line with a noopener link; note is plain text, capped and escaped');
console.log('PASS: KOTOBA-159 App QA A (one <p> per notice paragraph), B (details wrap within the dialog), C (explicit tabindex and a Tab cycle inside the dialog)');
