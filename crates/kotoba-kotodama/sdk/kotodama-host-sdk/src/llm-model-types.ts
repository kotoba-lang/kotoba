/**
 * LLM model definition — maps a model ID to its CF Workers AI identifier and constraints.
 */
export interface ModelDef {
  /** Cloudflare Workers AI model identifier (e.g. "@cf/qwen/qwen3-30b-a3b-fp8"). */
  cfModel: string;
  /** Maximum output tokens. */
  maxTokens: number;
  /** Maximum context window tokens. */
  contextWindow: number;
  /** Use cases this model is suitable for. */
  useCases: UseCaseName[];
  /** Whether this model is currently available on CF Workers AI. */
  available: boolean;
  /** Ollama model tag for self-hosted GPU pod inference (e.g. "gemma4:2b-it-q4_K_M"). */
  ollamaModel?: string;
  /**
   * Hugging Face model ID for training base loads (e.g. "google/gemma-4-E4B")
   * or for edge/browser/CPU runtimes that pull weights from HF
   * (e.g. "microsoft/bitnet-b1.58-2B-4T-bf16"). Inference paths that go
   * through CF Workers AI / RunPod ignore this field.
   */
  huggingfaceModel?: string;
}

/** Known use-case identifiers for model routing. */
export type UseCaseName =
  | "heartbeat"
  | "shinka"
  | "react"
  | "kyumei-koji"
  | "kyumei-koji-validate"
  | "general"
  | "simple"
  | "social"
  | "japanese"
  | "extraction"
  | "json"
  | "structured"
  | "reasoning"
  | "validation"
  | "complex"
  | "convo"
  | "analysis"
  | "translation"
  | "i18n"
  | "multilingual"
  // Oka (ADR 2605092345) — FP8 H100 trainer + 6000 Ada inference.
  | "training-base"
  // Baien (ADR 2605092350) — 1.58-bit BitNet trunk for on-device inference.
  | "edge"
  | "browser"
  | "cpu"
  // SES案件 ingest extraction (ADR-2605120000).
  | "ses-extraction";
