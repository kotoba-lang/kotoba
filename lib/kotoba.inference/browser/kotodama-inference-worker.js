import init, { BrowserInferenceWorker } from "../pkg-web/kotoba_kotodama_inference.js";

let engine = null;
let initPromise = null;

async function ensureEngine(wasmUrl) {
  if (!initPromise) {
    const defaultWasmUrl = new URL(
      "../pkg-web/kotoba_kotodama_inference_bg.wasm",
      import.meta.url,
    );
    initPromise = init(wasmUrl || defaultWasmUrl).then(async () => {
      engine = await BrowserInferenceWorker.create();
      return engine;
    });
  }
  return initPromise;
}

async function loadWeightsFromMessage(msg) {
  const e = await ensureEngine(msg.wasmUrl);
  if (msg.weights instanceof Uint8Array) {
    return e.loadWeights(msg.weights);
  }
  if (msg.weights instanceof ArrayBuffer) {
    return e.loadWeights(new Uint8Array(msg.weights));
  }
  if (msg.weightsUrl) {
    const response = await fetch(msg.weightsUrl);
    if (!response.ok) {
      throw new Error(`failed to fetch weights: ${response.status} ${response.statusText}`);
    }
    return e.loadWeights(new Uint8Array(await response.arrayBuffer()));
  }
  throw new Error("loadWeights requires weights, ArrayBuffer, or weightsUrl");
}

async function handle(msg) {
  const e = await ensureEngine(msg.wasmUrl);
  switch (msg.type) {
    case "init":
      return { ok: true, capabilities: JSON.parse(e.probeCapabilities()) };
    case "probe":
      return JSON.parse(e.probeCapabilities());
    case "registerEnvelope":
      return JSON.parse(e.buildRegisterEnvelope());
    case "setSessionId":
      e.setSessionId(msg.sessionId || "");
      return { ok: true };
    case "loadWeights":
      return { ok: true, info: await loadWeightsFromMessage(msg) };
    case "hasModel":
      return { hasModel: e.hasModel() };
    case "forward": {
      const input = msg.inputIds instanceof Uint32Array
        ? msg.inputIds
        : new Uint32Array(msg.inputIds || []);
      const logits = await e.inferenceForward(input);
      return { logits };
    }
    case "matmul": {
      const out = await e.matmul(
        msg.a instanceof Float32Array ? msg.a : new Float32Array(msg.a || []),
        msg.b instanceof Float32Array ? msg.b : new Float32Array(msg.b || []),
        msg.m,
        msg.k,
        msg.n,
      );
      return { output: out };
    }
    case "executeShard":
      return JSON.parse(await e.executeShard(
        msg.taskId,
        msg.leaseId,
        msg.hiddenStatesB64,
        msg.shardParams || "{}",
      ));
    default:
      throw new Error(`unknown kotodama inference command: ${msg.type}`);
  }
}

self.onmessage = async (event) => {
  const msg = event.data || {};
  try {
    const result = await handle(msg);
    const transfers = [];
    if (result?.logits?.buffer) transfers.push(result.logits.buffer);
    if (result?.output?.buffer) transfers.push(result.output.buffer);
    self.postMessage({ id: msg.id, ok: true, result }, transfers);
  } catch (error) {
    self.postMessage({
      id: msg.id,
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
};
