import { z, type ZodObject } from "zod";

export interface ArxivHandle {
  search_papers(input: ArxivSearchPapersInput): Promise<ArxivSearchPapersOutput>;
}

// ── searchPapers ─────────────────────────────────────────────────────────
export const search_papersInputSchema = z.object({
    search_query: z.string().min(1).max(2048).describe("arXiv structured query (e.g. `cat:cs.AI AND ti:transformer`). At least one of `search_query` or `id_list` must be present.").optional(),
    id_list: z.string().max(4096).describe("Comma-separated list of arXiv ids (e.g. `2310.06825,2401.04088`).").optional(),
    start: z.number().int().min(0).default(0).describe("Result offset for paging (0-based).").optional(),
    max_results: z.number().int().min(1).max(2000).default(10).describe("Page size. arXiv caps this near 2000; the public API recommends ≤100 per call.").optional(),
    sortBy: z.enum(["relevance", "lastUpdatedDate", "submittedDate"] as [string, ...string[]]).default("relevance").describe("Sort key.").optional(),
    sortOrder: z.enum(["ascending", "descending"] as [string, ...string[]]).default("descending").describe("Sort direction.").optional(),
});
export type ArxivSearchPapersInput = z.infer<typeof search_papersInputSchema>;

export interface ArxivSearchPapersOutput {
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
  invoke: (handle: ArxivHandle, input: unknown) => Promise<unknown>;
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
    name: "search_papers",
    title: "Search arXiv papers",
    description: "Search arXiv for papers matching a structured query. Returns an Atom 1.0 feed. Either `searchQuery` or `idList` (or both) must be supplied. The Atom XML is returned verbatim — parsing belongs to the caller cell.",
    inputSchema: search_papersInputSchema,
    jsonSchema: zodToJsonSchemaShim(search_papersInputSchema),
    invoke: async (handle, input) => handle.search_papers(input as ArxivSearchPapersInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
