import { z, type ZodObject } from "zod";

export interface BlsHandle {
  fetch_timeseries(input: BlsFetchTimeseriesInput): Promise<BlsFetchTimeseriesOutput>;
}

// ── fetchTimeseries ─────────────────────────────────────────────────────────
export const fetch_timeseriesInputSchema = z.object({
    seriesid: z.array(z.string().min(1).max(64)).describe("BLS series ids (e.g. `CES0000000001`, `LNS14000000`)."),
    startyear: z.string().describe("Inclusive lower bound (4-digit year, string form per BLS contract).").optional(),
    endyear: z.string().describe("Inclusive upper bound.").optional(),
    registrationkey: z.string().describe("Optional BLS API registration key (extends quota).").optional(),
    catalog: z.boolean().describe("If true, includes series metadata catalog in the response.").optional(),
    calculations: z.boolean().describe("If true, includes 1/3/6/12-month percent change calculations.").optional(),
    annualaverage: z.boolean().describe("If true, includes annual averages.").optional(),
});
export type BlsFetchTimeseriesInput = z.infer<typeof fetch_timeseriesInputSchema>;

export interface BlsFetchTimeseriesOutput {
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
  invoke: (handle: BlsHandle, input: unknown) => Promise<unknown>;
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
    name: "fetch_timeseries",
    title: "Fetch BLS timeseries data",
    description: "POST a list of BLS series ids and an inclusive year range. Returns the requested observations keyed by series id under `Results.series[]`. Unauthenticated calls are rate-limited to 25/day per IP and to a 10-year max range; authenticated calls (with `registrationkey`) extend to 500/day and 20 years.",
    inputSchema: fetch_timeseriesInputSchema,
    jsonSchema: zodToJsonSchemaShim(fetch_timeseriesInputSchema),
    invoke: async (handle, input) => handle.fetch_timeseries(input as BlsFetchTimeseriesInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
