(function () {
  function extractTask(source) {
    const match = source.match(/:task\s+"([^"]+)"/);
    return match ? match[1] : "summarize evidence";
  }

  function hash(input) {
    let value = 2166136261;
    for (let i = 0; i < input.length; i += 1) {
      value ^= input.charCodeAt(i);
      value = Math.imul(value, 16777619);
    }
    return (value >>> 0).toString(16).padStart(8, "0");
  }

  window.KotobaLLMProvider = {
    id: "kotoba-research-assistant",
    version: "shim-0.1.0",
    status: "available",
    capability: "llm-infer",

    infer({ cell, evidence, budget }) {
      const source = cell["cell/source"] || "";
      const task = extractTask(source);
      const support = (evidence?.["evidence/output-cids"] || []).join(", ") || "current notebook evidence";
      const claimId = `claim-${hash(`${cell["cell/id"]}:${task}:${support}`)}`;
      return {
        claimId,
        text: `Draft ${claimId}: ${task}. Supported by ${support}.`,
        citationsRequired: true,
        budget: budget || { maxTokens: 512, maxCostUsd: 0 },
        diagnostics: [
          "llm-infer shim generated deterministic research draft",
          "real provider adapter can replace this API without changing Kotoba cell source",
        ],
      };
    },
  };
})();
