// Public entry point. Importers either spawn the bin (stdio MCP host)
// or import the factory + a Streamable HTTP transport.

export { createYorishiroBlsMcpServer } from "./server.js";
export type { McpServerConfig } from "./server.js";
export { tools, findTool } from "./tools.js";
export type { ToolDefinition, BlsHandle } from "./tools.js";
export { createDefaultBlsHandle } from "./handle.js";
