/**
 * LLM Model Registry — Single Source of Truth.
 *
 * All model IDs, CF Workers AI mappings, availability, and use-case defaults
 * are defined here. No other file in the repo should hardcode model strings.
 */
import type { ModelDef, UseCaseName } from "./llm-model-types.js";

/** Canonical model registry. Add/remove/update models here only. */
export const MODEL_REGISTRY: Record<string, ModelDef> = {
  // ── Maxwell — etzhayyim default LLM weight (ADR-2606061000) ──────────────
  // Charter-aligned instruction fine-tune of Gemma 4 E4B, served Murakumo-only
  // (Ollama `maxwell-1` slot + LiteLLM 127.0.0.1:4000 + EVO-X2 LAN per ADR-2605215000).
  // Server/fleet tier — NOT the edge tier (that is baien; edge invariant ADR-2605241900).
  // R0: available=false until a real fine-tune clears the microbench gate
  // (≥250 SGD steps OR ≥+5pp on `e7m bench micro`, recorded in maxwell-models.jsonl).
  // Until then USE_CASE_DEFAULTS keep resolving to gemma-4-e4b-it and resolveModelId
  // fails open to it (an unavailable maxwell-1 never breaks routing — see ADR-2606061000 D3).
  "maxwell-1": {
    cfModel: "huggingface:etzhayyim/maxwell-1-gemma4-e4b",
    huggingfaceModel: "etzhayyim/maxwell-1-gemma4-e4b",
    maxTokens: 4096,
    contextWindow: 128000,
    // Inherits the full gemma-4-e4b-it default use-case set; becomes the resolved
    // target for these at M1 when available flips true (ADR-2606061000 D3).
    useCases: ["heartbeat", "shinka", "react", "general", "simple", "social", "convo", "japanese", "structured"],
    available: false,
    ollamaModel: "maxwell-1",
  },
  // Tier 0: Gemma 4 E4B — best Gemma4 for Mac Mini M4 16GB (murakumo fleet default)
  "gemma-4-e4b-it": {
    cfModel: "@cf/google/gemma-4-e4b-it",
    maxTokens: 4096,
    contextWindow: 128000,
    useCases: ["heartbeat", "shinka", "react", "general", "simple", "social", "convo", "japanese", "structured"],
    available: true,
    // gemma4:e4b ~6 GiB VRAM, 128K context, 4B effective params (MoE larger model).
    // Best Gemma4 for Mac Mini M4 16GB — fits comfortably, better quality than e2b.
    // Runs on all 10 fleet nodes as tier0-structured; now also tier0-general.
    ollamaModel: "gemma4:e4b",
  },
  // Tier 0 GPU burst: routed by LiteLLM to RunPod Gemma4.
  "gemma4-runpod": {
    cfModel: "openai/gemma-4-e4b-it",
    maxTokens: 8192,
    contextWindow: 128000,
    useCases: ["general", "structured", "japanese", "json", "extraction"],
    available: true,
    ollamaModel: "gemma4:26b-a4b-it-q4_K_M",
  },
  "tier0-runpod": {
    cfModel: "openai/gemma-4-e4b-it",
    maxTokens: 8192,
    contextWindow: 128000,
    useCases: ["general", "structured", "japanese", "json", "extraction"],
    available: true,
    ollamaModel: "gemma4:26b-a4b-it-q4_K_M",
  },
  // Tier 0 fallback: Gemma 4 E2B (lightweight, 2B — fast cold path / fallback)
  "gemma-4-e2b-it": {
    cfModel: "@cf/google/gemma-4-e2b-it",
    maxTokens: 4096,
    contextWindow: 128000,
    useCases: [],
    available: true,
    // gemma4:e2b ~4 GiB VRAM, 128K context. Fast fallback when e4b slots are full.
    ollamaModel: "gemma4:e2b",
  },
  // Tier 1: Qwen3 MoE (30B total, 3B active — lightweight, fast)
  "qwen3-30b": {
    cfModel: "@cf/qwen/qwen3-30b-a3b-fp8",
    maxTokens: 4096,
    contextWindow: 32768,
    useCases: ["kyumei-koji", "extraction", "json"],
    available: true,
    // Fleet alternative: gemma4:e4b (dedicated entry above).
    ollamaModel: "gemma4:e4b",
  },
  // Tier 2: Qwen2.5-Coder (structured output, extraction)
  "qwen2.5-coder-32b": {
    cfModel: "@cf/qwen/qwen2.5-coder-32b-instruct",
    maxTokens: 8192,
    contextWindow: 32768,
    useCases: ["kyumei-koji", "extraction", "json", "structured"],
    available: false, // CF Workers AI returns "model not available" as of 2026-04-08
  },
  // Tier 3: QwQ (reasoning, validation)
  "qwq-32b": {
    cfModel: "@cf/qwen/qwq-32b",
    maxTokens: 8192,
    contextWindow: 32768,
    useCases: ["kyumei-koji-validate", "reasoning", "validation", "complex"],
    available: true,
  },
  // Tier 4: Convo (large, tool calling)
  "llama-3.3-70b": {
    cfModel: "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    maxTokens: 4096,
    contextWindow: 8192,
    useCases: ["convo", "analysis"],
    available: true,
  },
  // Tier 5: Multilingual (Gemma 3 12B)
  "gemma-3-12b": {
    cfModel: "@cf/google/gemma-3-12b-it",
    maxTokens: 4096,
    contextWindow: 8192,
    useCases: ["translation", "i18n", "multilingual"],
    available: true,
  },
  // Training trunk: Gemma 4 E4B base (non-instruct) for the H100 training pod
  // (ADR 2605092345). Loaded by `kotodama.primitives.training_run` on the
  // training-only H100 pod; inference is unaffected and continues on the
  // RunPod 6000 Ada pool (ADR-2605010000).
  "gemma-4-e4b-base": {
    cfModel: "huggingface:google/gemma-4-E4B",
    huggingfaceModel: "google/gemma-4-E4B",
    maxTokens: 4096,
    contextWindow: 128000,
    useCases: ["training-base"],
    available: true,
  },
  // DeepSeek Pro V4 — routed via llm.etzhayyim.com → OpenRouter (ADR-2605120000, SES extraction).
  // cfModel is the OpenRouter path forwarded by the LiteLLM gateway at llm.etzhayyim.com.
  "deepseek-pro-v4": {
    cfModel: "deepseek/deepseek-chat",
    maxTokens: 8192,
    contextWindow: 131072,
    useCases: ["ses-extraction", "extraction", "json", "structured"],
    available: true,
  },
  // Baien (ADR 2605092350) — 1.58-bit BitNet trunk for edge / browser / CPU
  // on-device inference. Sibling to Oka (FP8 server-side trunk). bf16
  // checkpoint is the master used for fine-tunes; runtime kernels (bitnet.cpp,
  // WebGPU, llama.cpp BitNet) consume the i2_s ternary blob derived from it.
  "baien-bitnet-1.58bit-base": {
    cfModel: "huggingface:microsoft/bitnet-b1.58-2B-4T-bf16",
    huggingfaceModel: "microsoft/bitnet-b1.58-2B-4T-bf16",
    maxTokens: 2048,
    contextWindow: 4096,
    useCases: ["edge", "browser", "cpu"],
    available: true,
  },
};

/** Use-case → default model mapping. */
export const USE_CASE_DEFAULTS: Record<UseCaseName, string> = {
  heartbeat: "gemma-4-e4b-it",
  shinka: "gemma-4-e4b-it",
  react: "gemma-4-e4b-it",
  "kyumei-koji": "qwen3-30b",
  "kyumei-koji-validate": "qwq-32b",
  general: "gemma-4-e4b-it",
  simple: "gemma-4-e4b-it",
  social: "gemma-4-e4b-it",
  japanese: "gemma-4-e4b-it",
  extraction: "qwen3-30b",
  json: "qwen3-30b",
  structured: "gemma-4-e4b-it",
  reasoning: "qwq-32b",
  validation: "qwq-32b",
  complex: "qwq-32b",
  convo: "gemma-4-e4b-it",
  analysis: "llama-3.3-70b",
  translation: "gemma-3-12b",
  i18n: "gemma-3-12b",
  multilingual: "gemma-3-12b",
  "training-base": "gemma-4-e4b-base",
  edge: "baien-bitnet-1.58bit-base",
  browser: "baien-bitnet-1.58bit-base",
  cpu: "baien-bitnet-1.58bit-base",
  "ses-extraction": "deepseek-pro-v4",
};

/**
 * LLM SSoT default model alias (ADR-2605010000).
 * Despite the legacy name, this constant resolves to the **RunPod-served default
 * model alias** (gemma-4-26B-A4B-it FP8) accessed via `https://llm.etzhayyim.com/v1/chat/completions`.
 * Murakumo は LLM 推論経路として想定しない。Rename は破壊的変更のため deferred — 意味は ADR で再定義。
 */
export const MURAKUMO_DEFAULT_MODEL = "gemma-4-e4b-it";

/**
 * Maxwell — etzhayyim's named default LLM weight (ADR-2606061000).
 * A Charter-aligned instruction fine-tune of Gemma 4 E4B, served Murakumo-only.
 * This constant is the SSoT for "the religious-corp default weight" — reference it
 * instead of hardcoding the `"maxwell"` string anywhere (gate G5).
 *
 * R0 flip path (ADR-2606061000 D3): until Maxwell weights exist and pass the
 * microbench gate, `maxwell-1` is registered with `available: false`, so
 * `USE_CASE_DEFAULTS` and `MURAKUMO_DEFAULT_MODEL` keep resolving to
 * `gemma-4-e4b-it` and `resolveModelId` fails open to it. At M1 the default
 * use-cases flip from `"gemma-4-e4b-it"` to `MAXWELL_DEFAULT_WEIGHT`.
 */
export const MAXWELL_DEFAULT_WEIGHT = "maxwell-1";

/**
 * Default Hugging Face base-model ID for the H100 training pod
 * (ADR 2605092345). Trainers (`kotodama.primitives.training_run`,
 * Unsloth runner, distill teacher loader) read this when the lexicon
 * input does not pin a `baseModel`. Training-only — inference paths
 * resolve via `MURAKUMO_DEFAULT_MODEL` instead.
 */
export const TRAINING_DEFAULT_BASE_MODEL = "google/gemma-4-E4B";

/**
 * Default 1.58-bit edge / browser / CPU trunk (ADR 2605092350, Baien).
 * Read by on-device inference paths (bitnet.cpp pod fallback, WebGPU /
 * WASM browser bundle, llama.cpp BitNet kernel). Distinct from Oka — do
 * not collapse the two SSoTs.
 */
export const BAIEN_DEFAULT_TRUNK_MODEL = "microsoft/bitnet-b1.58-2B-4T-bf16";

/** Model alias map for backward compatibility. */
export const MODEL_ALIASES: Record<string, string> = {
  // Maxwell — default weight (ADR-2606061000)
  "maxwell": "maxwell-1",
  "etzhayyim/maxwell-1-gemma4-e4b": "maxwell-1",
  "gemma-3-12b-it": "gemma-3-12b",
  "@cf/google/gemma-3-12b-it": "gemma-3-12b",
  "gemma-4-e2b": "gemma-4-e2b-it",
  "@cf/google/gemma-4-e2b-it": "gemma-4-e2b-it",
  "gemma-4-e4b": "gemma-4-e4b-it",
  "@cf/google/gemma-4-e4b-it": "gemma-4-e4b-it",
  "qwen3.5-4b": "qwen3-30b",
  "qwen3.5-4b-instruct": "qwen3-30b",
  "qwen3.5-9b": "qwen3-30b",
  "qwen3.5-9b-instruct": "qwen3-30b",
};

/**
 * Resolve a model hint + optional use-case to a canonical model ID.
 * Falls back to available models if the requested one is unavailable.
 */
export function resolveModelId(hint?: string, useCase?: string): string {
  // 1. Try hint directly
  if (hint) {
    const trimmed = hint.trim();
    if (MODEL_REGISTRY[trimmed]?.available) return trimmed;
    const aliased = MODEL_ALIASES[trimmed.toLowerCase()];
    if (aliased && MODEL_REGISTRY[aliased]?.available) return aliased;
    // Try matching by cfModel
    for (const [id, def] of Object.entries(MODEL_REGISTRY)) {
      if (def.cfModel.toLowerCase() === trimmed.toLowerCase() && def.available) return id;
    }
    // Hint exists in registry but unavailable — fall through to use-case
    if (MODEL_REGISTRY[trimmed] && !MODEL_REGISTRY[trimmed].available) {
      console.warn(`[llm-models] model "${trimmed}" is unavailable, falling back to use-case default`);
    }
  }
  // 2. Try use-case default
  if (useCase) {
    const ucModel = USE_CASE_DEFAULTS[useCase as UseCaseName];
    if (ucModel && MODEL_REGISTRY[ucModel]?.available) return ucModel;
  }
  // 3. Fallback to gemma-4-e4b-it
  return "gemma-4-e4b-it";
}

/** Resolve to a full ModelDef. Never returns undefined. */
export function resolveModel(hint?: string, useCase?: string): ModelDef {
  const id = resolveModelId(hint, useCase);
  return MODEL_REGISTRY[id] ?? MODEL_REGISTRY["gemma-4-e4b-it"];
}

/** Check if a model ID is known (regardless of availability). */
export function isKnownModel(id: string): boolean {
  return id in MODEL_REGISTRY || id.toLowerCase() in MODEL_ALIASES;
}
