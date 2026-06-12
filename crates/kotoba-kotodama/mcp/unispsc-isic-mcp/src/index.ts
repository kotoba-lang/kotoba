// Public entry point for the @etzhayyim/unispsc-isic-mcp package.
//
// Importers either:
//   1. spawn the CLI (`unispsc-isic-mcp` bin -> ./cli.ts) which speaks stdio
//      to a desktop MCP host (Claude Desktop, Codex CLI, etc.), or
//   2. import `createUnispscIsicMcpServer` + a transport from the
//      `@modelcontextprotocol/sdk` and bind them themselves (used by the
//      in-cluster HTTP transport at deploy time).

export { createUnispscIsicMcpServer } from "./server.js";
export type { McpServerConfig } from "./server.js";
export { tools, findTool } from "./tools.js";
export type {
  ActorsHandle,
  ToolDefinition,
  ClassifyUnispscInput,
  InvokeUnispscAgentInput,
  ListUnispscAgentsInput,
  ClassifyIsicInput,
  ClassifyIsicHierarchicalInput,
  InvokeIsicAgentInput,
  ListIsicAgentsInput,
  TaxonomyHealthInput,
} from "./tools.js";
