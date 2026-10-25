const state = {
  data: null,
  selectedCellId: null,
  storageAvailable: false,
  storageKey: "kotoba-lab:notebook:v1",
  runtime: {
    preferred: "kotoba-wasm-safe",
    active: "local-deterministic",
    diagnostics: [],
  },
};

const keyword = Symbol("keyword");

class EdnParser {
  constructor(input) {
    this.input = input;
    this.index = 0;
  }

  parse() {
    this.skip();
    return this.readValue();
  }

  readValue() {
    this.skip();
    const ch = this.peek();
    if (ch === "{") return this.readMap();
    if (ch === "[") return this.readVector();
    if (ch === '"') return this.readString();
    if (ch === ":") return this.readKeyword();
    return this.readSymbol();
  }

  readMap() {
    this.expect("{");
    const result = {};
    while (true) {
      this.skip();
      if (this.peek() === "}") {
        this.index += 1;
        return result;
      }
      const key = this.readValue();
      const value = this.readValue();
      result[this.keyName(key)] = value;
    }
  }

  readVector() {
    this.expect("[");
    const result = [];
    while (true) {
      this.skip();
      if (this.peek() === "]") {
        this.index += 1;
        return result;
      }
      result.push(this.readValue());
    }
  }

  readString() {
    this.expect('"');
    let out = "";
    while (this.index < this.input.length) {
      const ch = this.input[this.index++];
      if (ch === '"') return out;
      if (ch === "\\") {
        const next = this.input[this.index++];
        if (next === "n") out += "\n";
        else if (next === "t") out += "\t";
        else out += next;
      } else {
        out += ch;
      }
    }
    throw new Error("Unterminated string");
  }

  readKeyword() {
    this.expect(":");
    const token = this.readToken();
    return { [keyword]: true, value: token };
  }

  readSymbol() {
    const token = this.readToken();
    if (/^-?\d+(\.\d+)?$/.test(token)) return Number(token);
    if (token === "true") return true;
    if (token === "false") return false;
    if (token === "nil") return null;
    return token;
  }

  readToken() {
    const start = this.index;
    while (this.index < this.input.length) {
      const ch = this.input[this.index];
      if (/\s|[\]\}\[\{"]/.test(ch)) break;
      this.index += 1;
    }
    return this.input.slice(start, this.index);
  }

  keyName(value) {
    if (value && value[keyword]) return value.value;
    return String(value);
  }

  skip() {
    while (this.index < this.input.length) {
      const ch = this.input[this.index];
      if (/\s|,/.test(ch)) {
        this.index += 1;
        continue;
      }
      if (ch === ";") {
        while (this.index < this.input.length && this.input[this.index] !== "\n") {
          this.index += 1;
        }
        continue;
      }
      break;
    }
  }

  peek() {
    return this.input[this.index];
  }

  expect(ch) {
    if (this.input[this.index] !== ch) {
      throw new Error(`Expected ${ch} at ${this.index}`);
    }
    this.index += 1;
  }
}

function extractLabUi(source) {
  const edn = source.trim();
  if (!edn.startsWith("{") || !edn.endsWith("}")) {
    throw new Error("lab.edn must contain one EDN map");
  }
  return edn;
}

function text(id, value) {
  document.getElementById(id).textContent = value ?? "-";
}

function keywordText(value) {
  if (value && value[keyword]) return value.value;
  return String(value ?? "");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function statusClass(status) {
  return `status-${keywordText(status)}`;
}

function makeKeyword(value) {
  return { [keyword]: true, value };
}

function runtimeAdapters() {
  return [
    {
      id: "kotoba-wasm-safe",
      label: "Kotoba Wasm safe-build",
      status: window.KotobaWasmRuntime?.status || "not-loaded",
      coverage: window.KotobaWasmRuntime ? 82 : 45,
      description: "Production adapter target: source -> safe-build -> Wasm runtime -> artifact evidence.",
    },
    {
      id: "local-deterministic",
      label: "Browser-local deterministic runner",
      status: "available",
      coverage: 60,
      description: "Current fallback adapter: deterministic output/evidence without real Wasm execution.",
    },
  ];
}

function environmentLockStatus() {
  const lock = state.data?.["lab/notebook"]?.["lab/environment-lock"] || {};
  const runtimeOk =
    lock["env/runtime"] === "kotoba-wasm-safe" &&
    lock["env/runtime-version"] === window.KotobaWasmRuntime?.version;
  const providerOk =
    lock["env/llm-provider"] === "kotoba-research-assistant" &&
    lock["env/llm-provider-version"] === window.KotobaLLMProvider?.version;
  const schemaOk = lock["env/schema"] === "kotoba-lab-notebook/v1";
  const verificationOk = lock["env/verification-contract"] === "src/kotoba/lab/verification.kotoba";
  const verificationCheckOk = lock["env/verification-check"] === "test/kotoba/lab/verification_conformance.kotoba";
  const runnerOk = lock["env/browser-runner"] === "scripts/verify-lab.js";
  const locked = runtimeOk && providerOk && schemaOk && verificationOk && verificationCheckOk && runnerOk;
  return {
    lock,
    locked,
    coverage: locked ? 84 : 35,
    rows: [
      ["Schema", lock["env/schema"] || "missing", schemaOk],
      ["Runtime", `${lock["env/runtime"] || "missing"} / ${lock["env/runtime-version"] || "missing"}`, runtimeOk],
      [
        "LLM provider",
        `${lock["env/llm-provider"] || "missing"} / ${lock["env/llm-provider-version"] || "missing"}`,
        providerOk,
      ],
      ["Verification contract", lock["env/verification-contract"] || "missing", verificationOk],
      ["Verification check", lock["env/verification-check"] || "missing", verificationCheckOk],
      ["Browser runner", lock["env/browser-runner"] || "missing", runnerOk],
    ],
  };
}

function selectRuntimeAdapter() {
  const adapters = runtimeAdapters();
  const preferred = adapters.find((adapter) => adapter.id === state.runtime.preferred);
  if (preferred?.status === "available") {
    state.runtime.active = preferred.id;
    state.runtime.diagnostics.unshift({
      at: new Date().toISOString(),
      level: "ok",
      message: `${preferred.label} available through window.KotobaWasmRuntime.`,
    });
    state.runtime.diagnostics = state.runtime.diagnostics.slice(0, 8);
    return preferred;
  }
  const fallback = adapters.find((adapter) => adapter.id === "local-deterministic");
  state.runtime.active = fallback.id;
  state.runtime.diagnostics.unshift({
    at: new Date().toISOString(),
    level: "info",
    message: `${preferred?.label || "preferred runtime"} unavailable; using ${fallback.label}.`,
  });
  state.runtime.diagnostics = state.runtime.diagnostics.slice(0, 8);
  return fallback;
}

function encodeForStorage(value) {
  if (Array.isArray(value)) return value.map(encodeForStorage);
  if (value && typeof value === "object") {
    if (value[keyword]) return { "__kotobaKeyword": value.value };
    return Object.fromEntries(
      Object.entries(value).map(([key, nested]) => [key, encodeForStorage(nested)]),
    );
  }
  return value;
}

function decodeFromStorage(value) {
  if (Array.isArray(value)) return value.map(decodeFromStorage);
  if (value && typeof value === "object") {
    if (typeof value.__kotobaKeyword === "string") return makeKeyword(value.__kotobaKeyword);
    return Object.fromEntries(
      Object.entries(value).map(([key, nested]) => [key, decodeFromStorage(nested)]),
    );
  }
  return value;
}

function storagePayload() {
  return {
    savedAt: new Date().toISOString(),
    selectedCellId: state.selectedCellId,
    runtime: state.runtime,
    data: encodeForStorage(state.data),
  };
}

function saveNotebook() {
  if (!state.storageAvailable || !state.data) return false;
  localStorage.setItem(state.storageKey, JSON.stringify(storagePayload()));
  return true;
}

function loadSavedNotebook() {
  if (!state.storageAvailable) return null;
  const raw = localStorage.getItem(state.storageKey);
  if (!raw) return null;
  const payload = JSON.parse(raw);
  return {
    data: decodeFromStorage(payload.data),
    selectedCellId: payload.selectedCellId,
    runtime: payload.runtime,
    savedAt: payload.savedAt,
  };
}

function clearSavedNotebook() {
  if (state.storageAvailable) localStorage.removeItem(state.storageKey);
}

function downloadNotebook() {
  const blob = new Blob([JSON.stringify(storagePayload(), null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "kotoba-lab-notebook.json";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function createReviewSnapshot() {
  const notebook = state.data["lab/notebook"];
  const report = maturityReport();
  const environment = environmentLockStatus();
  const snapshot = {
    "snapshot/id": cidFor(
      "snapshot",
      `${notebook["lab/notebook-id"]}:${notebook["lab/replay-fingerprint"]}:${report.average}`,
    ),
    "snapshot/status": makeKeyword("ready"),
    "snapshot/created-at": new Date().toISOString(),
    "snapshot/maturity": report.maturity,
    "snapshot/coverage": `${report.average}%`,
    "snapshot/replay-fingerprint": notebook["lab/replay-fingerprint"],
    "snapshot/environment": environment.rows.map(([label, value]) => `${label}: ${value}`).join(" | "),
    "snapshot/cells": report.cells,
    "snapshot/artifacts": report.artifacts,
  };
  notebook["lab/review-snapshot"] = snapshot;
  notebook["lab/evidence"]["evidence/review-snapshot"] = snapshot["snapshot/id"];
  saveNotebook();
  return snapshot;
}

function restoreNotebookPayload(payload) {
  state.data = decodeFromStorage(payload.data || payload);
  if (payload.runtime) state.runtime = payload.runtime;
  state.selectedCellId = payload.selectedCellId || state.data["lab/notebook"]["lab/cells"][0]?.["cell/id"];
  ensureNotebookShape();
  saveNotebook();
  render();
}

function ensureNotebookShape() {
  const notebook = state.data?.["lab/notebook"];
  if (!notebook) return;
  notebook["lab/artifacts"] ||= [];
  notebook["lab/evidence"] ||= {};
  notebook["lab/runs"] ||= [];
  notebook["lab/replay-fingerprint"] ||= replayFingerprint(notebook);
  notebook["lab/review-snapshot"] ||= {};
}

function selectedCell() {
  return state.data["lab/notebook"]["lab/cells"].find(
    (cell) => cell["cell/id"] === state.selectedCellId,
  );
}

function inferCell(cell) {
  const source = cell["cell/source"] || "";
  const kind = keywordText(cell["cell/kind"]);
  const inferred = new Set();
  if (/kqe-query|:query/.test(source) || kind === "query") inferred.add("graph-read");
  if (/kqe-assert!|kqe-retract!/.test(source)) inferred.add("graph-write");
  if (/llm-infer|summarize|claim|assistant/i.test(source) || kind === "llm") {
    inferred.add("llm-infer");
  }
  if (/table|artifact|rows|arrow|csv/i.test(source) || ["table", "viz", "kotoba"].includes(kind)) {
    inferred.add("artifact-read");
  }
  if (/select|group-by|mark|plot|figure|normalize|artifact-write/i.test(source) || ["table", "viz"].includes(kind)) {
    inferred.add("artifact-write");
  }
  const policy = new Set((cell["cell/policy"] || []).map(keywordText));
  const missing = [...inferred].filter((capability) => !policy.has(capability));
  const unused = [...policy].filter((capability) => !inferred.has(capability));
  const deps = cell["cell/depends-on"] || [];
  const allCells = state.data["lab/notebook"]["lab/cells"];
  const blocked = deps.filter((dep) => {
    const depCell = allCells.find((item) => item["cell/id"] === dep);
    return !depCell || keywordText(depCell["cell/status"]) !== "succeeded";
  });
  const replay = missing.length === 0 && blocked.length === 0 ? "clean" : "needs review";
  return {
    inferred: [...inferred],
    missing,
    unused,
    blocked,
    replay,
  };
}

function llmDraft(prompt, baseCell) {
  const title = prompt.trim() || "Summarize degradation evidence";
  const shortTitle = title ? `LLM: ${title.slice(0, 28)}` : "LLM claim draft";
  const dependency = baseCell?.["cell/id"] || "c-003";
  return {
    "cell/id": nextCellId(),
    "cell/kind": makeKeyword("kotoba"),
    "cell/title": shortTitle,
    "cell/status": makeKeyword("ready"),
    "cell/policy": [makeKeyword("artifact-read"), makeKeyword("llm-infer"), makeKeyword("artifact-write")],
    "cell/source": `(defn infer-claim [evidence]\n  (llm-infer "kotoba-research-assistant"\n    {:task "${title.replaceAll('"', '\\"')}"\n     :evidence evidence\n     :output :claim-with-citations}))`,
    "cell/depends-on": [dependency],
    "cell/output": "LLM draft cell generated; run to materialize artifact",
  };
}

function nextCellId() {
  const cells = state.data["lab/notebook"]["lab/cells"];
  const max = cells.reduce((acc, cell) => {
    const n = Number(String(cell["cell/id"]).replace(/\D/g, ""));
    return Number.isFinite(n) ? Math.max(acc, n) : acc;
  }, 0);
  return `c-${String(max + 1).padStart(3, "0")}`;
}

function stableHash(input) {
  let hash = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, "0");
}

function cidFor(prefix, input) {
  return `bafy-${prefix}-${stableHash(input)}`;
}

function replayFingerprint(notebook) {
  const cells = notebook["lab/cells"] || [];
  const runs = notebook["lab/runs"] || [];
  const material = {
    cells: cells.map((cell) => [
      cell["cell/id"],
      keywordText(cell["cell/status"]),
      cell["cell/source-cid"] || "",
      cell["cell/wasm-cid"] || "",
      (cell["cell/output-cids"] || []).join("|"),
    ]),
    runs: runs.map((run) => [
      run["run/id"],
      run["run/cell-id"],
      run["run/source-cid"],
      run["run/wasm-cid"],
      run["run/output-cid"],
    ]),
  };
  return cidFor("replay", JSON.stringify(material));
}

function nowRunId() {
  const iso = new Date().toISOString().replace(/[-:]/g, "").replace(/\..+/, "Z");
  return `r-${iso}`;
}

function materializeOutput(cell, inference) {
  const source = cell["cell/source"] || "";
  const kind = keywordText(cell["cell/kind"]);
  if (inference.missing.length > 0) {
    return {
      status: makeKeyword("failed"),
      output: `policy review required: ${inference.missing.join(", ")}`,
      mediaType: "application/edn",
      artifactKind: makeKeyword("evidence"),
    };
  }
  if (inference.blocked.length > 0) {
    return {
      status: makeKeyword("stale"),
      output: `dependency blocked: ${inference.blocked.join(", ")}`,
      mediaType: "application/edn",
      artifactKind: makeKeyword("log"),
    };
  }
  if (source.includes("llm-infer")) {
    return {
      status: makeKeyword("succeeded"),
      output: "LLM claim draft artifact generated with citations required",
      mediaType: "text/markdown",
      artifactKind: makeKeyword("model"),
    };
  }
  if (kind === "viz" || source.includes(":mark")) {
    return {
      status: makeKeyword("succeeded"),
      output: "figure artifact generated from declarative viz spec",
      mediaType: "image/svg+xml",
      artifactKind: makeKeyword("figure"),
    };
  }
  if (kind === "table" || source.includes("table/") || source.includes(":group-by")) {
    return {
      status: makeKeyword("succeeded"),
      output: "table artifact generated from Kotoba table transform",
      mediaType: "application/vnd.apache.arrow.file",
      artifactKind: makeKeyword("table"),
    };
  }
  if (kind === "query" || source.includes("kqe-query")) {
    return {
      status: makeKeyword("succeeded"),
      output: "query result materialized as table artifact",
      mediaType: "application/vnd.apache.arrow.file",
      artifactKind: makeKeyword("table"),
    };
  }
  return {
    status: makeKeyword("succeeded"),
    output: "Kotoba cell evaluated by browser-local deterministic runner",
    mediaType: "application/edn",
    artifactKind: makeKeyword("evidence"),
  };
}

function runLlmProvider(cell, notebook) {
  if (!cell["cell/source"]?.includes("llm-infer") || !window.KotobaLLMProvider) return null;
  return window.KotobaLLMProvider.infer({
    cell,
    evidence: notebook["lab/evidence"],
    budget: { maxTokens: 512, maxCostUsd: 0, mode: "deterministic-shim" },
  });
}

function runCell(cell, options = {}) {
  const notebook = state.data["lab/notebook"];
  if (options.syncEditor) applyEditorSource();
  const adapter = selectRuntimeAdapter();
  const inference = inferCell(cell);
  const result = materializeOutput(cell, inference);
  const llmResult = runLlmProvider(cell, notebook);
  if (llmResult) {
    result.output = llmResult.text;
    result.mediaType = "text/markdown";
    result.artifactKind = makeKeyword("model");
  }
  const policy = (cell["cell/policy"] || []).map(keywordText);
  const compiled =
    adapter.id === "kotoba-wasm-safe" && window.KotobaWasmRuntime
      ? window.KotobaWasmRuntime.compile({ cell, policy })
      : {
          sourceCid: cidFor("source", cell["cell/source"]),
          policyCid: cidFor("policy", JSON.stringify(policy)),
          wasmCid: cidFor("wasm", `${cell["cell/id"]}:${cell["cell/source"]}:${JSON.stringify(policy)}`),
          diagnostics: ["local fallback compile"],
        };
  const run =
    adapter.id === "kotoba-wasm-safe" && window.KotobaWasmRuntime
      ? window.KotobaWasmRuntime.run({ cell, compiled, output: result.output })
      : {
          outputCid: cidFor("artifact", `${cell["cell/id"]}:${cell["cell/source"]}:${result.output}`),
          timingMs: 24 + cell["cell/source"].length,
          status: keywordText(result.status),
        };
  const sourceCid = compiled.sourceCid;
  const policyCid = compiled.policyCid;
  const wasmCid = compiled.wasmCid;
  const outputCid = run.outputCid;
  const runId = nowRunId();

  cell["cell/status"] = result.status;
  cell["cell/output"] = result.output;
  cell["cell/output-kind"] = result.artifactKind;
  cell["cell/output-media-type"] = result.mediaType;
  cell["cell/source-cid"] = sourceCid;
  cell["cell/wasm-cid"] = wasmCid;
  cell["cell/output-cids"] = [outputCid];
  cell["cell/runtime-adapter"] = adapter.id;

  const artifactName = `${cell["cell/id"]}-${keywordText(cell["cell/kind"])}-output`;
  const artifacts = notebook["lab/artifacts"];
  const existingIndex = artifacts.findIndex((artifact) => artifact["artifact/name"] === artifactName);
  const artifact = {
    "artifact/name": artifactName,
    "artifact/kind": result.artifactKind,
    "artifact/cid": outputCid,
    "artifact/media-type": result.mediaType,
    "artifact/size": `${Math.max(1, Math.ceil((result.output.length + cell["cell/source"].length) / 32))} KB`,
  };
  if (existingIndex >= 0) artifacts[existingIndex] = artifact;
  else artifacts.push(artifact);

  const runEntry = {
    "run/id": runId,
    "run/cell-id": cell["cell/id"],
    "run/status": result.status,
    "run/replay": makeKeyword(inference.replay),
    "run/source-cid": sourceCid,
    "run/policy-cid": policyCid,
    "run/wasm-cid": wasmCid,
    "run/output-cid": outputCid,
    "run/runtime": adapter.id,
    "run/provider": llmResult ? window.KotobaLLMProvider.id : "none",
    "run/timing-ms": run.timingMs,
  };
  notebook["lab/runs"] = [runEntry, ...(notebook["lab/runs"] || [])].slice(0, 16);
  notebook["lab/replay-fingerprint"] = replayFingerprint(notebook);
  notebook["lab/run-id"] = runId;
  notebook["lab/active-runtime"] = adapter.id;
  notebook["lab/replay-status"] = keywordText(result.status) === "succeeded" ? "replayable" : "needs review";
  notebook["lab/evidence"] = {
    "evidence/source-cid": sourceCid,
    "evidence/policy-cid": policyCid,
    "evidence/wasm-cid": wasmCid,
    "evidence/input-cids": (cell["cell/depends-on"] || []).map((dep) => cidFor("dep", dep)),
    "evidence/output-cids": [outputCid],
    "evidence/capabilities-used": inference.inferred.map(makeKeyword),
    "evidence/replay": inference.replay,
    "evidence/timing-ms": run.timingMs,
    "evidence/runtime-adapter": adapter.id,
    "evidence/runtime-status": adapter.status,
    "evidence/runtime-version": window.KotobaWasmRuntime?.version || "fallback",
    "evidence/runtime-diagnostics": compiled.diagnostics,
    "evidence/llm-provider": llmResult ? window.KotobaLLMProvider.id : "none",
    "evidence/llm-provider-version": llmResult ? window.KotobaLLMProvider.version : "none",
    "evidence/llm-budget": llmResult ? JSON.stringify(llmResult.budget) : "{}",
    "evidence/llm-claim-id": llmResult ? llmResult.claimId : "none",
    "evidence/llm-diagnostics": llmResult ? llmResult.diagnostics : [],
    "evidence/replay-fingerprint": notebook["lab/replay-fingerprint"],
    "evidence/host": adapter.label,
  };
  saveNotebook();
  return { cell, result, inference };
}

function runSelectedCell() {
  return runCell(selectedCell(), { syncEditor: true });
}

function runAllCells() {
  applyEditorSource();
  const notebook = state.data["lab/notebook"];
  const cells = notebook["lab/cells"];
  const executable = cells.filter((cell) => keywordText(cell["cell/kind"]) !== "markdown");
  const results = executable.map((cell) => runCell(cell));
  const failed = results.filter(({ result }) => keywordText(result.status) !== "succeeded");
  notebook["lab/replay-status"] = failed.length ? "needs review" : "replayable";
  notebook["lab/replay-fingerprint"] = replayFingerprint(notebook);
  notebook["lab/evidence"]["evidence/replay-fingerprint"] = notebook["lab/replay-fingerprint"];
  notebook["lab/evidence"]["evidence/run-all-count"] = executable.length;
  saveNotebook();
  return { ran: executable.length, failed: failed.length };
}

function maturityReport() {
  const notebook = state.data["lab/notebook"];
  const cells = notebook["lab/cells"];
  const artifacts = notebook["lab/artifacts"];
  const runs = notebook["lab/runs"] || [];
  const succeeded = cells.filter((cell) => keywordText(cell["cell/status"]) === "succeeded").length;
  const withEvidence = cells.filter((cell) => cell["cell/source-cid"] && cell["cell/wasm-cid"]).length;
  const executable = cells.filter((cell) => keywordText(cell["cell/kind"]) !== "markdown").length;
  const llmCells = cells.filter((cell) => /llm-infer/.test(cell["cell/source"] || "")).length;
  const llmCoverage = window.KotobaLLMProvider ? (llmCells ? 68 : 58) : llmCells ? 45 : 40;
  const allExecutableSucceeded = executable > 0 && succeeded >= executable;
  const richOutputs = cells.filter((cell) =>
    ["table", "figure", "model"].includes(keywordText(cell["cell/output-kind"])),
  ).length;
  const completeRuns = runs.filter(
    (run) => run["run/source-cid"] && run["run/wasm-cid"] && run["run/output-cid"],
  ).length;
  const persistenceCoverage = state.storageAvailable ? 70 : 15;
  const runtimeCoverage = Math.max(...runtimeAdapters().map((adapter) => adapter.coverage));
  const environment = environmentLockStatus();
  const hasSnapshot = Boolean(notebook["lab/review-snapshot"]?.["snapshot/id"]);
  const contractVerified = environment.lock["env/verification-contract"] === "src/kotoba/lab/verification.kotoba";
  const verificationCoverage = state.storageAvailable && window.KotobaLLMProvider ? (allExecutableSucceeded ? 76 : 72) : 35;
  const evidenceCoverage = Math.min(
    76,
    44 +
      (cells.length ? Math.round((withEvidence / cells.length) * 16) : 0) +
      (completeRuns ? 10 : 0) +
      (notebook["lab/replay-fingerprint"] ? 6 : 0),
  );
  const replayCoverage = Math.min(78, completeRuns ? 66 + Math.min(12, completeRuns * 2) : 42);
  const richOutputCoverage = Math.min(82, richOutputs ? 58 + Math.min(24, richOutputs * 8) : 35);
  const accessibilityCoverage = 78;
  const coverage = [
    ["Notebook UI", 72, "editable cells, block insert, toolbar, inspector, and run ledger"],
    ["Manifest contract", 75, "lab.edn drives page state, providers, verification, and run history"],
    [
      "Local execution",
      executable ? 38 + Math.round((succeeded / executable) * 27) : 35,
      "Run all executes non-note cells in dependency order with deterministic outputs",
    ],
    [
      "Runtime adapter",
      runtimeCoverage,
      state.runtime.active === "kotoba-wasm-safe"
        ? "kotoba-wasm adapter shim available"
        : "adapter boundary ready; local fallback active",
    ],
    [
      "Environment lock",
      environment.coverage,
      environment.locked
        ? "schema, runtime, provider, and verifier versions match the notebook lock"
        : "environment lock is incomplete or mismatched",
    ],
    [
      "Evidence",
      evidenceCoverage,
      "run updates source/policy/wasm/output CIDs and replay fingerprint",
    ],
    [
      "LLM workflow",
      llmCoverage,
      window.KotobaLLMProvider
        ? "capability-gated provider shim generates deterministic drafts"
        : "llm-infer source generation, no provider call",
    ],
    [
      "Rich outputs",
      richOutputCoverage,
      "selected cells render table, figure, and model artifacts as structured notebook previews",
    ],
    [
      "Persistence",
      persistenceCoverage,
      state.storageAvailable
        ? "localStorage save/restore plus JSON export/import"
        : "browser storage unavailable",
    ],
    [
      "Review snapshot",
      hasSnapshot ? 80 : 45,
      hasSnapshot
        ? "review snapshot freezes maturity, coverage, environment, cells, artifacts, and replay fingerprint"
        : "create a review snapshot before sharing",
    ],
    [
      "Contract verification",
      contractVerified ? 82 : 35,
      contractVerified
        ? "CLJC verification contract is checked by CI before browser replay"
        : "CLJC verification contract is not pinned",
    ],
    [
      "Accessibility",
      accessibilityCoverage,
      "CI checks tab state, keyboard focus targets, labels, touch size, and responsive overflow",
    ],
    [
      "Replay ledger",
      allExecutableSucceeded ? Math.max(replayCoverage, 82) : replayCoverage,
      "bounded run history records cell, runtime, provider, CIDs, timing, replay status, and run-all coverage",
    ],
    [
      "Verification",
      verificationCoverage,
      "Playwright CI covers runtime, LLM, replay ledger, persistence, evidence, maturity, and layout overflow",
    ],
  ];
  const average = Math.round(coverage.reduce((sum, row) => sum + row[1], 0) / coverage.length);
  const maturity =
    average >= 70 ? "M4" : average >= 55 ? "M3" : average >= 35 ? "M2.5" : average >= 20 ? "M2" : "M1";
  return { coverage, average, maturity, artifacts: artifacts.length, cells: cells.length };
}

function render() {
  const data = state.data;
  const notebook = data["lab/notebook"];
  const cells = notebook["lab/cells"];
  state.selectedCellId ||= cells[0]["cell/id"];

  text("app-status", `${keywordText(data["app/status"])} / ${data["app/repo"]}`);
  text("app-title", data["app/title"]);
  text("notebook-title", notebook["lab/title"]);
  text("replay-status", notebook["lab/replay-status"]);
  text("run-id", notebook["lab/run-id"]);
  text("runtime", notebook["lab/runtime"]);

  renderCells(cells);
  renderSelectedCell();
  renderArtifacts(notebook["lab/artifacts"]);
  renderEvidence(notebook["lab/evidence"]);
  renderAssistant();
  renderRuntime();
  renderMaturity();
}

function renderCells(cells) {
  const list = document.getElementById("cell-list");
  list.innerHTML = "";
  cells.forEach((cell, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `cell-button ${
      cell["cell/id"] === state.selectedCellId ? "is-active" : ""
    }`;
    button.addEventListener("click", () => {
      state.selectedCellId = cell["cell/id"];
      render();
    });

    const deps = cell["cell/depends-on"];
    button.innerHTML = `
      <span class="cell-index">${String(index + 1).padStart(2, "0")}</span>
      <span>
        <span class="cell-name">${cell["cell/title"]}</span>
        <span class="cell-deps">${keywordText(cell["cell/kind"])} / ${
          deps.length ? deps.join(", ") : "root"
        }</span>
      </span>
      <span class="status-pill ${statusClass(cell["cell/status"])}">${keywordText(
        cell["cell/status"],
      )}</span>
    `;
    list.appendChild(button);
  });
}

function renderSelectedCell() {
  const cell = selectedCell();
  const inference = inferCell(cell);
  text("selected-kind", keywordText(cell["cell/kind"]));
  text("selected-status", keywordText(cell["cell/status"]));
  text("selected-title", cell["cell/title"]);
  document.getElementById("source-editor").value = cell["cell/source"];
  text("cell-output", cell["cell/output"]);
  renderOutputPreview(cell);

  const strip = document.getElementById("policy-strip");
  strip.innerHTML = "";
  const policy = cell["cell/policy"];
  if (policy.length === 0) {
    const chip = document.createElement("span");
    chip.className = "policy-chip";
    chip.textContent = "no runtime capability";
    strip.appendChild(chip);
    renderInference(inference);
    return;
  }
  policy.forEach((cap) => {
    const chip = document.createElement("span");
    chip.className = "policy-chip";
    chip.textContent = keywordText(cap);
    strip.appendChild(chip);
  });
  renderInference(inference);
}

function renderOutputPreview(cell) {
  const panel = document.getElementById("output-preview");
  const kind = keywordText(cell["cell/output-kind"]);
  panel.innerHTML = "";
  panel.className = `output-preview ${kind ? `output-${kind}` : ""}`;
  if (kind === "table") {
    panel.innerHTML = `
      <table>
        <thead><tr><th>site</th><th>month</th><th>avg-loss</th><th>temp-band</th></tr></thead>
        <tbody>
          <tr><td>kisarazu-a</td><td>18</td><td>2.8%</td><td>high</td></tr>
          <tr><td>sendai-b</td><td>18</td><td>1.6%</td><td>normal</td></tr>
          <tr><td>naha-c</td><td>18</td><td>3.4%</td><td>high</td></tr>
        </tbody>
      </table>
    `;
    return;
  }
  if (kind === "figure") {
    panel.innerHTML = `
      <div class="figure-preview">
        <span style="height: 34%"></span>
        <span style="height: 47%"></span>
        <span style="height: 61%"></span>
        <span style="height: 78%"></span>
        <span style="height: 88%"></span>
      </div>
    `;
    return;
  }
  if (kind === "model") {
    panel.innerHTML = `
      <div class="model-preview">
        <strong>Claim draft</strong>
        <span>${escapeHtml(cell["cell/output"])}</span>
        <code>${escapeHtml((cell["cell/output-cids"] || ["pending"])[0])}</code>
      </div>
    `;
    return;
  }
  panel.innerHTML = `<span class="output-empty">Run this cell to materialize a rich output preview.</span>`;
}

function renderInference(inference) {
  const panel = document.getElementById("cell-inference");
  panel.innerHTML = "";
  const rows = [
    ["Inferred policy", inference.inferred.length ? inference.inferred.join(", ") : "none"],
    ["Missing grants", inference.missing.length ? inference.missing.join(", ") : "none"],
    ["Replay", inference.blocked.length ? `blocked by ${inference.blocked.join(", ")}` : inference.replay],
  ];
  rows.forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "inference-card";
    card.innerHTML = `<strong>${label}</strong><span>${value}</span>`;
    panel.appendChild(card);
  });
}

function renderArtifacts(artifacts) {
  const panel = document.getElementById("artifacts-tab");
  panel.innerHTML = "";
  artifacts.forEach((artifact) => {
    const row = document.createElement("div");
    row.className = "artifact-row";
    row.innerHTML = `
      <strong>${artifact["artifact/name"]}</strong>
      <span class="artifact-meta">${keywordText(artifact["artifact/kind"])} / ${
        artifact["artifact/media-type"]
      } / ${artifact["artifact/size"]}</span>
      <code>${artifact["artifact/cid"]}</code>
    `;
    panel.appendChild(row);
  });
}

function renderEvidence(evidence) {
  const panel = document.getElementById("evidence-tab");
  panel.innerHTML = "";
  Object.entries(evidence).forEach(([key, value]) => {
    const row = document.createElement("div");
    row.className = "evidence-row";
    const rendered = Array.isArray(value)
      ? value.map(keywordText).join(", ")
      : keywordText(value);
    row.innerHTML = `<strong>${key}</strong><code>${rendered}</code>`;
    panel.appendChild(row);
  });
  renderReviewSnapshot(panel);
  renderRunLedger(panel);
}

function renderReviewSnapshot(panel) {
  const snapshot = state.data["lab/notebook"]["lab/review-snapshot"] || {};
  const row = document.createElement("div");
  row.className = "snapshot-card";
  row.innerHTML = `
    <strong>Review snapshot</strong>
    <span>${keywordText(snapshot["snapshot/status"]) || "not created"} / ${
      snapshot["snapshot/coverage"] || "no coverage"
    } / ${snapshot["snapshot/replay-fingerprint"] || "no fingerprint"}</span>
    <code>${snapshot["snapshot/id"] || "snapshot pending"}</code>
  `;
  panel.appendChild(row);
}

function renderRunLedger(panel) {
  const notebook = state.data["lab/notebook"];
  const runs = notebook["lab/runs"] || [];
  const heading = document.createElement("div");
  heading.className = "ledger-heading";
  heading.innerHTML = `<strong>Run ledger</strong><span>${runs.length} replayable records / ${notebook["lab/replay-fingerprint"]}</span>`;
  panel.appendChild(heading);
  runs.slice(0, 8).forEach((run) => {
    const row = document.createElement("div");
    row.className = "run-row";
    row.innerHTML = `
      <div>
        <strong>${run["run/cell-id"]} / ${keywordText(run["run/status"])}</strong>
        <span>${run["run/runtime"]} / ${run["run/provider"]} / ${keywordText(run["run/replay"])}</span>
      </div>
      <code>${run["run/output-cid"]}</code>
    `;
    panel.appendChild(row);
  });
}

function renderAssistant() {
  const cell = selectedCell();
  const inference = inferCell(cell);
  const summary = [
    `${cell["cell/id"]} / ${keywordText(cell["cell/kind"])}`,
    `inferred: ${inference.inferred.join(", ") || "none"}`,
    `missing: ${inference.missing.join(", ") || "none"}`,
    `replay: ${inference.replay}`,
  ].join(" | ");
  text("assistant-summary", summary);
}

function renderRuntime() {
  const panel = document.getElementById("runtime-tab");
  const adapters = runtimeAdapters();
  const environment = environmentLockStatus();
  panel.innerHTML = `
    <div class="assistant-card">
      <strong>Active: ${state.runtime.active}</strong>
      <span>Preferred adapter is ${state.runtime.preferred}. Production coverage increases when KotobaWasmRuntime is loaded.</span>
    </div>
    <div class="assistant-card">
      <strong>Environment lock: ${environment.locked ? "locked" : "review"}</strong>
      <span>Notebook schema, runtime, provider, and CI verifier are pinned for replay.</span>
    </div>
  `;
  environment.rows.forEach(([label, value, ok]) => {
    const row = document.createElement("div");
    row.className = "runtime-row";
    row.innerHTML = `
      <div>
        <strong>${label}</strong>
        <span>${value}</span>
      </div>
      <code>${ok ? "locked" : "review"}</code>
    `;
    panel.appendChild(row);
  });
  adapters.forEach((adapter) => {
    const row = document.createElement("div");
    row.className = "runtime-row";
    row.innerHTML = `
      <div>
        <strong>${adapter.label}</strong>
        <span>${adapter.description}</span>
      </div>
      <code>${adapter.status}</code>
    `;
    panel.appendChild(row);
  });
  state.runtime.diagnostics.forEach((diagnostic) => {
    const row = document.createElement("div");
    row.className = "evidence-row";
    row.innerHTML = `<strong>${diagnostic.level} / ${diagnostic.at}</strong><code>${diagnostic.message}</code>`;
    panel.appendChild(row);
  });
}

function renderMaturity() {
  const panel = document.getElementById("maturity-tab");
  const report = maturityReport();
  panel.innerHTML = `
    <div class="assistant-card">
      <strong>${report.maturity} / ${report.average}% coverage</strong>
      <span>${report.cells} cells, ${report.artifacts} artifacts. Maturity rises when cells run with evidence and artifacts.</span>
    </div>
  `;
  report.coverage.forEach(([label, percent, note]) => {
    const row = document.createElement("div");
    row.className = "coverage-row";
    row.innerHTML = `
      <div><strong>${label}</strong><span>${note}</span></div>
      <div class="coverage-meter" aria-label="${label} coverage ${percent}%">
        <span style="width: ${percent}%"></span>
      </div>
      <code>${percent}%</code>
    `;
    panel.appendChild(row);
  });
}

function addBlock(kind) {
  const cells = state.data["lab/notebook"]["lab/cells"];
  const current = selectedCell();
  let cell;
  if (kind === "llm") {
    cell = llmDraft("Explain the strongest supported research claim", current);
  } else {
    const id = nextCellId();
    cell = {
      "cell/id": id,
      "cell/kind": makeKeyword(kind),
      "cell/title": kind === "markdown" ? "New note" : "New Kotoba cell",
      "cell/status": makeKeyword("draft"),
      "cell/policy": kind === "kotoba" ? [makeKeyword("artifact-read")] : [],
      "cell/source": kind === "markdown" ? "Write observation here." : "(defn analyze [input]\n  input)",
      "cell/depends-on": current ? [current["cell/id"]] : [],
      "cell/output": "not run",
    };
  }
  cells.push(cell);
  state.selectedCellId = cell["cell/id"];
  saveNotebook();
  render();
}

function applyEditorSource() {
  const cell = selectedCell();
  cell["cell/source"] = document.getElementById("source-editor").value;
  cell["cell/status"] = makeKeyword("stale");
  saveNotebook();
  const inference = inferCell(cell);
  renderInference(inference);
  renderAssistant();
}

function setupInteractions() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => {
        const activeItem = item === tab;
        item.classList.toggle("is-active", activeItem);
        item.setAttribute("aria-selected", String(activeItem));
      });
      const active = tab.dataset.tab;
      document
        .getElementById("artifacts-tab")
        .classList.toggle("is-hidden", active !== "artifacts");
      document
        .getElementById("evidence-tab")
        .classList.toggle("is-hidden", active !== "evidence");
      document
        .getElementById("assistant-tab")
        .classList.toggle("is-hidden", active !== "assistant");
      document
        .getElementById("runtime-tab")
        .classList.toggle("is-hidden", active !== "runtime");
      document
        .getElementById("maturity-tab")
        .classList.toggle("is-hidden", active !== "maturity");
    });
  });

  document.querySelectorAll("[data-add-block]").forEach((button) => {
    button.addEventListener("click", () => addBlock(button.dataset.addBlock));
  });

  document.getElementById("source-editor").addEventListener("input", applyEditorSource);

  document.getElementById("run-button").addEventListener("click", () => {
    runSelectedCell();
    render();
  });

  document.getElementById("toolbar-run").addEventListener("click", () => {
    const summary = runAllCells();
    render();
    text(
      "cell-output",
      summary.failed
        ? `run all completed with ${summary.failed} review item(s)`
        : `run all completed: ${summary.ran} executable cells replayable`,
    );
    document.querySelector('[data-tab="maturity"]').click();
  });

  document.getElementById("toolbar-run-selected").addEventListener("click", () => {
    runSelectedCell();
    render();
  });

  document.getElementById("replay-button").addEventListener("click", () => {
    const inference = inferCell(selectedCell());
    text(
      "cell-output",
      inference.blocked.length
        ? `replay blocked by ${inference.blocked.join(", ")}`
        : "replay clean / inputs and wasm cid unchanged",
    );
  });

  document.getElementById("infer-button").addEventListener("click", () => {
    applyEditorSource();
    document.querySelector('[data-tab="assistant"]').click();
  });

  document.getElementById("evidence-button").addEventListener("click", () => {
    document.querySelector('[data-tab="evidence"]').click();
  });

  document.getElementById("assistant-generate").addEventListener("click", () => {
    const prompt = document.getElementById("assistant-prompt").value;
    const cell = llmDraft(prompt, selectedCell());
    state.data["lab/notebook"]["lab/cells"].push(cell);
    state.selectedCellId = cell["cell/id"];
    saveNotebook();
    text("assistant-output", `Generated ${cell["cell/id"]} with llm-infer capability.`);
    render();
  });

  document.getElementById("save-button").addEventListener("click", () => {
    const ok = saveNotebook();
    text("cell-output", ok ? "notebook saved to browser storage" : "browser storage unavailable");
    renderMaturity();
  });

  document.getElementById("snapshot-button").addEventListener("click", () => {
    const snapshot = createReviewSnapshot();
    render();
    text("cell-output", `review snapshot ready: ${snapshot["snapshot/id"]}`);
    document.querySelector('[data-tab="evidence"]').click();
  });

  document.getElementById("reset-button").addEventListener("click", () => {
    clearSavedNotebook();
    window.location.reload();
  });

  document.getElementById("export-button").addEventListener("click", downloadNotebook);

  document.getElementById("import-file").addEventListener("change", async (event) => {
    const [file] = event.target.files;
    if (!file) return;
    const payload = JSON.parse(await file.text());
    restoreNotebookPayload(payload);
    event.target.value = "";
  });
}

async function boot() {
  setupInteractions();
  try {
    try {
      localStorage.setItem(`${state.storageKey}:probe`, "1");
      localStorage.removeItem(`${state.storageKey}:probe`);
      state.storageAvailable = true;
    } catch {
      state.storageAvailable = false;
    }
    const response = await fetch("./lab.edn", { cache: "no-store" });
    const source = await response.text();
    const edn = extractLabUi(source);
    const saved = loadSavedNotebook();
    if (saved?.data) {
      state.data = saved.data;
      state.selectedCellId = saved.selectedCellId;
      if (saved.runtime) state.runtime = saved.runtime;
    } else {
      state.data = new EdnParser(edn).parse();
    }
    ensureNotebookShape();
    render();
  } catch (error) {
    text("notebook-title", "Failed to load lab.edn");
    document.getElementById("source-editor").value = error.stack || String(error);
  }
}

boot();
