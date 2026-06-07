// tool-manifest/_types.ts — Auto-generated. DO NOT EDIT.
// Regenerate with: node 70-tools/scripts/contract/gen-tool-manifest.mjs
//
// Shared type definitions for per-app tool manifests (ADR-0042).

export type LexiconMainType = "query" | "procedure";

export interface JsonSchemaLike {
	type?: string;
	properties?: Record<string, unknown>;
	required?: string[];
	description?: string;
	[key: string]: unknown;
}

export interface ToolManifestEntry {
	nsid: string;
	description: string;
	inputSchema: JsonSchemaLike;
	outputSchema: JsonSchemaLike;
	method: LexiconMainType;
}

export interface McpTool {
	name: string;
	description: string;
	inputSchema: JsonSchemaLike;
}
