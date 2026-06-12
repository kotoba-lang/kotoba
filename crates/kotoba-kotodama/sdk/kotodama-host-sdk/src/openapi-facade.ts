// openapi-facade.ts — Build an OpenAPI 3.0 document from generated routes (ADR-0042).
//
// Uses @hono/zod-openapi as a spec builder only — routes are registered on a
// throwaway OpenAPIHono instance with dummy handlers, then the spec is
// extracted via getOpenAPIDocument(). The instance is not mounted as a live
// route tree (doing so would conflict with the main router's /xrpc/:nsid path).
//
// The actual execution path for every tool remains /xrpc/:nsid (AT-native) and
// /mcp (tools/call). This module only powers /.well-known/openapi.json.

import { OpenAPIHono, type RouteConfig } from "@hono/zod-openapi";

export interface OpenApiFacadeInput {
	appName: string;
	routes: readonly RouteConfig[];
	version?: string;
	title?: string;
	description?: string;
	serverUrl?: string;
}

export function buildOpenApiDocument(input: OpenApiFacadeInput): Record<string, unknown> {
	const builder = new OpenAPIHono();
	for (const route of input.routes) {
		// Dummy handler — this instance is not actually served, only used as a
		// spec builder. app.openapi() requires a handler to register the route.
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		builder.openapi(route as any, ((c: any) => c.json({})) as any);
	}

	const doc = builder.getOpenAPIDocument({
		openapi: "3.0.0",
		info: {
			title: input.title ?? `${input.appName} tools`,
			version: input.version ?? "1.0.0",
			description:
				input.description ??
				`Tools exposed by kotodama actor '${input.appName}' via XRPC and MCP. ` +
				"See /mcp for Model Context Protocol (LangGraph / OpenAI Apps SDK / Claude Desktop).",
		},
		servers: input.serverUrl ? [{ url: input.serverUrl }] : [],
	});
	return doc as unknown as Record<string, unknown>;
}
