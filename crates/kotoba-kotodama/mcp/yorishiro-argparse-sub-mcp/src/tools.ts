import { z, type ZodObject } from "zod";

export interface ArgparseSubHandle {
  encode(input: ArgparseSubEncodeInput): Promise<ArgparseSubEncodeOutput>;
  decode(input: ArgparseSubDecodeInput): Promise<ArgparseSubDecodeOutput>;
  inspect(input: ArgparseSubInspectInput): Promise<ArgparseSubInspectOutput>;
}

// ── encode ─────────────────────────────────────────────────────────
export const encodeInputSchema = z.object({
    verbose: z.boolean().describe("Enable verbose logging across all subcommands.").optional(),
    config: z.string().default("/etc/sub.conf").describe("Path to config file.").optional(),
    input_path: z.string().describe("Source path."),
    output: z.string().default("-").describe("Output file; '-' for stdout.").optional(),
    bitrate: z.number().int().default(128).describe("Output bitrate (kbps).").optional(),
    lossless: z.boolean().describe("Use lossless encoding.").optional(),
});
export type ArgparseSubEncodeInput = z.infer<typeof encodeInputSchema>;

export interface ArgparseSubEncodeOutput {
  exitCode: number;
  stdout?: string;
  stderr?: string;
  error?: string;
}

// ── decode ─────────────────────────────────────────────────────────
export const decodeInputSchema = z.object({
    verbose: z.boolean().describe("Enable verbose logging across all subcommands.").optional(),
    config: z.string().default("/etc/sub.conf").describe("Path to config file.").optional(),
    input_path: z.string().describe("Source path."),
    output_path: z.string().default("-").describe("Output file; '-' for stdout.").optional(),
    sample_rate: z.number().int().default(44100).describe("Sample rate (Hz).").optional(),
});
export type ArgparseSubDecodeInput = z.infer<typeof decodeInputSchema>;

export interface ArgparseSubDecodeOutput {
  exitCode: number;
  stdout?: string;
  stderr?: string;
  error?: string;
}

// ── inspect ─────────────────────────────────────────────────────────
export const inspectInputSchema = z.object({
    verbose: z.boolean().describe("Enable verbose logging across all subcommands.").optional(),
    config: z.string().default("/etc/sub.conf").describe("Path to config file.").optional(),
    input_path: z.string().describe("Source path."),
});
export type ArgparseSubInspectInput = z.infer<typeof inspectInputSchema>;

export interface ArgparseSubInspectOutput {
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
  invoke: (handle: ArgparseSubHandle, input: unknown) => Promise<unknown>;
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
    name: "encode",
    title: "Encode an input file.",
    description: "Encode an input file.",
    inputSchema: encodeInputSchema,
    jsonSchema: zodToJsonSchemaShim(encodeInputSchema),
    invoke: async (handle, input) => handle.encode(input as ArgparseSubEncodeInput),
  },
  {
    name: "decode",
    title: "Decode an input file.",
    description: "Decode an input file.",
    inputSchema: decodeInputSchema,
    jsonSchema: zodToJsonSchemaShim(decodeInputSchema),
    invoke: async (handle, input) => handle.decode(input as ArgparseSubDecodeInput),
  },
  {
    name: "inspect",
    title: "Print metadata only.",
    description: "Print metadata only.",
    inputSchema: inspectInputSchema,
    jsonSchema: zodToJsonSchemaShim(inspectInputSchema),
    invoke: async (handle, input) => handle.inspect(input as ArgparseSubInspectInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
