import { z, type ZodObject } from "zod";

export interface CobraDemoHandle {
  cobra_demo(input: CobraDemoCobraDemoInput): Promise<CobraDemoCobraDemoOutput>;
  greet(input: CobraDemoGreetInput): Promise<CobraDemoGreetOutput>;
  render(input: CobraDemoRenderInput): Promise<CobraDemoRenderOutput>;
}

// ── cobra-demo ─────────────────────────────────────────────────────────
export const cobra_demoInputSchema = z.object({
    verbose: z.boolean().default(false).describe("Enable verbose logging.").optional(),
    config: z.string().default("/etc/cobra-demo.yaml").describe("Path to config file.").optional(),
});
export type CobraDemoCobraDemoInput = z.infer<typeof cobra_demoInputSchema>;

export interface CobraDemoCobraDemoOutput {
  exitCode: number;
  stdout?: string;
  stderr?: string;
  error?: string;
}

// ── greet ─────────────────────────────────────────────────────────
export const greetInputSchema = z.object({
    verbose: z.boolean().default(false).describe("Enable verbose logging.").optional(),
    config: z.string().default("/etc/cobra-demo.yaml").describe("Path to config file.").optional(),
    shout: z.boolean().default(false).describe("Uppercase the greeting.").optional(),
    lang: z.string().default("en").describe("Language code (en|jp).").optional(),
    arg0: z.string().describe("Positional argument 0 (cobra ExactNArgs)."),
});
export type CobraDemoGreetInput = z.infer<typeof greetInputSchema>;

export interface CobraDemoGreetOutput {
  exitCode: number;
  stdout?: string;
  stderr?: string;
  error?: string;
}

// ── render ─────────────────────────────────────────────────────────
export const renderInputSchema = z.object({
    verbose: z.boolean().default(false).describe("Enable verbose logging.").optional(),
    config: z.string().default("/etc/cobra-demo.yaml").describe("Path to config file.").optional(),
    max_rows: z.number().int().default(100).describe("Maximum rows.").optional(),
    quality: z.number().default(0.9).describe("Quality multiplier.").optional(),
    arg0: z.string().describe("Positional argument 0 (cobra MinimumNArgs)."),
});
export type CobraDemoRenderInput = z.infer<typeof renderInputSchema>;

export interface CobraDemoRenderOutput {
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
  invoke: (handle: CobraDemoHandle, input: unknown) => Promise<unknown>;
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
    name: "cobra_demo",
    title: "Demo cobra CLI used by the yorishiro source-repo fixture.",
    description: "Longer description of the cobra demo CLI.",
    inputSchema: cobra_demoInputSchema,
    jsonSchema: zodToJsonSchemaShim(cobra_demoInputSchema),
    invoke: async (handle, input) => handle.cobra_demo(input as CobraDemoCobraDemoInput),
  },
  {
    name: "greet",
    title: "Print a greeting.",
    description: "Print a greeting for NAME with optional shouting.",
    inputSchema: greetInputSchema,
    jsonSchema: zodToJsonSchemaShim(greetInputSchema),
    invoke: async (handle, input) => handle.greet(input as CobraDemoGreetInput),
  },
  {
    name: "render",
    title: "Render output to file or stdout.",
    description: "Render output to file or stdout.",
    inputSchema: renderInputSchema,
    jsonSchema: zodToJsonSchemaShim(renderInputSchema),
    invoke: async (handle, input) => handle.render(input as CobraDemoRenderInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
