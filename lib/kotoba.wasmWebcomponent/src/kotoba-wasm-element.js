// KotobaWasmElement: a reusable base for hosting a `kotoba wasm emit`
// binary (kotoba-lang/kotoba) as a browser WebComponent, running it via the
// browser's own native WebAssembly engine -- already-AOT-compiled machine
// code, no interpreter, no JVM, no com.dylibso.chicory, no wasmtime. This is
// the library kotoba-lang/kototama's original `web/` PoC (kototama-wasm-run.js
// + kototama-wasm-kgraph-demo.js) was extracted from -- see README.md.
//
// NO fuel or memory-cap protection here, structurally, not just by
// omission: `fn()` below runs synchronously on the MAIN/DOM thread, so
// there is no way for any JS code (a `setTimeout`, another thread, nothing)
// to preempt or observe it mid-call -- a genuinely-hanging or
// memory-bombing guest freezes the whole page/tab until it returns (or
// the OS kills the process). `KotobaWasmWorkerElement`
// (kotoba-wasm-worker-element.js) exists specifically to fix this: it runs
// the guest in a dedicated Worker so a wall-clock deadline can
// `worker.terminate()` a runaway guest (its own namespace comment explains
// why that's the achievable fuel-equivalent here, versus
// kototama.tender's real instruction-count fuel). `actorHostImports`'
// `maxMemoryPages` reactive check (actor-host.js) still applies if a
// `createImports` implementation uses it, but that only catches a guest
// that also calls back into the host after growing -- prefer
// `KotobaWasmWorkerElement` for anything untrusted or capability-bearing.
//
// Usage (zero-import module):
//   import { KotobaWasmElement } from './kotoba-wasm-element.js';
//   KotobaWasmElement.define('my-wasm-run');
//   <my-wasm-run src="./demo.wasm"></my-wasm-run>
//
// Usage (module with host imports, e.g. kgraph.js's kgraphHostImports):
//   import { KotobaWasmElement } from './kotoba-wasm-element.js';
//   import { kgraphHostImports } from './kgraph.js';
//   KotobaWasmElement.define('my-kgraph-demo', {
//     createImports(memoryBox) {
//       const store = [];
//       return { kotoba: kgraphHostImports(store, memoryBox) };
//     },
//   });
export class KotobaWasmElement extends HTMLElement {
  // Registers a customElements.define()-backed tag hosting a
  // kotoba-wasm-emitted binary. OPTIONS:
  //   exportName  - export to call after instantiate (default "main", or
  //                 the element's "export" attribute if set).
  //   createImports(memoryBox) -> importObject
  //                 called once per element instance, BEFORE
  //                 WebAssembly.instantiate; memoryBox is an empty {} that
  //                 gets `.memory` set to `instance.exports.memory` right
  //                 after instantiation resolves (host-import functions
  //                 read/write through it, since they can only actually be
  //                 CALLED after the guest's export runs, by which point the
  //                 box is populated). Default: no imports (`{}`).
  //   render(pre, ctx) - ctx = {src, exportName, result, memoryBox, instance}.
  //                 Default: prints "src export() => result" as text.
  static define(tagName, options = {}) {
    class Defined extends KotobaWasmElement {
      get exportName() {
        return this.getAttribute('export') || options.exportName || 'main';
      }

      createImports(memoryBox) {
        return options.createImports ? options.createImports(memoryBox) : {};
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

  // Base-class defaults, used when a subclass is authored by hand (extends
  // KotobaWasmElement) instead of going through .define(options) -- kept in
  // sync with .define()'s fallback behavior so both paths are safe.
  get exportName() {
    return this.getAttribute('export') || 'main';
  }

  createImports(_memoryBox) {
    return {};
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

    try {
      const memoryBox = {};
      const importObject = this.createImports(memoryBox);

      const response = await fetch(src);
      const { instance } = await WebAssembly.instantiateStreaming(response, importObject);
      memoryBox.memory = instance.exports.memory;

      const fn = instance.exports[exportName];
      if (typeof fn !== 'function') {
        throw new Error(`module has no export "${exportName}"`);
      }
      const result = fn();

      this.render(pre, { src, exportName, result, memoryBox, instance });
      this.dispatchEvent(new CustomEvent('kotoba-wasm:done', { detail: { result } }));
    } catch (err) {
      pre.textContent = `ERROR: ${err.message}`;
      this.dispatchEvent(new CustomEvent('kotoba-wasm:error', { detail: { error: err.message } }));
    }
  }
}
