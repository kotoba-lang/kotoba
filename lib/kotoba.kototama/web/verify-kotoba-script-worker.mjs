import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { runKotobaScriptIsolated } from "./kotoba-script-worker-host.mjs";

globalThis.crypto ??= webcrypto;
const request = { sourceText: "export const x=1;", manifest: { ok: true } };

function respondingWorker() {
  return {
    terminated: false,
    set onmessage(handler) {
      this._onmessage = handler;
      queueMicrotask(() => handler({ data: { type: "kotoba-worker-ready" } }));
    },
    get onmessage() { return this._onmessage; },
    postMessage(message) {
      queueMicrotask(() => this.onmessage({
        data: { id: message.id, ok: true, value: 42n, artifact: {
          schema: "kotoba-js-artifact/v1", sourceDigest: "source", kirDigest: "kir",
          compilerVersion: "compiler", requiredCapabilities: []
        } }
      }));
    },
    terminate() { this.terminated = true; }
  };
}

const worker = respondingWorker();
const result = await runKotobaScriptIsolated({ ...request, workerFactory: () => worker });
assert.equal(result.value, 42n);
assert.equal(worker.terminated, true);

const hanging = { postMessage() {}, terminate() { this.terminated = true; } };
Object.defineProperty(hanging, "onmessage", {
  set(handler) {
    this._onmessage = handler;
    queueMicrotask(() => handler({ data: { type: "kotoba-worker-ready" } }));
  }, get() { return this._onmessage; }
});
await assert.rejects(
  runKotobaScriptIsolated({ ...request, timeoutMs: 5, workerFactory: () => hanging }),
  /worker-timeout/);
assert.equal(hanging.terminated, true);

await assert.rejects(runKotobaScriptIsolated({
  ...request, args: Array(65), workerFactory: respondingWorker
}), /request-rejected/);
await assert.rejects(runKotobaScriptIsolated({
  ...request, args: [{ ambient: true }], workerFactory: respondingWorker
}), /value-rejected/);

const objectReturning = respondingWorker();
objectReturning.postMessage = function (message) {
  queueMicrotask(() => this.onmessage({
    data: { id: message.id, ok: true, value: { escaped: true }, artifact: {} }
  }));
};
await assert.rejects(runKotobaScriptIsolated({
  ...request, workerFactory: () => objectReturning
}), /value-rejected/);
console.log("kotoba-script worker host: ok");
