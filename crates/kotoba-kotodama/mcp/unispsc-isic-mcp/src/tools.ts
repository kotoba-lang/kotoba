// tools.ts — MCP tool definitions for the UNSPSC + ISIC langservers.
//
// Each tool corresponds 1:1 to a lexicon under
// `00-contracts/lexicons/com/etzhayyim/apps/{unispsc,isic}/`, so MCP / XRPC /
// in-process actor callers share identical input/output schemas.
//
// The handler body delegates to the per-taxonomy actor wrapper authored in
// ADR-2605180900 Phase 6 (`@etzhayyim/kotodama-host-sdk`).

import { z } from "zod";
import type { IsicActor, UnispscActor } from "@etzhayyim/kotodama-host-sdk";

// ───── Shared shapes ─────────────────────────────────────────────────────────

const modelHintSchema = z
  .enum(["haiku-4.5", "sonnet-4.6", "auto"])
  .default("auto")
  .describe(
    "LLM selection hint. 'auto' = Haiku-first with confidence-based Sonnet escalation.",
  );

const confidenceThresholdSchema = z
  .number()
  .min(0)
  .max(1)
  .default(0.7)
  .describe(
    "Below this top-candidate confidence, escalate from Haiku to Sonnet.",
  );

// ───── UNSPSC tool input schemas ────────────────────────────────────────────

export const classifyUnispscInputSchema = z.object({
  description: z
    .string()
    .min(1)
    .max(4000)
    .describe("Free-text product or service description to classify."),
  topK: z.number().int().min(1).max(20).default(5),
  modelHint: modelHintSchema.optional(),
  confidenceThreshold: confidenceThresholdSchema.optional(),
});
export type ClassifyUnispscInput = z.infer<typeof classifyUnispscInputSchema>;

export const invokeUnispscAgentInputSchema = z.object({
  code: z
    .string()
    .min(4)
    .max(12)
    .describe("UNSPSC commodity code (typically 8 digits)."),
  payload: z
    .record(z.string(), z.unknown())
    .describe("Agent input state matching the agent's StateGraph schema."),
  modelHint: modelHintSchema.optional(),
  timeoutMs: z.number().int().min(100).max(25_000).default(10_000).optional(),
});
export type InvokeUnispscAgentInput = z.infer<
  typeof invokeUnispscAgentInputSchema
>;

export const listUnispscAgentsInputSchema = z.object({
  prefix: z
    .string()
    .optional()
    .describe("Filter by commodity-code prefix (e.g. '10')."),
  limit: z.number().int().min(1).max(1000).default(100),
  cursor: z.string().optional(),
});
export type ListUnispscAgentsInput = z.infer<
  typeof listUnispscAgentsInputSchema
>;

// ───── ISIC tool input schemas ──────────────────────────────────────────────

export const classifyIsicInputSchema = z.object({
  description: z.string().min(1).max(4000),
  topK: z.number().int().min(1).max(20).default(5),
  modelHint: modelHintSchema.optional(),
  confidenceThreshold: confidenceThresholdSchema.optional(),
});
export type ClassifyIsicInput = z.infer<typeof classifyIsicInputSchema>;

export const classifyIsicHierarchicalInputSchema = z.object({
  description: z.string().min(1).max(4000),
  stopAt: z
    .enum(["section", "division", "group", "class"])
    .default("class")
    .describe("Highest level of detail to resolve."),
  modelHint: modelHintSchema.optional(),
  confidenceThreshold: confidenceThresholdSchema.optional(),
});
export type ClassifyIsicHierarchicalInput = z.infer<
  typeof classifyIsicHierarchicalInputSchema
>;

export const invokeIsicAgentInputSchema = z.object({
  classCode: z
    .string()
    .min(4)
    .max(4)
    .describe("4-digit ISIC Rev. 4 class code."),
  payload: z.record(z.string(), z.unknown()),
  modelHint: modelHintSchema.optional(),
  timeoutMs: z.number().int().min(100).max(25_000).default(10_000).optional(),
});
export type InvokeIsicAgentInput = z.infer<typeof invokeIsicAgentInputSchema>;

export const listIsicAgentsInputSchema = z.object({
  divisionPrefix: z
    .string()
    .optional()
    .describe("Filter by 2-digit division code prefix."),
  section: z
    .string()
    .optional()
    .describe("Filter by ISIC section letter (A through U)."),
  limit: z.number().int().min(1).max(500).default(100),
  cursor: z.string().optional(),
});
export type ListIsicAgentsInput = z.infer<typeof listIsicAgentsInputSchema>;

// ───── Shared health tool input ─────────────────────────────────────────────

export const taxonomyHealthInputSchema = z.object({});
export type TaxonomyHealthInput = z.infer<typeof taxonomyHealthInputSchema>;

// ───── Tool registry ────────────────────────────────────────────────────────

export interface ActorsHandle {
  unispsc: UnispscActor;
  isic: IsicActor;
}

export interface ToolDefinition {
  name: string;
  title: string;
  description: string;
  inputSchema: z.ZodTypeAny;
  handler: (input: unknown, actors: ActorsHandle) => Promise<unknown>;
}

export const tools: ToolDefinition[] = [
  // UNSPSC
  {
    name: "classify_unispsc",
    title: "Classify text into UNSPSC commodity codes",
    description:
      "Classify a free-text product/service description into top-K UNSPSC codes. " +
      "Haiku-4.5 by default; confidence below threshold escalates to Sonnet-4.6.",
    inputSchema: classifyUnispscInputSchema,
    handler: async (input, actors) =>
      actors.unispsc.classify(input as ClassifyUnispscInput),
  },
  {
    name: "invoke_unispsc_agent",
    title: "Invoke a UNSPSC commodity agent",
    description:
      "Invoke the LangGraph Pregel agent for a specific UNSPSC commodity code " +
      "with a payload matching its StateGraph schema. Returns the post-transition state.",
    inputSchema: invokeUnispscAgentInputSchema,
    handler: async (input, actors) =>
      actors.unispsc.invokeAgent(input as InvokeUnispscAgentInput),
  },
  {
    name: "list_unispsc_agents",
    title: "List UNSPSC commodity agents",
    description:
      "Paged listing of UNSPSC agents in the registry. Filter by commodity-code prefix.",
    inputSchema: listUnispscAgentsInputSchema,
    handler: async (input, actors) =>
      actors.unispsc.listAgents(input as ListUnispscAgentsInput),
  },
  {
    name: "unispsc_health",
    title: "UNSPSC langserver health probe",
    description:
      "Returns registry readiness, agent count, warm-cache size, and available models.",
    inputSchema: taxonomyHealthInputSchema,
    handler: async (_input, actors) => actors.unispsc.health(),
  },

  // ISIC
  {
    name: "classify_isic",
    title: "Classify text into an ISIC Rev. 4 class",
    description:
      "Single-level (leaf) ISIC Rev. 4 classification. Use classify_isic_hierarchical " +
      "to get section/division/group context.",
    inputSchema: classifyIsicInputSchema,
    handler: async (input, actors) =>
      actors.isic.classify(input as ClassifyIsicInput),
  },
  {
    name: "classify_isic_hierarchical",
    title: "Hierarchical ISIC Rev. 4 classification",
    description:
      "Resolve section (A-U) → division (2-digit) → group (3-digit) → class (4-digit). " +
      "Stop at any level via the stopAt parameter.",
    inputSchema: classifyIsicHierarchicalInputSchema,
    handler: async (input, actors) =>
      actors.isic.hierarchicalClassify(input as ClassifyIsicHierarchicalInput),
  },
  {
    name: "invoke_isic_agent",
    title: "Invoke an ISIC class agent",
    description:
      "Invoke the LangGraph Pregel agent for a specific ISIC Rev. 4 class code " +
      "with a payload matching its StateGraph schema.",
    inputSchema: invokeIsicAgentInputSchema,
    handler: async (input, actors) =>
      actors.isic.invokeAgent(input as InvokeIsicAgentInput),
  },
  {
    name: "list_isic_agents",
    title: "List ISIC class agents",
    description:
      "Paged listing of ISIC agents in the registry. Filter by section or divisionPrefix.",
    inputSchema: listIsicAgentsInputSchema,
    handler: async (input, actors) =>
      actors.isic.listAgents(input as ListIsicAgentsInput),
  },
  {
    name: "isic_health",
    title: "ISIC langserver health probe",
    description:
      "Returns registry readiness, agent count, warm-cache size, and available models.",
    inputSchema: taxonomyHealthInputSchema,
    handler: async (_input, actors) => actors.isic.health(),
  },
];

export function findTool(name: string): ToolDefinition | undefined {
  return tools.find((t) => t.name === name);
}
