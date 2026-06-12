import { z, type ZodObject } from "zod";

export interface ClapDeriveDemoHandle {
  encode(input: ClapDeriveDemoEncodeInput): Promise<ClapDeriveDemoEncodeOutput>;
  decode(input: ClapDeriveDemoDecodeInput): Promise<ClapDeriveDemoDecodeOutput>;
}

// ── encode ─────────────────────────────────────────────────────────
export const encodeInputSchema = z.object({
    verbose: z.boolean().describe("Enable verbose logging across all subcommands.").optional(),
    config: z.string().default("/etc/derive.conf").describe("Path to config file.").optional(),
    input_path: z.string(),
    bitrate: z.number().int().default(192).optional(),
    lossless: z.boolean().optional(),
});
export type ClapDeriveDemoEncodeInput = z.infer<typeof encodeInputSchema>;

export interface ClapDeriveDemoEncodeOutput {
  exitCode: number;
  stdout?: string;
  stderr?: string;
  error?: string;
}

// ── decode ─────────────────────────────────────────────────────────
export const decodeInputSchema = z.object({
    verbose: z.boolean().describe("Enable verbose logging across all subcommands.").optional(),
    config: z.string().default("/etc/derive.conf").describe("Path to config file.").optional(),
    input_path: z.string(),
    output_path: z.string().optional(),
    sample_rate: z.number().int().default(44100).optional(),
});
export type ClapDeriveDemoDecodeInput = z.infer<typeof decodeInputSchema>;

export interface ClapDeriveDemoDecodeOutput {
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
  invoke: (handle: ClapDeriveDemoHandle, input: unknown) => Promise<unknown>;
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
    title: "clap-derive encode",
    description: "Demo clap derive-style CLI used by the yorishiro fixture.",
    inputSchema: encodeInputSchema,
    jsonSchema: zodToJsonSchemaShim(encodeInputSchema),
    invoke: async (handle, input) => handle.encode(input as ClapDeriveDemoEncodeInput),
  },
  {
    name: "decode",
    title: "clap-derive decode",
    description: "Demo clap derive-style CLI used by the yorishiro fixture.",
    inputSchema: decodeInputSchema,
    jsonSchema: zodToJsonSchemaShim(decodeInputSchema),
    invoke: async (handle, input) => handle.decode(input as ClapDeriveDemoDecodeInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
