import { z, type ZodObject } from "zod";

export interface CrossrefHandle {
  search_works(input: CrossrefSearchWorksInput): Promise<CrossrefSearchWorksOutput>;
  get_work_by_doi(input: CrossrefGetWorkByDoiInput): Promise<CrossrefGetWorkByDoiOutput>;
}

// ── searchWorks ─────────────────────────────────────────────────────────
export const search_worksInputSchema = z.object({
    query: z.string().max(1024).describe("Free-text query.").optional(),
    rows: z.number().int().min(1).max(1000).default(20).describe("Page size.").optional(),
    offset: z.number().int().min(0).default(0).describe("Result offset for paging.").optional(),
});
export type CrossrefSearchWorksInput = z.infer<typeof search_worksInputSchema>;

export interface CrossrefSearchWorksOutput {
  httpStatus: number;
  json?: unknown;
  body?: string;
  error?: string;
}

// ── getWorkByDoi ─────────────────────────────────────────────────────────
export const get_work_by_doiInputSchema = z.object({
    doi: z.string().min(4).max(256).describe("DOI string, e.g. `10.1038/nature12373`."),
});
export type CrossrefGetWorkByDoiInput = z.infer<typeof get_work_by_doiInputSchema>;

export interface CrossrefGetWorkByDoiOutput {
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
  invoke: (handle: CrossrefHandle, input: unknown) => Promise<unknown>;
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
    name: "search_works",
    title: "Search Crossref works",
    description: "Free-text + structured query over the Crossref works index.",
    inputSchema: search_worksInputSchema,
    jsonSchema: zodToJsonSchemaShim(search_worksInputSchema),
    invoke: async (handle, input) => handle.search_works(input as CrossrefSearchWorksInput),
  },
  {
    name: "get_work_by_doi",
    title: "Get a Crossref work by DOI",
    description: "Fetch a single work record by its DOI.",
    inputSchema: get_work_by_doiInputSchema,
    jsonSchema: zodToJsonSchemaShim(get_work_by_doiInputSchema),
    invoke: async (handle, input) => handle.get_work_by_doi(input as CrossrefGetWorkByDoiInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
