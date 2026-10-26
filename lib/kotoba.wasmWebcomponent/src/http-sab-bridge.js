const CONTROL_WORDS = 4;
const CONTROL_BYTES = CONTROL_WORDS * Int32Array.BYTES_PER_ELEMENT;

export function createSabHttpGetClient({ postMessage = globalThis.postMessage.bind(globalThis), timeoutMs = 5000 } = {}) {
  if (typeof SharedArrayBuffer !== 'function') throw new Error('SharedArrayBuffer unavailable');
  return ({ host, port, path, maxBytes, redirect = 'manual' }) => {
    if (!Number.isInteger(maxBytes) || maxBytes <= 0) return null;
    const sab = new SharedArrayBuffer(CONTROL_BYTES + maxBytes);
    const control = new Int32Array(sab, 0, CONTROL_WORDS);
    postMessage({ type: 'kotoba:http-get', sab, request: { host, port, path, maxBytes, redirect } });
    const waited = Atomics.wait(control, 0, 0, timeoutMs);
    if (waited === 'timed-out' || Atomics.load(control, 0) !== 1) return null;
    const length = Atomics.load(control, 1);
    if (length < 0 || length > maxBytes) return null;
    return new Uint8Array(new Uint8Array(sab, CONTROL_BYTES, length));
  };
}

export function createSabHttpPostClient({ postMessage = globalThis.postMessage.bind(globalThis), timeoutMs = 5000 } = {}) {
  if (typeof SharedArrayBuffer !== 'function') throw new Error('SharedArrayBuffer unavailable');
  return ({ url, body, maxBytes, redirect = 'manual' }) => {
    if (!(body instanceof Uint8Array) || !Number.isInteger(maxBytes) || maxBytes <= 0) return null;
    const sab = new SharedArrayBuffer(CONTROL_BYTES + maxBytes);
    const control = new Int32Array(sab, 0, CONTROL_WORDS);
    postMessage({ type: 'kotoba:http-post', sab, request: { url, body, maxBytes, redirect } });
    const waited = Atomics.wait(control, 0, 0, timeoutMs);
    if (waited === 'timed-out' || Atomics.load(control, 0) !== 1) return null;
    const length = Atomics.load(control, 1);
    if (length < 0 || length > maxBytes) return null;
    return new Uint8Array(new Uint8Array(sab, CONTROL_BYTES, length));
  };
}

export function attachSabHttpGetBridge(worker, handler) {
  if (!worker || typeof worker.addEventListener !== 'function') throw new TypeError('worker required');
  if (typeof handler !== 'function') throw new TypeError('handler required');
  const listener = async (event) => {
    const message = event.data;
    if (!message || message.type !== 'kotoba:http-get' || !(message.sab instanceof SharedArrayBuffer)) return;
    const control = new Int32Array(message.sab, 0, CONTROL_WORDS);
    try {
      const response = await handler(Object.freeze({ ...message.request }));
      if (!(response instanceof Uint8Array) || response.byteLength > message.request.maxBytes) throw new Error('invalid response');
      new Uint8Array(message.sab, CONTROL_BYTES, response.byteLength).set(response);
      Atomics.store(control, 1, response.byteLength);
      Atomics.store(control, 0, 1);
    } catch (_) {
      Atomics.store(control, 0, -1);
    } finally {
      Atomics.notify(control, 0, 1);
    }
  };
  worker.addEventListener('message', listener);
  return () => worker.removeEventListener('message', listener);
}

export function attachSabHttpPostBridge(worker, handler) {
  if (!worker || typeof worker.addEventListener !== 'function') throw new TypeError('worker required');
  if (typeof handler !== 'function') throw new TypeError('handler required');
  const listener = async (event) => {
    const message = event.data;
    if (!message || message.type !== 'kotoba:http-post' || !(message.sab instanceof SharedArrayBuffer)) return;
    const control = new Int32Array(message.sab, 0, CONTROL_WORDS);
    try {
      const response = await handler(Object.freeze({ ...message.request }));
      if (!(response instanceof Uint8Array) || response.byteLength > message.request.maxBytes) throw new Error('invalid response');
      new Uint8Array(message.sab, CONTROL_BYTES, response.byteLength).set(response);
      Atomics.store(control, 1, response.byteLength);
      Atomics.store(control, 0, 1);
    } catch (_) {
      Atomics.store(control, 0, -1);
    } finally {
      Atomics.notify(control, 0, 1);
    }
  };
  worker.addEventListener('message', listener);
  return () => worker.removeEventListener('message', listener);
}
