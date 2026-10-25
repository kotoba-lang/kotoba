export class KotodamaInferenceClient {
  constructor(worker = new Worker(new URL("./kotodama-inference-worker.js", import.meta.url), {
    type: "module",
  })) {
    this.worker = worker;
    this.nextId = 1;
    this.pending = new Map();
    this.worker.onmessage = (event) => this.#onMessage(event.data);
  }

  init(options = {}) {
    return this.#request({ type: "init", wasmUrl: options.wasmUrl });
  }

  probe() {
    return this.#request({ type: "probe" });
  }

  registerEnvelope() {
    return this.#request({ type: "registerEnvelope" });
  }

  setSessionId(sessionId) {
    return this.#request({ type: "setSessionId", sessionId });
  }

  loadWeightsUrl(weightsUrl) {
    return this.#request({ type: "loadWeights", weightsUrl });
  }

  loadWeightsBytes(weights) {
    const bytes = weights instanceof Uint8Array ? weights : new Uint8Array(weights);
    return this.#request({ type: "loadWeights", weights: bytes }, [bytes.buffer]);
  }

  hasModel() {
    return this.#request({ type: "hasModel" });
  }

  forward(inputIds) {
    const ids = inputIds instanceof Uint32Array ? inputIds : new Uint32Array(inputIds);
    return this.#request({ type: "forward", inputIds: ids }, [ids.buffer]);
  }

  matmul(a, b, m, k, n) {
    const aa = a instanceof Float32Array ? a : new Float32Array(a);
    const bb = b instanceof Float32Array ? b : new Float32Array(b);
    return this.#request({ type: "matmul", a: aa, b: bb, m, k, n }, [aa.buffer, bb.buffer]);
  }

  executeShard(task) {
    return this.#request({
      type: "executeShard",
      taskId: task.taskId,
      leaseId: task.leaseId,
      hiddenStatesB64: task.hiddenStatesB64,
      shardParams: task.shardParams || "{}",
    });
  }

  close() {
    this.worker.terminate();
    for (const { reject } of this.pending.values()) {
      reject(new Error("kotodama inference worker terminated"));
    }
    this.pending.clear();
  }

  #request(message, transfers = []) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage({ ...message, id }, transfers);
    });
  }

  #onMessage(message) {
    const pending = this.pending.get(message.id);
    if (!pending) return;
    this.pending.delete(message.id);
    if (message.ok) {
      pending.resolve(message.result);
    } else {
      pending.reject(new Error(message.error || "kotodama inference worker failed"));
    }
  }
}
