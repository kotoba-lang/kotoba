import { z, type ZodObject } from "zod";

export interface HuggingfaceHandle {
  search_models(input: HuggingfaceSearchModelsInput): Promise<HuggingfaceSearchModelsOutput>;
  search_datasets(input: HuggingfaceSearchDatasetsInput): Promise<HuggingfaceSearchDatasetsOutput>;
}

// ── searchModels ─────────────────────────────────────────────────────────
export const search_modelsInputSchema = z.object({
    search: z.string().max(512).describe("Free-text query.").optional(),
    author: z.string().max(128).describe("Filter by author/organization.").optional(),
    filter: z.string().max(256).describe("Tag filter (e.g. `pytorch`, `text-generation`).").optional(),
    sort: z.enum(["downloads", "likes", "lastModified"] as [string, ...string[]]).describe("Sort key.").optional(),
    direction: z.enum(["-1", "1"] as [string, ...string[]]).describe("Sort direction (-1 desc, 1 asc).").optional(),
    limit: z.number().int().min(1).max(1000).default(10).describe("Maximum number of results.").optional(),
});
export type HuggingfaceSearchModelsInput = z.infer<typeof search_modelsInputSchema>;

export interface HuggingfaceSearchModelsOutput {
  httpStatus: number;
  json?: unknown;
  body?: string;
  error?: string;
}

// ── searchDatasets ─────────────────────────────────────────────────────────
export const search_datasetsInputSchema = z.object({
    search: z.string().max(512).optional(),
    filter: z.string().max(256).optional(),
    limit: z.number().int().min(1).max(1000).default(10).optional(),
});
export type HuggingfaceSearchDatasetsInput = z.infer<typeof search_datasetsInputSchema>;

export interface HuggingfaceSearchDatasetsOutput {
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
  invoke: (handle: HuggingfaceHandle, input: unknown) => Promise<unknown>;
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
    name: "search_models",
    title: "Search HuggingFace Hub models",
    description: "List models with optional free-text search, author filter, and sort. Returns a JSON array of model summaries.",
    inputSchema: search_modelsInputSchema,
    jsonSchema: zodToJsonSchemaShim(search_modelsInputSchema),
    invoke: async (handle, input) => handle.search_models(input as HuggingfaceSearchModelsInput),
  },
  {
    name: "search_datasets",
    title: "Search HuggingFace Hub datasets",
    description: "List datasets with optional free-text search and tag filter.",
    inputSchema: search_datasetsInputSchema,
    jsonSchema: zodToJsonSchemaShim(search_datasetsInputSchema),
    invoke: async (handle, input) => handle.search_datasets(input as HuggingfaceSearchDatasetsInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
