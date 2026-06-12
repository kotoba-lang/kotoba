// Public entry point. Importers either spawn the bin (stdio MCP host)
// or import the factory + a Streamable HTTP transport.

export { createYorishiroHuggingfaceInferenceMcpServer } from "./server.js";
export type { McpServerConfig } from "./server.js";
export { tools, findTool } from "./tools.js";
export type { ToolDefinition, HuggingfaceInferenceHandle } from "./tools.js";
export { createDefaultHuggingfaceInferenceHandle } from "./handle.js";
