import { z, type ZodObject } from "zod";

export interface ExamplePortalHandle {
  read_heading(input: ExamplePortalReadHeadingInput): Promise<ExamplePortalReadHeadingOutput>;
  search_term(input: ExamplePortalSearchTermInput): Promise<ExamplePortalSearchTermOutput>;
}

// ── readHeading ─────────────────────────────────────────────────────────
export const read_headingInputSchema = z.object({
  // (no input fields — pure-extract op)
});
export type ExamplePortalReadHeadingInput = z.infer<typeof read_headingInputSchema>;

export interface ExamplePortalReadHeadingOutput {
  ok: boolean;
  error?: string;
  heading?: string;
}

// ── searchTerm ─────────────────────────────────────────────────────────
export const search_termInputSchema = z.object({
    query: z.string(),
});
export type ExamplePortalSearchTermInput = z.infer<typeof search_termInputSchema>;

export interface ExamplePortalSearchTermOutput {
  ok: boolean;
  error?: string;
  result_titles?: string[];
  result_count_label?: string;
}


export interface ToolDefinition {
  name: string;
  title: string;
  description: string;
  inputSchema: ZodObject<Record<string, z.ZodTypeAny>>;
  jsonSchema: unknown;
  invoke: (handle: ExamplePortalHandle, input: unknown) => Promise<unknown>;
}

function zodToJsonSchemaShim(schema: ZodObject<Record<string, z.ZodTypeAny>>): unknown {
  const shape = (schema as unknown as { shape: Record<string, z.ZodTypeAny> }).shape;
  const props: Record<string, unknown> = {};
  const required: string[] = [];
  for (const [k, v] of Object.entries(shape)) {
    const def = (v as unknown as { _def: { typeName?: string } })._def;
    const t = (def?.typeName ?? "").replace(/^Zod/, "").toLowerCase();
    props[k] = { type: t === "boolean" ? "boolean" : t === "number" || t === "bigint" ? "number" : "string" };
    if (!(v as unknown as { isOptional?: () => boolean }).isOptional?.()) required.push(k);
  }
  return { type: "object", properties: props, required };
}

export const tools: ToolDefinition[] = [
  {
    name: "read_heading",
    title: "Read the H1 heading from example.com",
    description: "Navigates to the kami's base URL, waits for the H1 to render, and extracts its textContent. Exists as the minimum L1 demonstration for browser-only mode.",
    inputSchema: read_headingInputSchema,
    jsonSchema: zodToJsonSchemaShim(read_headingInputSchema),
    invoke: async (handle, input) => handle.read_heading(input as ExamplePortalReadHeadingInput),
  },
  {
    name: "search_term",
    title: "Fill a hypothetical search input on the portal and read results",
    description: "Hypothetical flow exercising fill + click + scroll + multi-extract — the page itself does NOT have a real search box, but the kami manifest is shaped this way to validate the L1 emitter's required-input derivation.",
    inputSchema: search_termInputSchema,
    jsonSchema: zodToJsonSchemaShim(search_termInputSchema),
    invoke: async (handle, input) => handle.search_term(input as ExamplePortalSearchTermInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
