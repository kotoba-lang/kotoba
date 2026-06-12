import { z, type ZodObject } from "zod";

export interface ArgparseDemoHandle {
  main(input: ArgparseDemoMainInput): Promise<ArgparseDemoMainOutput>;
}

// ── main ─────────────────────────────────────────────────────────
export const mainInputSchema = z.object({
    source_path: z.string().describe("Path to read from."),
    output_path: z.string().default("-").describe("Output path; '-' for stdout.").optional(),
    max_rows: z.number().int().default(100).describe("Maximum rows to emit.").optional(),
    encoding: z.string().default("utf-8").describe("Output encoding.").optional(),
    verbose: z.boolean().describe("Enable verbose logging.").optional(),
    dry_run: z.boolean().describe("Plan without writing.").optional(),
});
export type ArgparseDemoMainInput = z.infer<typeof mainInputSchema>;

export interface ArgparseDemoMainOutput {
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
  invoke: (handle: ArgparseDemoHandle, input: unknown) => Promise<unknown>;
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
    name: "main",
    title: "Demo argparse CLI used by the yorishiro source-repo fixture.",
    description: "Demo argparse CLI used by the yorishiro source-repo fixture.",
    inputSchema: mainInputSchema,
    jsonSchema: zodToJsonSchemaShim(mainInputSchema),
    invoke: async (handle, input) => handle.main(input as ArgparseDemoMainInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
