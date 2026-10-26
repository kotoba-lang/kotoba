// SharedArrayBuffer + Atomics.wait bridge for sync `http_post` host imports.
//
// Browser requirements:
//   - crossOriginIsolated === true
//     (COOP: same-origin + COEP: require-corp on the document)
//   - SharedArrayBuffer + Atomics.wait
//
// Control Int32Array (SharedArrayBuffer):
//   [0] status: 0 idle | 1 pending | 2 ok | 3 err
//   [1] response length (or -1)
//   [2] url length
//   [3] body length
//   [4] headers length
//   [5] method: 0 POST | 1 GET | 2 POST with headers
// Payload SAB: [url bytes][body bytes][headers bytes], then response bytes.
//
// Prefer opts.httpPost inject on Node/tests. Use this bridge only when a
// real browser tab is cross-origin-isolated.

const STATUS_IDLE = 0;
const STATUS_PENDING = 1;
const STATUS_OK = 2;
const STATUS_ERR = 3;

const DEFAULT_PAYLOAD_BYTES = 256 * 1024;

/**
 * @param {object} [opts]
 * @param {number} [opts.payloadBytes]
 * @param {number} [opts.timeoutMs]
 * @param {number} [opts.readyTimeoutMs]
 * @returns {Promise<object>}
 */
export async function createSabHttpPostBridge(opts = {}) {
  if (typeof SharedArrayBuffer === 'undefined' || typeof Atomics === 'undefined') {
    throw new Error('http-post-bridge: SharedArrayBuffer/Atomics unavailable');
  }
  if (typeof window !== 'undefined' && globalThis.crossOriginIsolated !== true) {
    throw new Error(
      'http-post-bridge: not crossOriginIsolated — set COOP/COEP headers ' +
        '(see COOP_COEP_HEADERS export)',
    );
  }
  if (typeof Worker === 'undefined') {
    throw new Error('http-post-bridge: Worker unavailable; use opts.httpPost inject');
  }

  const payloadBytes = opts.payloadBytes || DEFAULT_PAYLOAD_BYTES;
  const timeoutMs = opts.timeoutMs || 30000;
  const ctrlSab = new SharedArrayBuffer(24);
  const payloadSab = new SharedArrayBuffer(payloadBytes);
  const ctrl = new Int32Array(ctrlSab);
  const payload = new Uint8Array(payloadSab);

  const workerSource = `
    const P=1, OK=2, ERR=3;
    self.onmessage = (ev) => {
      const ctrl = new Int32Array(ev.data.ctrlSab);
      const payload = new Uint8Array(ev.data.payloadSab);
      // Signal readiness only once this handler is about to commit to the
      // wait loop below -- the caller blocks its own first postSync() on
      // this message instead of guessing a fixed delay.
      self.postMessage({ kind: 'ready' });
      (async function loop() {
        for (;;) {
          let s = Atomics.load(ctrl, 0);
          while (s !== P) {
            Atomics.wait(ctrl, 0, s);
            s = Atomics.load(ctrl, 0);
          }
          try {
            const urlLen = Atomics.load(ctrl, 2);
            const bodyLen = Atomics.load(ctrl, 3);
            const headersLen = Atomics.load(ctrl, 4);
            const methodId = Atomics.load(ctrl, 5);
            // .slice (not .subarray) -- TextDecoder.decode() throws
            // "The provided ArrayBufferView value must not be shared" on a
            // view backed directly by a SharedArrayBuffer (confirmed live);
            // .slice() copies into a fresh, non-shared ArrayBuffer first.
            const url = new TextDecoder().decode(payload.slice(0, urlLen));
            const body = payload.slice(urlLen, urlLen + bodyLen);
            const headerStart = urlLen + bodyLen;
            const headerText = new TextDecoder().decode(
              payload.slice(headerStart, headerStart + headersLen)
            );
            const headers = methodId === 2
              ? Object.fromEntries(headerText.split('\\n').filter(Boolean).map((line) => {
                  const tab = line.indexOf('\\t');
                  return tab < 0 ? [line, ''] : [line.slice(0, tab), line.slice(tab + 1)];
                }))
              : { 'content-type': 'application/octet-stream' };
            const init = methodId === 1
              ? { method: 'GET' }
              : { method: 'POST', body, headers };
            const resp = await fetch(url, init);
            const buf = new Uint8Array(await resp.arrayBuffer());
            const n = Math.min(buf.length, payload.length);
            payload.set(buf.subarray(0, n), 0);
            Atomics.store(ctrl, 1, n);
            Atomics.store(ctrl, 0, OK);
            Atomics.notify(ctrl, 0);
          } catch (e) {
            Atomics.store(ctrl, 1, -1);
            Atomics.store(ctrl, 0, ERR);
            Atomics.notify(ctrl, 0);
          }
        }
      })();
    };
  `;

  const blob = new Blob([workerSource], { type: 'application/javascript' });
  const url = URL.createObjectURL(blob);
  const worker = new Worker(url);

  const readyTimeoutMs = opts.readyTimeoutMs || 5000;
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error('http-post-bridge: inner worker did not signal ready in time'));
    }, readyTimeoutMs);
    worker.onmessage = (ev) => {
      if (ev.data && ev.data.kind === 'ready') {
        clearTimeout(timer);
        worker.onmessage = null;
        resolve();
      }
    };
    worker.onerror = (ev) => {
      clearTimeout(timer);
      reject(new Error(`http-post-bridge: inner worker failed to start: ${ev.message}`));
    };
    worker.postMessage({ ctrlSab, payloadSab });
  });

  function requestSync(methodId, urlStr, body, headers = '') {
    const urlBytes = new TextEncoder().encode(String(urlStr));
    const bodyBytes =
      body instanceof Uint8Array ? body : new TextEncoder().encode(String(body || ''));
    const headerBytes = new TextEncoder().encode(String(headers || ''));
    if (urlBytes.length + bodyBytes.length + headerBytes.length > payload.length) return null;

    // Wait for idle
    let s = Atomics.load(ctrl, 0);
    while (s === STATUS_PENDING) {
      Atomics.wait(ctrl, 0, STATUS_PENDING, 50);
      s = Atomics.load(ctrl, 0);
    }

    payload.fill(0);
    payload.set(urlBytes, 0);
    payload.set(bodyBytes, urlBytes.length);
    payload.set(headerBytes, urlBytes.length + bodyBytes.length);
    Atomics.store(ctrl, 2, urlBytes.length);
    Atomics.store(ctrl, 3, bodyBytes.length);
    Atomics.store(ctrl, 4, headerBytes.length);
    Atomics.store(ctrl, 5, methodId);
    Atomics.store(ctrl, 1, 0);
    Atomics.store(ctrl, 0, STATUS_PENDING);
    Atomics.notify(ctrl, 0);

    const wr = Atomics.wait(ctrl, 0, STATUS_PENDING, timeoutMs);
    if (wr === 'timed-out') {
      Atomics.store(ctrl, 0, STATUS_IDLE);
      return null;
    }
    const status = Atomics.load(ctrl, 0);
    const n = Atomics.load(ctrl, 1);
    Atomics.store(ctrl, 0, STATUS_IDLE);
    if (status !== STATUS_OK || n < 0) return null;
    return payload.slice(0, n);
  }

  const postSync = (urlStr, body) => requestSync(0, urlStr, body);
  const getSync = (urlStr) => requestSync(1, urlStr, new Uint8Array());
  const postHeadersSync = (urlStr, body, headers) => {
    const text = Array.isArray(headers)
      ? headers.map(([name, value]) => `${name}\t${value}`).join('\n')
      : String(headers || '');
    return requestSync(2, urlStr, body, text);
  };

  return {
    postSync,
    getSync,
    postHeadersSync,
    dispose() {
      try {
        worker.terminate();
        URL.revokeObjectURL(url);
      } catch (_) {}
    },
    capabilities: { mode: 'sab-coop', payloadBytes, timeoutMs },
  };
}

/** Headers a static file server must emit for crossOriginIsolated. */
export const COOP_COEP_HEADERS = {
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Cross-Origin-Embedder-Policy': 'require-corp',
};
