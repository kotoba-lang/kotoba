import { z, type ZodObject } from "zod";

export interface PdftotextHandle {
  convert(input: PdftotextConvertInput): Promise<PdftotextConvertOutput>;
}

// ── convert ─────────────────────────────────────────────────────────
export const convertInputSchema = z.object({
    first_page: z.number().int().describe("First page to convert (1-based).").optional(),
    last_page: z.number().int().describe("Last page to convert (inclusive).").optional(),
    layout: z.boolean().describe("Maintain (as best as possible) original physical layout.").optional(),
    raw: z.boolean().describe("Keep strings in content stream order.").optional(),
    encoding: z.string().default("UTF-8").describe("Output text encoding name (e.g. UTF-8, Latin1).").optional(),
    pdf_file: z.string().describe("Input PDF path on the cell runtime filesystem."),
    text_file: z.string().default("-").describe("Output text path; '-' (default) sends to stdout, which the cell captures.").optional(),
});
export type PdftotextConvertInput = z.infer<typeof convertInputSchema>;

export interface PdftotextConvertOutput {
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
  invoke: (handle: PdftotextHandle, input: unknown) => Promise<unknown>;
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
    name: "convert",
    title: "Convert a PDF file to plain text",
    description: "Invoke `pdftotext [flags] <pdf_file> [text_file]`. When `text_file` is '-' (default) the result lands on stdout; the cell captures stdout and returns it in the response.",
    inputSchema: convertInputSchema,
    jsonSchema: zodToJsonSchemaShim(convertInputSchema),
    invoke: async (handle, input) => handle.convert(input as PdftotextConvertInput),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
