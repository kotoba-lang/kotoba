// KOTOBA-159 App QA findings on the consent dialog (2026-11-22, Chrome 158 and Safari 26.4 on desktop):
//   A  notice paragraphs joined by "\n\n" collapsed into one paragraph inside one <p>;
//   B  the details <pre> (SHA-256, full payload) overflowed the dialog width at 390 px;
//   C  Safari's default Tab order skipped the buttons (h2 → summary → out of the dialog).
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
assert.match(paragraphs[0].textContent, /病歴/);
assert.match(paragraphs[1].textContent, /許可しない場合、この情報は送られません/);
assert.match(paragraphs[2].textContent, /送り先は日本の外/);
assert.ok(paragraphs.every((p) => !p.textContent.includes('\n\n')));

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
assert.equal(tab(), true, 'the dialog handles Tab itself');
assert.equal(doc.activeElement, summaryToggle, 'Tab from the heading reaches 詳細を見る');
tab(); assert.equal(doc.activeElement, deny, 'then the refusal button');
tab(); assert.equal(doc.activeElement, summaryToggle, 'Allow is skipped while disabled; focus wraps inside the dialog');
now += 600; await new Promise((resolve) => setTimeout(resolve, 650));
assert.equal(allow.disabled, false, 'Allow is armed after 600 ms');
tab(); tab(); assert.equal(doc.activeElement, allow, 'once armed, Tab reaches Allow');
tab(); assert.equal(doc.activeElement, summaryToggle, 'Tab after the last control wraps to the first');
tab(true); assert.equal(doc.activeElement, allow, 'Shift+Tab wraps backwards');
details.open = true; fullToggle.hidden = false;
doc.activeElement = summaryToggle; tab(); assert.equal(doc.activeElement, fullToggle, 'the 全文 toggle is in the cycle when details are open');
deny.dispatch('click');
await assert.rejects(call, /not approved/);
consentHost.destroy();
console.log('PASS: KOTOBA-159 App QA A (one <p> per notice paragraph), B (details wrap within the dialog), C (explicit tabindex and a Tab cycle inside the dialog)');
