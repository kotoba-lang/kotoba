// mcp-registry-loader.test.ts — Unit tests for the Kysely-backed MCP
// manifest loader (ADR-2604261000).

import { describe, it, expect, beforeEach, vi } from "vitest";

// Mock createKyselyDb so the loader builds against a fake Kysely fluent
// chain instead of opening a real Hyperdrive connection.
const executeMock = vi.fn();
const whereMock = vi.fn();
const selectMock = vi.fn();
const selectFromMock = vi.fn();

function resetChain() {
	executeMock.mockReset();
	whereMock.mockReset().mockReturnValue({ where: whereMock, execute: executeMock });
	selectMock.mockReset().mockReturnValue({ where: whereMock });
	selectFromMock.mockReset().mockReturnValue({ select: selectMock });
}

// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
vi.mock("../src/kysely.js", () => ({
	createKyselyDb: () => ({ selectFrom: selectFromMock }),
}));

import {
	loadMcpManifestFromRegistry,
	clearMcpRegistryCache,
} from "../src/mcp-registry-loader.js";

const HYPERDRIVE = { __mock: true };
const ACTOR_DID = "did:web:lawfirm.etzhayyim.com";

beforeEach(() => {
	resetChain();
	clearMcpRegistryCache();
});

describe("loadMcpManifestFromRegistry", () => {
	it("returns mapped manifest from rows", async () => {
		executeMock.mockResolvedValueOnce([
			{
				nsid: "com.etzhayyim.apps.lawfirm.createCase",
				description: "Open a new client matter",
				input_schema: '{"type":"object","properties":{"domain":{"type":"string"}}}',
			},
			{
				nsid: "com.etzhayyim.apps.lawfirm.listMatters",
				description: "",
				input_schema: null,
			},
		]);

		const manifest = await loadMcpManifestFromRegistry({
			hyperdrive: HYPERDRIVE,
			actorDid: ACTOR_DID,
			appName: "lawfirm",
		});

		expect(manifest.appName).toBe("lawfirm");
		expect(manifest.mcpTools).toHaveLength(2);
		expect(manifest.mcpTools[0]).toMatchObject({
			name: "com.etzhayyim.apps.lawfirm.createCase",
			description: "Open a new client matter",
			inputSchema: { type: "object" },
		});
		expect(manifest.mcpTools[1].inputSchema).toEqual({ type: "object", properties: {}, required: [] });
		expect(manifest.knownNsids.has("com.etzhayyim.apps.lawfirm.createCase")).toBe(true);
		expect(manifest.knownNsids.has("com.etzhayyim.apps.lawfirm.listMatters")).toBe(true);
	});

	it("hits cache on second call within TTL", async () => {
		executeMock.mockResolvedValueOnce([
			{ nsid: "com.etzhayyim.apps.lawfirm.x", description: "", input_schema: null },
		]);

		await loadMcpManifestFromRegistry({ hyperdrive: HYPERDRIVE, actorDid: ACTOR_DID, appName: "lawfirm" });
		await loadMcpManifestFromRegistry({ hyperdrive: HYPERDRIVE, actorDid: ACTOR_DID, appName: "lawfirm" });

		expect(executeMock).toHaveBeenCalledTimes(1);
	});

	it("shares in-flight promise across concurrent callers", async () => {
		let resolve: (rows: unknown[]) => void = () => {};
		executeMock.mockImplementation(
			() => new Promise((r) => { resolve = r as never; }),
		);

		const p1 = loadMcpManifestFromRegistry({ hyperdrive: HYPERDRIVE, actorDid: ACTOR_DID, appName: "lawfirm" });
		const p2 = loadMcpManifestFromRegistry({ hyperdrive: HYPERDRIVE, actorDid: ACTOR_DID, appName: "lawfirm" });

		resolve([{ nsid: "com.etzhayyim.apps.lawfirm.y", description: "", input_schema: null }]);

		const [m1, m2] = await Promise.all([p1, p2]);
		expect(m1.mcpTools[0].name).toBe(m2.mcpTools[0].name);
		expect(executeMock).toHaveBeenCalledTimes(1);
	});

	it("noCache: true bypasses cache", async () => {
		executeMock.mockResolvedValue([
			{ nsid: "com.etzhayyim.apps.lawfirm.z", description: "", input_schema: null },
		]);

		await loadMcpManifestFromRegistry({ hyperdrive: HYPERDRIVE, actorDid: ACTOR_DID, appName: "lawfirm" });
		await loadMcpManifestFromRegistry({ hyperdrive: HYPERDRIVE, actorDid: ACTOR_DID, appName: "lawfirm", noCache: true });

		expect(executeMock).toHaveBeenCalledTimes(2);
	});

	it("rejects when actorDid is missing", async () => {
		await expect(
			loadMcpManifestFromRegistry({ hyperdrive: HYPERDRIVE, actorDid: "", appName: "lawfirm" }),
		).rejects.toThrow(/actorDid/);
	});

	it("rejects when hyperdrive is missing", async () => {
		await expect(
			loadMcpManifestFromRegistry({ hyperdrive: null, actorDid: ACTOR_DID, appName: "lawfirm" }),
		).rejects.toThrow(/HYPERDRIVE/);
	});

	it("falls back to empty schema when input_schema is invalid JSON", async () => {
		executeMock.mockResolvedValueOnce([
			{ nsid: "com.etzhayyim.apps.lawfirm.bad", description: "broken", input_schema: "{not-json" },
		]);

		const manifest = await loadMcpManifestFromRegistry({
			hyperdrive: HYPERDRIVE,
			actorDid: ACTOR_DID,
			appName: "lawfirm",
		});

		expect(manifest.mcpTools[0].inputSchema).toEqual({ type: "object", properties: {}, required: [] });
	});
});
