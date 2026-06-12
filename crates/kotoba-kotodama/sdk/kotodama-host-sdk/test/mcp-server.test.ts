// mcp-server.test.ts — Unit tests for the MCP JSON-RPC dispatcher (ADR-0042).
//
// Uses a fake App stub so the tests don't need the full SDK. Verifies:
//   - initialize returns protocol version + tools capability
//   - ping returns empty result
//   - tools/list returns the manifest's MCP_TOOLS untouched
//   - tools/call validates name against knownNsids, delegates to app.handleXRPC,
//     wraps body as MCP content block, sets isError based on HTTP status
//   - notifications (id undefined) never produce a response
//   - malformed payloads produce standard JSON-RPC error codes

import { describe, it, expect, beforeEach, vi } from "vitest";
import type { App } from "../src/app.js";
import { dispatchMcp, type McpManifest } from "../src/mcp-server.js";

function fakeApp(handler: (path: string, headers: [string, string][], body: Uint8Array) => Promise<{ body: Uint8Array; status: number; headers: Record<string, string> }>): App {
	return { handleXRPC: handler } as unknown as App;
}

const canonicalManifest: McpManifest = {
	appName: "lawfirm",
	mcpTools: [
		{
			name: "com.etzhayyim.apps.lawfirm.createCase",
			description: "Open a new client matter",
			inputSchema: { type: "object", properties: { domain: { type: "string" } } },
		},
		{
			name: "com.etzhayyim.apps.lawfirm.listMatters",
			description: "List matters",
			inputSchema: { type: "object", properties: {} },
		},
	],
	knownNsids: new Set([
		"com.etzhayyim.apps.lawfirm.createCase",
		"com.etzhayyim.apps.lawfirm.listMatters",
	]),
};

const serverInfo = { name: "kotodama-lawfirm", version: "1.0.0" };

function ctx(app: App) {
	return {
		app,
		manifest: canonicalManifest,
		headers: [] as [string, string][],
		serverInfo,
	};
}

describe("dispatchMcp — initialize", () => {
	it("returns protocol version + tools capability", async () => {
		const app = fakeApp(async () => ({ body: new Uint8Array(), status: 200, headers: {} }));
		const resp = await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: 1,
			method: "initialize",
			params: { protocolVersion: "2025-06-18", capabilities: {} },
		}));
		expect(resp).not.toBeNull();
		expect(resp!.id).toBe(1);
		const result = resp!.result as { protocolVersion: string; capabilities: { tools: { listChanged: boolean } }; serverInfo: typeof serverInfo };
		expect(result.protocolVersion).toBe("2025-06-18");
		expect(result.capabilities.tools.listChanged).toBe(false);
		expect(result.serverInfo).toEqual(serverInfo);
	});
});

describe("dispatchMcp — ping", () => {
	it("returns empty object result", async () => {
		const app = fakeApp(async () => ({ body: new Uint8Array(), status: 200, headers: {} }));
		const resp = await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: 42,
			method: "ping",
		}));
		expect(resp!.id).toBe(42);
		expect(resp!.result).toEqual({});
	});
});

describe("dispatchMcp — tools/list", () => {
	it("returns manifest mcpTools verbatim", async () => {
		const app = fakeApp(async () => ({ body: new Uint8Array(), status: 200, headers: {} }));
		const resp = await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: "list-1",
			method: "tools/list",
		}));
		const tools = (resp!.result as { tools: unknown[] }).tools;
		expect(tools).toHaveLength(2);
		expect((tools[0] as { name: string }).name).toBe("com.etzhayyim.apps.lawfirm.createCase");
	});
});

// G4 (ADR-2604261000 §G4): bpmnRouter mock helpers for integration tests.
// We mock the router module directly so the test exercises the real
// dispatchMcp branching (lookup → dispatch → fall-through) without needing
// Hyperdrive or the live dispatcher.
const bpmnRouterMocks = {
	lookup: vi.fn(),
	dispatch: vi.fn(),
};
vi.mock("../src/mcp-bpmn-router.js", () => ({
	lookupBpmnRoute: (opts: unknown) => bpmnRouterMocks.lookup(opts),
	dispatchToBpmn: (opts: unknown) => bpmnRouterMocks.dispatch(opts),
}));
function withBpmnCtx(app: App) {
	return {
		...ctx(app),
		bpmnRouter: { hyperdrive: { __mock: true }, bpmnUrl: "https://dispatcher.test" },
	};
}

describe("dispatchMcp — tools/call", () => {
	beforeEach(() => {
		bpmnRouterMocks.lookup.mockReset();
		bpmnRouterMocks.dispatch.mockReset();
	});

	it("delegates to app.handleXRPC and wraps response as content block", async () => {
		const seen: { path: string; args: unknown } = { path: "", args: null };
		const app = fakeApp(async (path, _h, body) => {
			seen.path = path;
			seen.args = JSON.parse(new TextDecoder().decode(body));
			return {
				body: new TextEncoder().encode(JSON.stringify({ did: "did:etzhayyim:abc", uri: "at://..." })),
				status: 200,
				headers: {},
			};
		});
		const resp = await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: "call-1",
			method: "tools/call",
			params: {
				name: "com.etzhayyim.apps.lawfirm.createCase",
				arguments: { domain: "ni138", state: "IN-MH", lang: "hi" },
			},
		}));
		expect(seen.path).toBe("/xrpc/com.etzhayyim.apps.lawfirm.createCase");
		expect(seen.args).toEqual({ domain: "ni138", state: "IN-MH", lang: "hi" });
		const result = resp!.result as { content: Array<{ type: string; text: string }>; isError: boolean };
		expect(result.isError).toBe(false);
		expect(result.content).toHaveLength(1);
		expect(result.content[0].type).toBe("text");
		expect(JSON.parse(result.content[0].text)).toEqual({ did: "did:etzhayyim:abc", uri: "at://..." });
	});

	it("marks isError=true when downstream XRPC returns 4xx/5xx", async () => {
		const app = fakeApp(async () => ({
			body: new TextEncoder().encode(JSON.stringify({ error: "Forbidden" })),
			status: 403,
			headers: {},
		}));
		const resp = await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: 7,
			method: "tools/call",
			params: { name: "com.etzhayyim.apps.lawfirm.listMatters", arguments: {} },
		}));
		const result = resp!.result as { isError: boolean };
		expect(result.isError).toBe(true);
	});

	it("rejects unknown tool name with METHOD_NOT_FOUND", async () => {
		const app = fakeApp(async () => ({ body: new Uint8Array(), status: 200, headers: {} }));
		const resp = await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: 8,
			method: "tools/call",
			params: { name: "com.etzhayyim.apps.lawfirm.noSuchTool", arguments: {} },
		}));
		expect(resp!.error?.code).toBe(-32601);
		expect(resp!.error?.message).toContain("tool not registered");
	});

	it("rejects missing params.name with INVALID_PARAMS", async () => {
		const app = fakeApp(async () => ({ body: new Uint8Array(), status: 200, headers: {} }));
		const resp = await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: 9,
			method: "tools/call",
			params: {},
		}));
		expect(resp!.error?.code).toBe(-32602);
	});

	it("defaults arguments to empty object when omitted", async () => {
		const seen: { args: unknown } = { args: null };
		const app = fakeApp(async (_p, _h, body) => {
			seen.args = JSON.parse(new TextDecoder().decode(body));
			return { body: new TextEncoder().encode("{}"), status: 200, headers: {} };
		});
		await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: 10,
			method: "tools/call",
			params: { name: "com.etzhayyim.apps.lawfirm.listMatters" },
		}));
		expect(seen.args).toEqual({});
	});

	// ── G4: bpmn-dispatcher routing (ADR-2604261000 §G4) ──

	it("G4: routes to bpmn-dispatcher when binding exists", async () => {
		bpmnRouterMocks.lookup.mockResolvedValue({
			nsid: "com.etzhayyim.apps.lawfirm.createCase",
			bpmnProcessId: "lawfirm-create-case",
			timeoutMs: 30000,
		});
		bpmnRouterMocks.dispatch.mockResolvedValue({
			body: new TextEncoder().encode(JSON.stringify({ caseDid: "did:web:lawfirm.etzhayyim.com:case:42" })),
			status: 200,
			headers: { "content-type": "application/json" },
		});
		const handleXrpcCalls: number[] = [];
		const app = fakeApp(async () => {
			handleXrpcCalls.push(Date.now());
			return { body: new TextEncoder().encode("{}"), status: 200, headers: {} };
		});

		const resp = await dispatchMcp(withBpmnCtx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: "g4-1",
			method: "tools/call",
			params: { name: "com.etzhayyim.apps.lawfirm.createCase", arguments: { domain: "ni138" } },
		}));

		expect(bpmnRouterMocks.lookup).toHaveBeenCalledOnce();
		expect(bpmnRouterMocks.dispatch).toHaveBeenCalledOnce();
		expect(handleXrpcCalls).toHaveLength(0);  // in-process path NOT taken
		const result = resp!.result as { content: Array<{ text: string }>; isError: boolean };
		expect(result.isError).toBe(false);
		expect(JSON.parse(result.content[0].text)).toEqual({ caseDid: "did:web:lawfirm.etzhayyim.com:case:42" });
	});

	it("G4: falls through to handleXRPC when no binding exists", async () => {
		bpmnRouterMocks.lookup.mockResolvedValue(null);  // no binding
		const handleXrpcCalls: number[] = [];
		const app = fakeApp(async () => {
			handleXrpcCalls.push(Date.now());
			return {
				body: new TextEncoder().encode(JSON.stringify({ inProcessHandled: true })),
				status: 200,
				headers: {},
			};
		});

		const resp = await dispatchMcp(withBpmnCtx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: "g4-2",
			method: "tools/call",
			params: { name: "com.etzhayyim.apps.lawfirm.listMatters", arguments: {} },
		}));

		expect(bpmnRouterMocks.lookup).toHaveBeenCalledOnce();
		expect(bpmnRouterMocks.dispatch).not.toHaveBeenCalled();
		expect(handleXrpcCalls).toHaveLength(1);  // fell through
		const result = resp!.result as { content: Array<{ text: string }>; isError: boolean };
		expect(JSON.parse(result.content[0].text)).toEqual({ inProcessHandled: true });
	});

	it("G4: falls through to handleXRPC when dispatcher returns null (5xx)", async () => {
		bpmnRouterMocks.lookup.mockResolvedValue({
			nsid: "com.etzhayyim.apps.lawfirm.createCase",
			bpmnProcessId: "p1",
			timeoutMs: 30000,
		});
		bpmnRouterMocks.dispatch.mockResolvedValue(null);  // dispatcher 5xx → null
		const fallbackBody = JSON.stringify({ recoveredInProcess: true });
		const app = fakeApp(async () => ({
			body: new TextEncoder().encode(fallbackBody),
			status: 200,
			headers: {},
		}));

		const resp = await dispatchMcp(withBpmnCtx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: "g4-3",
			method: "tools/call",
			params: { name: "com.etzhayyim.apps.lawfirm.createCase", arguments: {} },
		}));

		expect(bpmnRouterMocks.dispatch).toHaveBeenCalledOnce();
		const result = resp!.result as { content: Array<{ text: string }>; isError: boolean };
		expect(JSON.parse(result.content[0].text)).toEqual({ recoveredInProcess: true });
	});

	it("G4: bpmnRouter omitted (status quo) skips lookup entirely", async () => {
		const app = fakeApp(async () => ({
			body: new TextEncoder().encode("{}"),
			status: 200,
			headers: {},
		}));

		await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: "g4-4",
			method: "tools/call",
			params: { name: "com.etzhayyim.apps.lawfirm.listMatters", arguments: {} },
		}));

		expect(bpmnRouterMocks.lookup).not.toHaveBeenCalled();
		expect(bpmnRouterMocks.dispatch).not.toHaveBeenCalled();
	});
});

describe("dispatchMcp — notifications and malformed input", () => {
	it("returns null for notifications/initialized (no id, no response)", async () => {
		const app = fakeApp(async () => ({ body: new Uint8Array(), status: 200, headers: {} }));
		const resp = await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "2.0",
			method: "notifications/initialized",
		}));
		expect(resp).toBeNull();
	});

	it("returns null when any method is called as a notification", async () => {
		const app = fakeApp(async () => ({ body: new Uint8Array(), status: 200, headers: {} }));
		const resp = await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "2.0",
			method: "nonexistent/method",
		}));
		expect(resp).toBeNull();
	});

	it("returns PARSE_ERROR on invalid JSON", async () => {
		const app = fakeApp(async () => ({ body: new Uint8Array(), status: 200, headers: {} }));
		const resp = await dispatchMcp(ctx(app), "not json at all");
		expect(resp!.error?.code).toBe(-32700);
	});

	it("returns INVALID_REQUEST when jsonrpc field is wrong", async () => {
		const app = fakeApp(async () => ({ body: new Uint8Array(), status: 200, headers: {} }));
		const resp = await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "1.0",
			id: 1,
			method: "ping",
		}));
		expect(resp!.error?.code).toBe(-32600);
	});

	it("returns METHOD_NOT_FOUND for unknown method when id is present", async () => {
		const app = fakeApp(async () => ({ body: new Uint8Array(), status: 200, headers: {} }));
		const resp = await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: 11,
			method: "unknown/method",
		}));
		expect(resp!.error?.code).toBe(-32601);
	});

	it("wraps handler exceptions as INTERNAL_ERROR", async () => {
		const app = fakeApp(async () => {
			throw new Error("downstream boom");
		});
		const resp = await dispatchMcp(ctx(app), JSON.stringify({
			jsonrpc: "2.0",
			id: 12,
			method: "tools/call",
			params: { name: "com.etzhayyim.apps.lawfirm.listMatters", arguments: {} },
		}));
		expect(resp!.error?.code).toBe(-32603);
		expect(resp!.error?.message).toContain("downstream boom");
	});
});
