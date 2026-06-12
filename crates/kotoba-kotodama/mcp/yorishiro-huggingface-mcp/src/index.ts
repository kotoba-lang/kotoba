// Public entry point. Importers either spawn the bin (stdio MCP host)
// or import the factory + a Streamable HTTP transport.

export { createYorishiroHuggingfaceMcpServer } from "./server.js";
export type { McpServerConfig } from "./server.js";
export { tools, findTool } from "./tools.js";
export type { ToolDefinition, HuggingfaceHandle } from "./tools.js";
export { createDefaultHuggingfaceHandle } from "./handle.js";
