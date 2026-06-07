import { z, type ZodObject } from "zod";

export interface FueleconomyHandle {
  download_vehicles_csv(input: FueleconomyDownloadVehiclesCsvInput): Promise<FueleconomyDownloadVehiclesCsvOutput>;
}

// ── downloadVehiclesCsv ─────────────────────────────────────────────────────────
export const download_vehicles_csvInputSchema = z.object({
  // (no input fields)
});
export type FueleconomyDownloadVehiclesCsvInput = z.infer<typeof download_vehicles_csvInputSchema>;

export interface FueleconomyDownloadVehiclesCsvOutput {
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
  invoke: (handle: FueleconomyHandle, input: unknown) => Promise<unknown>;
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
    name: "download_vehicles_csv",
    title: "Download the full EPA vehicles dataset as CSV",
    description: "GETs the canonical EPA vehicle fuel economy CSV. Body is returned verbatim — the caller cell parses it via stdlib csv. Multi-megabyte payload (~40 MB at time of authoring); set caller timeouts accordingly.",
    inputSchema: download_vehicles_csvInputSchema,
    jsonSchema: zodToJsonSchemaShim(download_vehicles_csvInputSchema),
    invoke: async (handle, input) => handle.download_vehicles_csv(input as FueleconomyDownloadVehiclesCsvInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
