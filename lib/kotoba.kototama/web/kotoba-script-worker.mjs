import { runKotobaScript } from "./kotoba-script-host.mjs";

const MAX_SOURCE_BYTES = 1024 * 1024;
const MAX_VALUE_NODES = 1024;

function checkedValue(value, depth = 0, budget = { nodes: 0 }) {
  budget.nodes += 1;
  if (budget.nodes > MAX_VALUE_NODES || depth > 32) {
    throw new Error("kotoba-worker-value-limit");
  }
  if (typeof value === "bigint") return value;
  if (Array.isArray(value) && value.length === 2) {
    return Object.freeze(value.map(item => checkedValue(item, depth + 1, budget)));
  }
  throw new Error("kotoba-worker-value-rejected");
}

self.onmessage = async event => {
  const { id, sourceText, manifest, exportName = "main", args = [] } = event.data ?? {};
  try {
    if (typeof id !== "string" || typeof sourceText !== "string" ||
        new TextEncoder().encode(sourceText).byteLength > MAX_SOURCE_BYTES) {
      throw new Error("kotoba-worker-request-rejected");
    }
    // Capability providers are intentionally installed inside this worker in a
    // future registry. Functions from the main realm are never accepted.
    const safeArgs = args.map(value => checkedValue(value));
    const result = await runKotobaScript(null, {
      providers: new Map(), exportName, args: safeArgs,
      verification: { sourceText, manifest }
    });
    self.postMessage({ id, ok: true, value: checkedValue(result.value), artifact: result.artifact });
  } catch (error) {
    self.postMessage({ id, ok: false, error: String(error?.message ?? error) });
  }
};

self.postMessage({ type: "kotoba-worker-ready" });
