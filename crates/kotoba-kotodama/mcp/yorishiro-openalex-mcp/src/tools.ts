import { z, type ZodObject } from "zod";

export interface OpenalexHandle {
  search_works(input: OpenalexSearchWorksInput): Promise<OpenalexSearchWorksOutput>;
  search_authors(input: OpenalexSearchAuthorsInput): Promise<OpenalexSearchAuthorsOutput>;
}

// ── searchWorks ─────────────────────────────────────────────────────────
export const search_worksInputSchema = z.object({
    search: z.string().max(1024).describe("Free-text query.").optional(),
    filter: z.string().max(2048).describe("OpenAlex filter expression (e.g. `concepts.id:C41008148,publication_year:>2020`).").optional(),
    sort: z.string().max(128).describe("Sort field (e.g. `cited_by_count:desc`).").optional(),
    per_page: z.number().int().min(1).max(200).default(25).describe("Results per page (rename of `per-page` for valid JSON key).").optional(),
    page: z.number().int().min(1).default(1).describe("1-based page index.").optional(),
});
export type OpenalexSearchWorksInput = z.infer<typeof search_worksInputSchema>;

export interface OpenalexSearchWorksOutput {
  httpStatus: number;
  json?: unknown;
  body?: string;
  error?: string;
}

// ── searchAuthors ─────────────────────────────────────────────────────────
export const search_authorsInputSchema = z.object({
    search: z.string().max(1024).optional(),
    filter: z.string().max(2048).optional(),
    per_page: z.number().int().min(1).max(200).default(25).optional(),
    page: z.number().int().min(1).default(1).optional(),
});
export type OpenalexSearchAuthorsInput = z.infer<typeof search_authorsInputSchema>;

export interface OpenalexSearchAuthorsOutput {
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
  invoke: (handle: OpenalexHandle, input: unknown) => Promise<unknown>;
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
    title: "Search OpenAlex works (papers, preprints)",
    description: "Full-text + structured search over the OpenAlex works index.",
    inputSchema: search_worksInputSchema,
    jsonSchema: zodToJsonSchemaShim(search_worksInputSchema),
    invoke: async (handle, input) => handle.search_works(input as OpenalexSearchWorksInput),
  },
  {
    name: "search_authors",
    title: "Search OpenAlex authors",
    description: "Free-text search over the OpenAlex authors index.",
    inputSchema: search_authorsInputSchema,
    jsonSchema: zodToJsonSchemaShim(search_authorsInputSchema),
    invoke: async (handle, input) => handle.search_authors(input as OpenalexSearchAuthorsInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
