// mcp-bpmn-router.test.ts — BPMN routing for MCP tools/call (G4).

import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";

const executeMock = vi.fn();
const limitMock = vi.fn();
const whereMock = vi.fn();
const selectMock = vi.fn();
const selectFromMock = vi.fn();

function resetChain() {
	executeMock.mockReset();
	limitMock.mockReset().mockReturnValue({ execute: executeMock });
	whereMock.mockReset().mockReturnValue({ where: whereMock, limit: limitMock, execute: executeMock });
	selectMock.mockReset().mockReturnValue({ where: whereMock });
	selectFromMock.mockReset().mockReturnValue({ select: selectMock });
}

// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
vi.mock("../src/kysely.js", () => ({
	createKyselyDb: () => ({ selectFrom: selectFromMock }),
}));

import {
	lookupBpmnRoute,
	dispatchToBpmn,
	clearBpmnRouteCache,
} from "../src/mcp-bpmn-router.js";

const HYPERDRIVE = { __mock: true };
const NSID = "com.etzhayyim.apps.lawfirm.createCase";

const fetchMock = vi.fn();
const originalFetch = globalThis.fetch;

beforeEach(() => {
	resetChain();
	clearBpmnRouteCache();
	fetchMock.mockReset();
	(globalThis as { fetch: typeof fetch }).fetch = fetchMock as unknown as typeof fetch;
});

afterEach(() => {
	(globalThis as { fetch: typeof fetch }).fetch = originalFetch;
});

describe("lookupBpmnRoute", () => {
	it("returns null when no row exists (cached)", async () => {
		executeMock.mockResolvedValueOnce([]);
		const route = await lookupBpmnRoute({ hyperdrive: HYPERDRIVE, nsid: NSID });
		expect(route).toBeNull();

		// Second call hits cache, no DB
		const route2 = await lookupBpmnRoute({ hyperdrive: HYPERDRIVE, nsid: NSID });
		expect(route2).toBeNull();
		expect(executeMock).toHaveBeenCalledTimes(1);
	});

	it("returns route when binding row exists", async () => {
		executeMock.mockResolvedValueOnce([
			{
				nsid: NSID,
				bpmn_process_id: "lawfirm-create-case",
				bpmn_version: 1,
				result_timeout_ms: 30000,
				status: "active",
			},
		]);
		const route = await lookupBpmnRoute({ hyperdrive: HYPERDRIVE, nsid: NSID });
		expect(route).toEqual({
			nsid: NSID,
			bpmnProcessId: "lawfirm-create-case",
			timeoutMs: 30000,
		});
	});

	it("defaults timeout when result_timeout_ms is null", async () => {
		executeMock.mockResolvedValueOnce([
			{ nsid: NSID, bpmn_process_id: "p1", bpmn_version: null, result_timeout_ms: null, status: null },
		]);
		const route = await lookupBpmnRoute({ hyperdrive: HYPERDRIVE, nsid: NSID });
		expect(route?.timeoutMs).toBe(60000);
	});

	it("returns null on missing inputs without DB hit", async () => {
		expect(await lookupBpmnRoute({ hyperdrive: null, nsid: NSID })).toBeNull();
		expect(await lookupBpmnRoute({ hyperdrive: HYPERDRIVE, nsid: "" })).toBeNull();
		expect(executeMock).not.toHaveBeenCalled();
	});

	it("noCache: true bypasses cache", async () => {
		executeMock.mockResolvedValue([
			{ nsid: NSID, bpmn_process_id: "p1", bpmn_version: 1, result_timeout_ms: 1000, status: "active" },
		]);
		await lookupBpmnRoute({ hyperdrive: HYPERDRIVE, nsid: NSID });
		await lookupBpmnRoute({ hyperdrive: HYPERDRIVE, nsid: NSID, noCache: true });
		expect(executeMock).toHaveBeenCalledTimes(2);
	});

	it("on DB error caches negative briefly and returns null", async () => {
		executeMock.mockRejectedValueOnce(new Error("RW down"));
		const route = await lookupBpmnRoute({ hyperdrive: HYPERDRIVE, nsid: NSID });
		expect(route).toBeNull();
		// Second immediate call hits the 5s negative cache
		const route2 = await lookupBpmnRoute({ hyperdrive: HYPERDRIVE, nsid: NSID });
		expect(route2).toBeNull();
		expect(executeMock).toHaveBeenCalledTimes(1);
	});
});

describe("dispatchToBpmn", () => {
	it("forwards to {bpmnUrl}/xrpc/{nsid} with content-type and body", async () => {
		fetchMock.mockResolvedValueOnce(
			new Response(JSON.stringify({ ok: true, variables: { caseDid: "did:web:lawfirm.etzhayyim.com:case:1" } }), {
				status: 200,
				headers: { "content-type": "application/json" },
			}),
		);
		const result = await dispatchToBpmn({
			bpmnUrl: "https://dispatcher.test",
			nsid: NSID,
			args: { domain: "ni138" },
			headers: [["authorization", "Bearer xyz"]],
			timeoutMs: 5000,
		});
		expect(result).not.toBeNull();
		expect(result?.status).toBe(200);
		const text = new TextDecoder().decode(result!.body);
		// Zeebe `{ok, variables}` shape unwrapped to flat handler shape
		expect(JSON.parse(text)).toEqual({ caseDid: "did:web:lawfirm.etzhayyim.com:case:1" });

		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toBe("https://dispatcher.test/xrpc/" + NSID);
		expect((init as RequestInit).method).toBe("POST");
		const fwdHeaders = (init as RequestInit).headers as Record<string, string>;
		expect(fwdHeaders["content-type"]).toBe("application/json");
		expect(fwdHeaders["authorization"]).toBe("Bearer xyz");
	});

	it("returns null on 5xx (caller falls through to in-process)", async () => {
		fetchMock.mockResolvedValueOnce(new Response("internal", { status: 503 }));
		const result = await dispatchToBpmn({
			bpmnUrl: "https://dispatcher.test",
			nsid: NSID,
			args: {},
			headers: [],
		});
		expect(result).toBeNull();
	});

	it("surfaces 4xx body verbatim (no unwrap)", async () => {
		fetchMock.mockResolvedValueOnce(
			new Response(JSON.stringify({ error: "InvalidInput" }), { status: 400 }),
		);
		const result = await dispatchToBpmn({
			bpmnUrl: "https://dispatcher.test",
			nsid: NSID,
			args: {},
			headers: [],
		});
		expect(result?.status).toBe(400);
		expect(JSON.parse(new TextDecoder().decode(result!.body))).toEqual({ error: "InvalidInput" });
	});

	it("filters headers (only authorization, content-type, x-etzhayyim-*, atproto-*)", async () => {
		fetchMock.mockResolvedValueOnce(new Response("{}", { status: 200 }));
		await dispatchToBpmn({
			bpmnUrl: "https://dispatcher.test",
			nsid: NSID,
			args: {},
			headers: [
				["authorization", "Bearer x"],
				["x-etzhayyim-org-id", "org1"],
				["atproto-proxy", "did:web:appview"],
				["cookie", "etzhayyim_session=should-not-leak"],
				["host", "lf1rm8k0.etzhayyim.com"],
			],
		});
		const fwd = fetchMock.mock.calls[0][1].headers as Record<string, string>;
		expect(fwd["authorization"]).toBe("Bearer x");
		expect(fwd["x-etzhayyim-org-id"]).toBe("org1");
		expect(fwd["atproto-proxy"]).toBe("did:web:appview");
		expect(fwd["cookie"]).toBeUndefined();
		expect(fwd["host"]).toBeUndefined();
	});

	it("attaches x-internal-trust when dispatcherSecret given", async () => {
		fetchMock.mockResolvedValueOnce(new Response("{}", { status: 200 }));
		await dispatchToBpmn({
			bpmnUrl: "https://dispatcher.test",
			nsid: NSID,
			args: {},
			headers: [],
			dispatcherSecret: "shared-secret",
		});
		const fwd = fetchMock.mock.calls[0][1].headers as Record<string, string>;
		expect(fwd["x-internal-trust"]).toBe("shared-secret");
	});

	it("returns null on network error (caller falls through)", async () => {
		fetchMock.mockRejectedValueOnce(new Error("ECONNREFUSED"));
		const result = await dispatchToBpmn({
			bpmnUrl: "https://dispatcher.test",
			nsid: NSID,
			args: {},
			headers: [],
		});
		expect(result).toBeNull();
	});
});
