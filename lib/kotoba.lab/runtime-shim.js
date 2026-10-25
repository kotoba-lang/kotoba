(function () {
  function hash(input) {
    let value = 2166136261;
    for (let i = 0; i < input.length; i += 1) {
      value ^= input.charCodeAt(i);
      value = Math.imul(value, 16777619);
    }
    return (value >>> 0).toString(16).padStart(8, "0");
  }

  function cid(prefix, input) {
    return `bafy-${prefix}-${hash(input)}`;
  }

  window.KotobaWasmRuntime = {
    id: "kotoba-wasm-safe",
    version: "shim-0.2.0",
    status: "available",
    capabilities: ["safe-build", "deterministic-run", "evidence"],

    compile({ cell, policy }) {
      const source = cell["cell/source"] || "";
      const policyText = JSON.stringify(policy || []);
      return {
        sourceCid: cid("source", source),
        policyCid: cid("policy", policyText),
        wasmCid: cid("wasm", `${cell["cell/id"]}:${source}:${policyText}:shim-0.2.0`),
        diagnostics: [
          "safe-build shim accepted source",
          "real wasm compiler adapter can replace this API without changing the notebook UI",
        ],
      };
    },

    run({ cell, compiled, output }) {
      return {
        outputCid: cid("artifact", `${compiled.wasmCid}:${output}`),
        timingMs: 18 + (cell["cell/source"] || "").length,
        status: "succeeded",
      };
    },
  };
})();
