// KOTOBA-968 test harness: a synthetic host for restricted-wasm-v1 host-local calls and declared bodies.
// It runs the real runtime (verifySignedClientDescriptor, createClientHostLocal, createClientOperationBroker,
// the real consent host and mountRestrictedClientApp) on a fake DOM, a fake frame and a real MessageChannel.
// The network is a stub (respondWith); storage is the runtime's encrypted backend over an in-memory store.
// Test-only: nothing here is exported by the runtime, and the runtime has no test hook (see the
// "no test-only export" check in verify-client-host-local-20261122.mjs).
// Shape: yataverse-acceptance.test.mjs (KOTOBA_HARNESS) from the Yataverse worker, 2026-11-22.

class Mouse { constructor(type, trusted = true) { this.type = type; this.isTrusted = trusted; } }
class Element {
  constructor(tag) { this.tagName = tag; this.listeners = new Map(); this.isConnected = true; this.open = false; this.textContent = ''; this.hidden = false; this.style = {}; }
  append() {} setAttribute() {} focus() {} remove() { this.isConnected = false; } click() { harnessState.clicks.push(this); }
  addEventListener(type, fn) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn]); }
  dispatch(type, event = {}) { event.currentTarget = this; for (const fn of this.listeners.get(type) ?? []) fn(event); }
  showModal() { this.open = true; harnessState.onShow?.(this); } close() { this.open = false; }
}
class Frame extends EventTarget {
  constructor() { super(); this.tagName = 'iframe'; this.contentWindow = { postMessage: (_data, _origin, ports) => { this.port = ports[0]; } }; }
  remove() { this.removed = true; }
}
class Container {
  constructor() { this.isConnected = true; this.ownerDocument = globalThis.document; }
  getRootNode() { return globalThis.document; }
  append(frame) { this.frame = frame; frame.isConnected = true; frame.parentNode = this; queueMicrotask(() => frame.dispatchEvent(new Event('load'))); }
}
export const harnessState = { now: 0, made: [], clicks: [], onShow: null };
globalThis.MutationObserver ??= class { observe() {} disconnect() {} };
globalThis.HTMLElement = Container;
globalThis.MouseEvent ??= Mouse;
globalThis.document = {
  body: new Element('body'), defaultView: { MouseEvent: Mouse, performance: { now: () => harnessState.now } },
  createElement(tag) { const el = tag === 'iframe' ? new Frame() : new Element(tag); harnessState.made.push(el); return el; },
};
export const HOST_ORIGIN = 'http://tauri.localhost';
globalThis.location = { origin: HOST_ORIGIN };

export const runtime = await import(process.env.KOTOBA_CLIENT_RUNTIME ?? '../src/kotoba-client-runtime.js');
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const hex = (bytes) => Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, '0')).join('');

/** An in-memory key-value store for createEncryptedClientStorageBackend; `raw` exposes what is "on disk". */
export function memoryKv() {
  const raw = new Map();
  return {
    raw,
    async get(key) { return raw.get(key) ?? null; },
    async entries(prefix) { return [...raw.entries()].filter(([key]) => key.startsWith(prefix)); },
    async batch(writes) { for (const [kind, key, value] of writes) { if (kind === 'put') raw.set(key, value); else raw.delete(key); } },
    async deletePrefix(prefix) { for (const key of [...raw.keys()]) if (key.startsWith(prefix)) raw.delete(key); },
  };
}
export const TEST_CONFORMANCE = Object.freeze({ host: 'synthetic-test-host', 'no-cloud-backup': true, 'no-logging': true, 'user-clearable': true, 'removed-with-app': true });
const roots = new Map();
export function storageFor(root) {
  if (!roots.has(root)) { const kv = memoryKv(); roots.set(root, { kv, backend: runtime.createEncryptedClientStorageBackend?.({ kv, conformance: TEST_CONFORMANCE }) }); }
  return roots.get(root);
}

// Every console call while a host is open is recorded as that host's telemetry (Legal L2: there must be none).
const activeSinks = new Set();
for (const name of ['log', 'info', 'warn', 'error', 'debug', 'trace']) {
  const real = console[name].bind(console);
  console[name] = (...args) => { if (activeSinks.size === 0) return real(...args); for (const sink of activeSinks) sink({ console: name, args }); };
}
let responder = () => new Response(null, { status: 204 });
export function respondWith(fn) { responder = fn; }

/** Sign the descriptor with a fresh publisher key and admit it the way a host does. */
export async function admit(descriptor, requestedCapabilities = [...new Set((descriptor.operations ?? []).map((op) => op.capability))]) {
  const bytes = new TextEncoder().encode(JSON.stringify(descriptor));
  const keys = await crypto.subtle.generateKey('Ed25519', true, ['sign', 'verify']);
  const publicKey = hex(await crypto.subtle.exportKey('raw', keys.publicKey));
  const signature = hex(await crypto.subtle.sign('Ed25519', keys.privateKey, bytes));
  const digest = hex(await crypto.subtle.digest('SHA-256', bytes));
  return runtime.verifySignedClientDescriptor({ bytes, signature, publicKey, pinnedPublicKey: publicKey, revision: '1'.repeat(40), digest, requestedCapabilities, appOrigins: [HOST_ORIGIN] });
}

/**
 * createTestHost({ descriptor, appId, approve, storageRoot, storage, saveTarget, linkTarget, locale, app })
 * approve: true (a trusted press after the arm delay), false (Deny), 'early' (a trusted press before the
 * delay, then Deny), 'synthetic' (an untrusted click, then Deny) or 'manual' (the test calls h.allow()/h.deny()).
 */
export async function createTestHost({ descriptor, appId, approve = false, storageRoot = 'default', storage, saveTarget, linkTarget, locale = 'ja', app = null }) {
  const dialogs = []; const requests = []; const telemetry = []; const guestMessages = []; const saves = []; const links = [];
  const pending = new Map(); let next = 0;
  const sink = (entry) => telemetry.push(entry);
  activeSinks.add(sink);
  const restore = () => activeSinks.delete(sink);
  const before = harnessState.made.length;
  let consentHost; let mountProblems = null; let mount = null; let container = null; let hostLocal = null;
  const mine = () => harnessState.made.slice(before);
  try {
    consentHost = runtime.createClientConsentHost({ locale });
    const admitted = await admit(descriptor);
    const operations = admitted.runtime.operations;
    const savedFetch = globalThis.fetch;
    globalThis.fetch = async (request) => {
      const body = request.body ? new Uint8Array(await request.arrayBuffer()) : null;
      requests.push({ url: request.url, method: request.method, origin: HOST_ORIGIN, headers: Object.fromEntries(request.headers), body });
      const response = await responder(request);
      Object.defineProperty(response, 'url', { value: request.url });
      return response;
    };
    const broker = runtime.createClientOperationBroker({
      runtime: admitted.runtime, requestedCapabilities: [...new Set(operations.map((op) => op.capability))], approvedOperations: operations,
      hostSupportedOperations: operations.map((op) => [op.capability, op.service, op.operation]), consentHost, app,
    });
    globalThis.fetch = savedFetch;
    if (admitted.runtime['host-local']) {
      hostLocal = runtime.createClientHostLocal({
        admitted, appId, storage: storage ?? storageFor(storageRoot).backend, consentHost, app,
        saveTarget: saveTarget ?? ((file) => { saves.push(file); }), linkTarget: linkTarget ?? ((url) => { links.push(url); }),
      });
    }
    const bytes = new TextEncoder().encode('<p>synthetic guest</p>');
    const artifact = await runtime.verifyClientArtifact(bytes, { revision: '2'.repeat(40), sha256: hex(await crypto.subtle.digest('SHA-256', bytes)), 'max-bytes': 1024 });
    container = new Container();
    mount = await runtime.mountRestrictedClientApp({ artifact, container, broker, hostLocal });
    await tick();
    container.frame.port.onmessage = ({ data }) => {
      guestMessages.push(data);
      if (data && Object.hasOwn(data, 'id') && pending.has(data.id)) { pending.get(data.id)(data); pending.delete(data.id); }
    };
  } catch (error) {
    mountProblems = [String(error?.message ?? error).slice(0, 400)];
  }
  const els = mine();
  const dialog = els.find((el) => el.tagName === 'dialog');
  const [deny, allow] = els.filter((el) => el.tagName === 'button');
  const byClass = (name) => els.find((el) => el.className === name);
  const press = (trusted = true) => { allow.dispatch('pointerdown', new Mouse('pointerdown', trusted)); allow.dispatch('click', new Mouse('click', trusted)); };
  const h = {
    mountProblems, dialogs, requests, telemetry, guestMessages, saves, links, dialog,
    allow() { harnessState.now += 600; press(true); }, deny() { deny.dispatch('click', new Mouse('click')); }, pressSynthetic() { harnessState.now += 600; press(false); },
    clearAppData: () => hostLocal.clearAppData(),
    events: () => guestMessages.filter((m) => m && !Object.hasOwn(m, 'id')),
    send(message) {
      if (mountProblems) return Promise.resolve({ ok: false, error: 'not-mounted' });
      const id = `m${next++}`;
      const reply = new Promise((resolve) => pending.set(id, resolve));
      container.frame.port.postMessage({ ...message, id });
      return reply;
    },
    local(call, args) { return h.send({ protocol: 'kotoba.client.local.v1', call, args }); },
    async operation(selector, payload) { return h.send({ protocol: 'kotoba.client.operation.v1', selector, payload }); },
    async close() { mount?.close(); container?.frame?.port?.close(); consentHost?.destroy(); restore(); },
  };
  if (dialog) {
    const shown = () => ({
      title: els.find((el) => el.tagName === 'h2')?.textContent, summary: byClass('kotoba-client-consent-summary')?.textContent,
      note: byClass('kotoba-client-consent-note')?.textContent, scope: byClass('kotoba-client-consent-scope')?.textContent,
      payload: byClass('kotoba-client-consent-payload')?.textContent, allowLabel: allow.textContent, denyLabel: deny.textContent,
    });
    const onShow = (el) => {
      if (el !== dialog) return;
      dialogs.push(shown());
      if (approve === 'manual') return;
      setTimeout(() => {
        if (approve === true) h.allow();
        else if (approve === 'early') { press(true); h.deny(); }
        else if (approve === 'synthetic') { h.pressSynthetic(); h.deny(); }
        else h.deny();
      }, 0);
    };
    const previous = harnessState.onShow;
    harnessState.onShow = (el) => { onShow(el); previous?.(el); };
  }
  return h;
}
