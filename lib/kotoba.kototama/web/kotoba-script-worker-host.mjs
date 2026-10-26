const DEFAULT_TIMEOUT_MS = 1000;
const DEFAULT_STARTUP_TIMEOUT_MS = 15000;
const MAX_SOURCE_BYTES = 1024 * 1024;
const MAX_ARGS = 64;
const MAX_VALUE_NODES = 1024;

function checkedArtifact(value) {
  const capabilities = value?.requiredCapabilities;
  if (!value || value.schema !== "kotoba-js-artifact/v1" ||
      typeof value.sourceDigest !== "string" || typeof value.kirDigest !== "string" ||
      typeof value.compilerVersion !== "string" || !Array.isArray(capabilities) ||
      capabilities.length > 256 || !capabilities.every(Number.isSafeInteger)) {
    throw new Error("kotoba-isolated-artifact-rejected");
  }
  return Object.freeze({
    schema: value.schema,
    sourceDigest: value.sourceDigest,
    kirDigest: value.kirDigest,
    compilerVersion: value.compilerVersion,
    requiredCapabilities: Object.freeze([...capabilities])
  });
}

function checkedValue(value, depth = 0, budget = { nodes: 0 }) {
  budget.nodes += 1;
  if (budget.nodes > MAX_VALUE_NODES || depth > 32) {
    throw new Error("kotoba-isolated-value-limit");
  }
  if (typeof value === "bigint") return value;
  if (Array.isArray(value) && value.length === 2) {
    return Object.freeze(value.map(item => checkedValue(item, depth + 1, budget)));
  }
  throw new Error("kotoba-isolated-value-rejected");
}

function defaultWorkerFactory() {
  return new Worker(new URL("./kotoba-script-worker.mjs", import.meta.url), {
    type: "module", name: "kotoba-script"
  });
}

export function runKotobaScriptIsolated(options) {
  const {
    sourceText, manifest, exportName = "main", args = [],
    timeoutMs = DEFAULT_TIMEOUT_MS, startupTimeoutMs = DEFAULT_STARTUP_TIMEOUT_MS,
    workerFactory = defaultWorkerFactory
  } = options ?? {};
  if (typeof sourceText !== "string" ||
      new TextEncoder().encode(sourceText).byteLength > MAX_SOURCE_BYTES ||
      !manifest || typeof manifest !== "object" ||
      typeof exportName !== "string" || !Array.isArray(args) || args.length > MAX_ARGS ||
      !Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30_000 ||
      !Number.isSafeInteger(startupTimeoutMs) || startupTimeoutMs < 1 ||
      startupTimeoutMs > 30_000) {
    return Promise.reject(new Error("kotoba-isolated-request-rejected"));
  }
  let safeArgs;
  try { safeArgs = args.map(value => checkedValue(value)); }
  catch (error) { return Promise.reject(error); }

  const worker = workerFactory();
  const id = crypto.randomUUID();
  return new Promise((resolve, reject) => {
    let settled = false;
    let executionTimer;
    const finish = (operation, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(startupTimer);
      clearTimeout(executionTimer);
      worker.terminate();
      operation(value);
    };
    const startupTimer = setTimeout(
      () => finish(reject, new Error("kotoba-worker-startup-timeout")), startupTimeoutMs);
    worker.onmessage = event => {
      if (event.data?.type === "kotoba-worker-ready") {
        clearTimeout(startupTimer);
        executionTimer = setTimeout(
          () => finish(reject, new Error("kotoba-worker-timeout")), timeoutMs);
        try {
          worker.postMessage({ id, sourceText, manifest, exportName, args: safeArgs });
        } catch (_) {
          finish(reject, new Error("kotoba-worker-clone-rejected"));
        }
        return;
      }
      if (event.data?.id !== id) return;
      if (event.data.ok) {
        try {
          finish(resolve, Object.freeze({
            value: checkedValue(event.data.value), artifact: checkedArtifact(event.data.artifact)
          }));
        } catch (error) { finish(reject, error); }
      }
      else finish(reject, new Error(event.data.error || "kotoba-worker-failed"));
    };
    worker.onerror = () => finish(reject, new Error("kotoba-worker-crashed"));
  });
}
