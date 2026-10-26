// Runs INSIDE a dedicated Worker -- the guest-hosting counterpart to
// `kotoba-wasm-worker-element.js`. `http_post`'s SharedArrayBuffer+
// Atomics.wait bridge (`http-post-bridge.js`'s `createSabHttpPostBridge`)
// must be constructed off the main/DOM thread (browsers throw if
// `Atomics.wait` runs there), so the whole guest instantiation + call
// happens here, in the Worker, not in `KotobaWasmElement`'s main-thread
// `connectedCallback`.
//
// Message protocol with the main thread (`kotoba-wasm-worker-element.js`):
//   in:  {kind: 'run', src, exportName, grants, limits, llmInferUrl}
//   out: {ok: true, result: <string>} | {ok: false, error: <string>}
// `result` is stringified (not sent as a raw BigInt) for the widest
// structured-clone compatibility across engines -- every current export in
// this ABI returns `i64`, always representable as a decimal string.
//
// `llm-infer` reuses this SAME SAB+Atomics bridge instance as `http-post` --
// both are "a synchronous host-import needs to trigger real async network
// I/O", solved identically. `llmInferUrl` is a caller-supplied endpoint that
// `llm_infer` POSTs the raw prompt bytes to and reads the raw completion
// text back from -- a developer-controlled proxy that itself holds any real
// LLM API key server-side. NEVER embed a real LLM provider API key in
// browser-shipped JS/HTML calling the provider directly; that's the whole
// reason this is a caller-supplied URL instead of a built-in Anthropic call
// like `kototama.tender`'s (JVM-only, server-side) `anthropic-infer`.
import { actorHostImports, hostCaps, memoryWithinCap } from './actor-host.js';
import { createSabHttpPostBridge } from './http-post-bridge.js';

self.onmessage = async (event) => {
  const msg = event.data;
  if (msg.kind !== 'run') return;
  const grants = msg.grants || ['http-post'];
  const limits = msg.limits || { maxHttpPosts: 8 };
  let bridge;
  try {
    // `createSabHttpPostBridge` now awaits a real ready handshake from its
    // inner Worker before resolving, so the first `postSync` call below is
    // never racing the inner Worker's startup.
    bridge = await createSabHttpPostBridge();
    const memoryBox = {};
    const caps = hostCaps({ grants, limits });
    const importObject = {
      kotoba: actorHostImports(grants, caps, memoryBox, {
        httpPostBridge: bridge,
        llmInferBridge: bridge,
        llmInferUrl: msg.llmInferUrl,
      }),
    };
    const response = await fetch(msg.src);
    const { instance } = await WebAssembly.instantiateStreaming(response, importObject);
    memoryBox.memory = instance.exports.memory;
    // Preventive check, run BEFORE the guest's export is ever called (see
    // memoryWithinCap's doc comment in actor-host.js): refuses a guest
    // whose own declared memory section already exceeds the page cap.
    // Growth DURING the call itself is only caught reactively, per
    // host-import call (actorHostImports' `overMemoryCap`) -- a guest that
    // grows past budget and never calls back into the host isn't caught
    // until it returns, if at all.
    if (!memoryWithinCap(memoryBox, caps)) {
      throw new Error('kototama actor-host: guest memory exceeds maxMemoryPages before running');
    }
    const fn = instance.exports[msg.exportName || 'main'];
    if (typeof fn !== 'function') {
      throw new Error(`module has no export "${msg.exportName || 'main'}"`);
    }
    const result = fn();
    self.postMessage({ ok: true, result: result.toString() });
  } catch (err) {
    self.postMessage({ ok: false, error: err.message });
  } finally {
    if (bridge) bridge.dispose();
  }
};
