import { z, type ZodObject } from "zod";

export interface ArgparseMultiHandle {
  main(input: ArgparseMultiMainInput): Promise<ArgparseMultiMainOutput>;
  main_1(input: ArgparseMultiMain1Input): Promise<ArgparseMultiMain1Output>;
}

// ── main ─────────────────────────────────────────────────────────
export const mainInputSchema = z.object({
    input_path: z.string().describe("Path to encode."),
    bitrate: z.number().int().default(192).describe("kbps.").optional(),
    mono: z.boolean().describe("Force mono output.").optional(),
});
export type ArgparseMultiMainInput = z.infer<typeof mainInputSchema>;

export interface ArgparseMultiMainOutput {
  exitCode: number;
  stdout?: string;
  stderr?: string;
  error?: string;
}

// ── main_1 ─────────────────────────────────────────────────────────
export const main_1InputSchema = z.object({
    input_path: z.string().describe("Path to decode."),
    sample_rate: z.number().int().default(48000).describe("Hz.").optional(),
});
export type ArgparseMultiMain1Input = z.infer<typeof main_1InputSchema>;

export interface ArgparseMultiMain1Output {
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
  invoke: (handle: ArgparseMultiHandle, input: unknown) => Promise<unknown>;
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
    title: "Standalone encoder driver.",
    description: "Standalone encoder driver.",
    inputSchema: mainInputSchema,
    jsonSchema: zodToJsonSchemaShim(mainInputSchema),
    invoke: async (handle, input) => handle.main(input as ArgparseMultiMainInput),
  },
  {
    name: "main_1",
    title: "Standalone decoder driver.",
    description: "Standalone decoder driver.",
    inputSchema: main_1InputSchema,
    jsonSchema: zodToJsonSchemaShim(main_1InputSchema),
    invoke: async (handle, input) => handle.main_1(input as ArgparseMultiMain1Input),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
