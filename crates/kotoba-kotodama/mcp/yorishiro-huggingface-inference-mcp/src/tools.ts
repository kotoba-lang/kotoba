import { z, type ZodObject } from "zod";

export interface HuggingfaceInferenceHandle {
  extract_features(input: HuggingfaceInferenceExtractFeaturesInput): Promise<HuggingfaceInferenceExtractFeaturesOutput>;
}

// ── extractFeatures ─────────────────────────────────────────────────────────
export const extract_featuresInputSchema = z.object({
    model_id: z.string().min(3).max(256).describe("Model id on the Hub (e.g. `sentence-transformers/all-MiniLM-L6-v2`)."),
    inputs: z.string().min(1).max(32768).describe("Text to embed (single string or batched). Phase 1: single only."),
    wait_for_model: z.boolean().default(true).describe("Wait for cold-start instead of returning 503.").optional(),
});
export type HuggingfaceInferenceExtractFeaturesInput = z.infer<typeof extract_featuresInputSchema>;

export interface HuggingfaceInferenceExtractFeaturesOutput {
  httpStatus: number;
  json?: unknown;
  body?: string;
  error?: string;
}


export interface ToolDefinition {
  name: string;
  title: string;
  description: string;
  inputSchema: ZodObject<Record<string, z.ZodTypeAny>>;
  jsonSchema: unknown;
  invoke: (handle: HuggingfaceInferenceHandle, input: unknown) => Promise<unknown>;
}

// Minimal zod → JSON Schema shim. MCP hosts only need a coarse "this
// looks like an object with these properties" hint; full conversion
// is intentionally deferred until we add zod-to-json-schema as a
// dependency in Phase 2.
function zodToJsonSchemaShim(schema: ZodObject<Record<string, z.ZodTypeAny>>): unknown {
  const shape = (schema as unknown as { shape: Record<string, z.ZodTypeAny> }).shape;
  const props: Record<string, unknown> = {};
  const required: string[] = [];
  for (const [k, v] of Object.entries(shape)) {
    const def = (v as unknown as { _def: { typeName?: string } })._def;
    const t = (def?.typeName ?? "").replace(/^Zod/, "").toLowerCase();
    props[k] = {
      type:
        t === "string"
          ? "string"
          : t === "number" || t === "bigint"
            ? "number"
            : t === "boolean"
              ? "boolean"
              : t === "array"
                ? "array"
                : "string",
    };
    if (!(v as unknown as { isOptional?: () => boolean }).isOptional?.()) {
      required.push(k);
    }
  }
  return { type: "object", properties: props, required };
}

export const tools: ToolDefinition[] = [
  {
    name: "extract_features",
    title: "Run a feature-extraction (embedding) pipeline against a model",
    description: "POST text to the configured model and receive its hidden-state vector representation. Used by mst-projector embedders. The API key is supplied via Authorization: Bearer <key> by the caller and is NOT part of this lexicon — yorishiri never store credentials.",
    inputSchema: extract_featuresInputSchema,
    jsonSchema: zodToJsonSchemaShim(extract_featuresInputSchema),
    invoke: async (handle, input) => handle.extract_features(input as HuggingfaceInferenceExtractFeaturesInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
