// openapi-facade.test.ts — Unit tests for the OpenAPI spec builder (ADR-0042).
//
// buildOpenApiDocument wraps @hono/zod-openapi's OpenAPIHono as a throwaway
// spec builder — registered routes feed getOpenAPIDocument(), the instance
// is never served. This test uses a realistic manifest (the generated lawfirm
// manifest) to confirm the output is a 3.0.0 document with the expected paths.

import { describe, it, expect } from "vitest";
import { buildOpenApiDocument } from "../src/openapi-facade.js";
import { ROUTES as LAWFIRM_ROUTES, APP_NAME as LAWFIRM_APP_NAME, MCP_TOOLS as LAWFIRM_MCP } from "../src/generated/tool-manifest/lawfirm.js";

describe("buildOpenApiDocument", () => {
	it("produces OpenAPI 3.0.0 with the right metadata", () => {
		const doc = buildOpenApiDocument({
			appName: LAWFIRM_APP_NAME,
			routes: LAWFIRM_ROUTES,
		}) as { openapi: string; info: { title: string; version: string }; paths: Record<string, unknown> };
		expect(doc.openapi).toBe("3.0.0");
		expect(doc.info.title).toBe(`${LAWFIRM_APP_NAME} tools`);
		expect(doc.info.version).toBe("1.0.0");
	});

	it("emits one path per registered route under /xrpc/{NSID}", () => {
		const doc = buildOpenApiDocument({
			appName: LAWFIRM_APP_NAME,
			routes: LAWFIRM_ROUTES,
		}) as { paths: Record<string, unknown> };
		const pathKeys = Object.keys(doc.paths);
		expect(pathKeys.length).toBe(LAWFIRM_ROUTES.length);
		expect(pathKeys.length).toBe(LAWFIRM_MCP.length);
		for (const key of pathKeys) {
			expect(key).toMatch(/^\/xrpc\/com\.etzhayyim\.apps\.lawfirm\./);
		}
		// spot check: createCase is a POST procedure
		expect(doc.paths["/xrpc/com.etzhayyim.apps.lawfirm.createCase"]).toHaveProperty("post");
	});

	it("honors serverUrl override when provided", () => {
		const doc = buildOpenApiDocument({
			appName: LAWFIRM_APP_NAME,
			routes: LAWFIRM_ROUTES,
			serverUrl: "https://lawfirm.etzhayyim.com",
		}) as { servers: Array<{ url: string }> };
		expect(doc.servers).toEqual([{ url: "https://lawfirm.etzhayyim.com" }]);
	});

	it("emits empty servers[] when serverUrl is omitted (deployment-agnostic spec)", () => {
		const doc = buildOpenApiDocument({
			appName: LAWFIRM_APP_NAME,
			routes: LAWFIRM_ROUTES,
		}) as { servers: unknown[] };
		expect(Array.isArray(doc.servers)).toBe(true);
		expect(doc.servers).toHaveLength(0);
	});

	it("is idempotent — multiple builds with same input produce equal output", () => {
		const a = buildOpenApiDocument({ appName: LAWFIRM_APP_NAME, routes: LAWFIRM_ROUTES });
		const b = buildOpenApiDocument({ appName: LAWFIRM_APP_NAME, routes: LAWFIRM_ROUTES });
		expect(JSON.stringify(a)).toBe(JSON.stringify(b));
	});
});
