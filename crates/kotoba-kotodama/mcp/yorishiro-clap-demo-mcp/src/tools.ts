import { z, type ZodObject } from "zod";

export interface ClapDemoHandle {
  clap_demo(input: ClapDemoClapDemoInput): Promise<ClapDemoClapDemoOutput>;
}

// ── clap-demo ─────────────────────────────────────────────────────────
export const clap_demoInputSchema = z.object({
    input_path: z.string().describe("Source path to read."),
    output_path: z.string().describe("Output path; '-' for stdout.").optional(),
    max_rows: z.number().int().default(100).describe("Maximum rows to emit.").optional(),
    encoding: z.string().default("utf-8").describe("Output encoding.").optional(),
    verbose: z.boolean().describe("Enable verbose logging.").optional(),
});
export type ClapDemoClapDemoInput = z.infer<typeof clap_demoInputSchema>;

export interface ClapDemoClapDemoOutput {
  exitCode: number;
  stdout?: string;
  stderr?: string;
  error?: string;
}


export interface ToolDefinition {
  name: string;
  title: string;
  description: string;
  inputSchema: ZodObject<Record<string, z.ZodTypeAny>>;
  jsonSchema: unknown;
  invoke: (handle: ClapDemoHandle, input: unknown) => Promise<unknown>;
}

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
              : "string",
    };
    if (!(v as unknown as { isOptional?: () => boolean }).isOptional?.()) required.push(k);
  }
  return { type: "object", properties: props, required };
}

export const tools: ToolDefinition[] = [
  {
    name: "clap_demo",
    title: "Demo clap CLI used by the yorishiro source-repo fixture.",
    description: "Longer description of the clap demo CLI for the source-repo extractor.",
    inputSchema: clap_demoInputSchema,
    jsonSchema: zodToJsonSchemaShim(clap_demoInputSchema),
    invoke: async (handle, input) => handle.clap_demo(input as ClapDemoClapDemoInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
