import { z, type ZodObject } from "zod";

export interface DemoFixtureHandle {
  greet(input: DemoFixtureGreetInput): Promise<DemoFixtureGreetOutput>;
  head(input: DemoFixtureHeadInput): Promise<DemoFixtureHeadOutput>;
}

// ── greet ─────────────────────────────────────────────────────────
export const greetInputSchema = z.object({
    name: z.string(),
    shout: z.boolean().describe("Uppercase the greeting.").optional(),
    lang: z.string().default("en").describe("Language code (en|jp).").optional(),
});
export type DemoFixtureGreetInput = z.infer<typeof greetInputSchema>;

export interface DemoFixtureGreetOutput {
  exitCode: number;
  stdout?: string;
  stderr?: string;
  error?: string;
}

// ── head ─────────────────────────────────────────────────────────
export const headInputSchema = z.object({
    input_path: z.string(),
    output_path: z.string().default("-").optional(),
    max_lines: z.number().int().default(100).describe("Maximum lines to read.").optional(),
    encoding: z.string().default("utf-8").describe("Input encoding.").optional(),
});
export type DemoFixtureHeadInput = z.infer<typeof headInputSchema>;

export interface DemoFixtureHeadOutput {
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
  invoke: (handle: DemoFixtureHandle, input: unknown) => Promise<unknown>;
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
    name: "greet",
    title: "Print a greeting for NAME.",
    description: "Print a greeting for NAME.",
    inputSchema: greetInputSchema,
    jsonSchema: zodToJsonSchemaShim(greetInputSchema),
    invoke: async (handle, input) => handle.greet(input as DemoFixtureGreetInput),
  },
  {
    name: "head",
    title: "Read up to MAX_LINES from INPUT_PATH and write to OUTPUT_PATH.",
    description: "Read up to MAX_LINES from INPUT_PATH and write to OUTPUT_PATH.",
    inputSchema: headInputSchema,
    jsonSchema: zodToJsonSchemaShim(headInputSchema),
    invoke: async (handle, input) => handle.head(input as DemoFixtureHeadInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
