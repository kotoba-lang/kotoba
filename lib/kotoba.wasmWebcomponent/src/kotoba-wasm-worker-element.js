// KotobaWasmWorkerElement: a Worker-hosted sibling of `KotobaWasmElement`
// (kotoba-wasm-element.js). Exists for capabilities whose host-import
// implementation cannot run on the main/DOM thread -- today that's
// `http-post`'s SharedArrayBuffer+Atomics.wait bridge (browsers throw if
// `Atomics.wait` is called there). Everything (fetch the guest, instantiate
// it, wire imports, call the export) happens inside a dedicated Worker
// (`kotoba-wasm-worker-host.js`); this element just spawns that Worker,
// forwards {src, exportName}, and renders whatever comes back.
//
// Usage (zero-import module, mirrors KotobaWasmElement.define):
//   import { KotobaWasmWorkerElement } from './kotoba-wasm-worker-element.js';
//   KotobaWasmWorkerElement.define('my-worker-demo');
//   <my-worker-demo src="./demo.wasm"></my-worker-demo>
//
// Requires a cross-origin-isolated page (COOP: same-origin + COEP:
// require-corp) for the guest's `http-post` import to actually work --
// see `http-post-bridge.js`'s own header comment. Without it,
// `createSabHttpPostBridge` throws inside the Worker and this element
// renders that error message, same as any other guest failure.
export class KotobaWasmWorkerElement extends HTMLElement {
  static define(tagName, options = {}) {
    class Defined extends KotobaWasmWorkerElement {
      get exportName() {
        return this.getAttribute('export') || options.exportName || 'main';
      }

      get workerUrl() {
        return options.workerUrl || new URL('./kotoba-wasm-worker-host.js', import.meta.url);
      }

      render(pre, ctx) {
        if (options.render) {
          options.render(pre, ctx);
        } else {
          pre.textContent = `${ctx.src} ${ctx.exportName}() => ${ctx.result}`;
        }
      }
    }
    customElements.define(tagName, Defined);
    return Defined;
  }

  get exportName() {
    return this.getAttribute('export') || 'main';
  }

  get workerUrl() {
    return new URL('./kotoba-wasm-worker-host.js', import.meta.url);
  }

  render(pre, ctx) {
    pre.textContent = `${ctx.src} ${ctx.exportName}() => ${ctx.result}`;
  }

  async connectedCallback() {
    const shadow = this.attachShadow({ mode: 'open' });
    const pre = document.createElement('pre');
    shadow.appendChild(pre);

    const src = this.getAttribute('src');
    const exportName = this.exportName;
    // `grants="http-post,llm-infer"` (comma-separated); defaults to
    // http-post only, matching kotoba-wasm-worker-host.js's own fallback.
    const grantsAttr = this.getAttribute('grants');
    const grants = grantsAttr
      ? grantsAttr.split(',').map((g) => g.trim()).filter(Boolean)
      : undefined;
    const maxHttpPosts = this.getAttribute('max-http-posts');
    const maxLlmInfers = this.getAttribute('max-llm-infers');
    const maxMemoryPages = this.getAttribute('max-memory-pages');
    const limits =
      maxHttpPosts != null || maxLlmInfers != null || maxMemoryPages != null
        ? {
            maxHttpPosts: maxHttpPosts != null ? Number(maxHttpPosts) : 8,
            maxLlmInfers: maxLlmInfers != null ? Number(maxLlmInfers) : 0,
            ...(maxMemoryPages != null ? { maxMemoryPages: Number(maxMemoryPages) } : {}),
          }
        : undefined;
    // Wall-clock guest budget in ms -- the browser/Node equivalent of
    // kototama.tender's (JVM/Chicory) instruction-count `fuel-listener`
    // (tender.clj:524-555, default 5,000,000 instructions). There is no
    // portable way to preempt a running, synchronous, engine-compiled Wasm
    // call from JS mid-instruction (Chicory can because it's an
    // interpreter dispatching one instruction at a time in Java; V8/JSC
    // WASM execution is JIT-compiled and opaque to the host once called).
    // The mechanism here is coarser but real: the guest runs in a dedicated
    // Worker (this element's whole reason to exist over KotobaWasmElement),
    // so a wall-clock deadline can hard-kill that Worker via
    // `worker.terminate()` -- bounding a runaway/looping guest to a fixed
    // wall-clock budget instead of letting it hang forever, same practical
    // goal `fuel-listener` serves on the JVM host, achieved by isolation
    // instead of instruction counting. Same 5000 ms default as
    // kototama.contract's `default-runtime-limits` :max-wall-ms
    // (contract.cljc:216) -- notably NOT currently enforced by tender.clj
    // itself (fuel already covers the runaway-loop case there); here it IS
    // the primary defense, since there is no fuel equivalent.
    const maxWallMsAttr = this.getAttribute('max-wall-ms');
    const maxWallMs = maxWallMsAttr != null ? Number(maxWallMsAttr) : 5000;
    // Developer-controlled proxy endpoint for llm-infer -- see
    // kotoba-wasm-worker-host.js's namespace comment for why this must
    // never be a real LLM provider URL called directly from the browser.
    const llmInferUrl = this.getAttribute('llm-infer-url') || undefined;
    let worker;

    try {
      // `src` is resolved against THIS PAGE's location before it crosses
      // into the Worker -- a relative path posted as-is would instead
      // resolve against `kotoba-wasm-worker-host.js`'s own script location
      // once `fetch` runs inside the Worker (confirmed live: a
      // `./foo.wasm` guest next to the page 404'd because the Worker
      // fetched `src/foo.wasm` instead, next to the worker script).
      const resolvedSrc = new URL(src, location.href).href;
      worker = new Worker(this.workerUrl, { type: 'module' });
      const run = new Promise((resolve, reject) => {
        worker.onmessage = (event) => {
          if (event.data.ok) resolve(event.data.result);
          else reject(new Error(event.data.error));
        };
        worker.onerror = (event) => reject(new Error(event.message));
        worker.postMessage({ kind: 'run', src: resolvedSrc, exportName, grants, limits, llmInferUrl });
      });
      // Races `run` against the wall-clock deadline above. On timeout,
      // `worker.terminate()` fires HERE (not just in `finally` below) --
      // `finally`'s own `worker.terminate()` never runs until this `await`
      // settles, so without this explicit terminate a hung guest would
      // never actually be killed, defeating the whole point of the
      // deadline. `worker.terminate()` is safe to call twice (idempotent).
      let timeoutId;
      const deadline = new Promise((_resolve, reject) => {
        timeoutId = setTimeout(() => {
          worker.terminate();
          reject(new Error(
            `kotoba-wasm-worker-element: guest exceeded max-wall-ms=${maxWallMs}, terminated`
          ));
        }, maxWallMs);
      });
      const result = await Promise.race([run, deadline]);
      clearTimeout(timeoutId);

      this.render(pre, { src, exportName, result });
      this.dispatchEvent(new CustomEvent('kotoba-wasm:done', { detail: { result } }));
    } catch (err) {
      pre.textContent = `ERROR: ${err.message}`;
      this.dispatchEvent(new CustomEvent('kotoba-wasm:error', { detail: { error: err.message } }));
    } finally {
      if (worker) worker.terminate();
    }
  }
}
