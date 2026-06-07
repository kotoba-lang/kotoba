// host-dispatcher.test.ts — F-Plan Phase 1 end-to-end proof.
//
// Verifies the full path: generated client → HostDispatcher → legacy HostImports.
// This is the POC that Lexicon JSON can replace WIT as the contract SSoT for host
// capabilities. Validates representative generated capabilities end-to-end.

import { describe, it, expect, beforeEach } from "vitest";
import { createHostDispatcher } from "../src/host-dispatcher.js";
import {
	HOST_NSID,
	secretsGet,
	setHostDispatcher,
} from "../src/generated/host-client.js";
import { createMockHostImports } from "./mock-helpers.js";

describe("F-Plan Phase 1: Lexicon-as-Contract POC", () => {
	describe("generated NSID registry", () => {
		it("exposes representative host capabilities", () => {
			expect(HOST_NSID.secretsGet).toBe("com.etzhayyim.host.secrets.get");
			expect(HOST_NSID.llmConverse).toBe("com.etzhayyim.host.llm.converse");
		});
	});

	describe("secrets.get end-to-end (Lexicon → generated → dispatcher → hostImports)", () => {
		beforeEach(() => {
			// Reset dispatcher between tests to avoid cross-test leakage.
			setHostDispatcher({
				dispatch: async () => {
					throw new Error("dispatcher not installed");
				},
			});
		});

		it("returns { found: true, value } when the secret exists", async () => {
			const hostImports = createMockHostImports({
				secretsGet: (key: string) => (key === "API_KEY" ? "sk-test-123" : null),
			});
			setHostDispatcher(createHostDispatcher(hostImports));

			const result = await secretsGet({ key: "API_KEY" });

			expect(result).toEqual({ found: true, value: "sk-test-123" });
		});

		it("returns { found: false } when the secret is absent", async () => {
			const hostImports = createMockHostImports({
				secretsGet: () => null,
			});
			setHostDispatcher(createHostDispatcher(hostImports));

			const result = await secretsGet({ key: "MISSING" });

			expect(result).toEqual({ found: false });
		});

		it("throws for truly unknown NSIDs", async () => {
			const hostImports = createMockHostImports();
			const dispatcher = createHostDispatcher(hostImports);

			await expect(
				dispatcher.dispatch("com.etzhayyim.host.nonexistent.method", {}),
			).rejects.toThrow(/unknown NSID/);
		});
	});

	describe("Phase 2 coverage — capability groups", () => {
		beforeEach(() => {
			setHostDispatcher({
				dispatch: async () => {
					throw new Error("dispatcher not installed");
				},
			});
		});

		it("core.configGet routes to hostImports.configGet", async () => {
			const hostImports = createMockHostImports({
				configGet: (key: string) => (key === "NODE_ENV" ? "production" : undefined),
			});
			const dispatcher = createHostDispatcher(hostImports);

			const result = await dispatcher.dispatch<{ value?: string }>(
				HOST_NSID.coreConfigGet,
				{ key: "NODE_ENV" },
			);
			expect(result).toEqual({ value: "production" });

			const missing = await dispatcher.dispatch<{ value?: string }>(
				HOST_NSID.coreConfigGet,
				{ key: "MISSING" },
			);
			expect(missing).toEqual({});
		});

		it("authz.enforce returns { allowed: true } on success", async () => {
			let enforceCalled = false;
			const hostImports = createMockHostImports({
				authzEnforce: () => {
					enforceCalled = true;
				},
			});
			const dispatcher = createHostDispatcher(hostImports);

			const result = await dispatcher.dispatch(HOST_NSID.authzEnforce, {
				orgId: "org1",
				role: "admin",
				permissions: ["read"],
				requiredPermissions: ["read"],
				requiredRoles: ["admin"],
			});
			expect(result).toEqual({ allowed: true });
			expect(enforceCalled).toBe(true);
		});

		it("lock.tryLock passes BigInt TTL to hostImports", async () => {
			let receivedTtl: bigint | null = null;
			const hostImports = createMockHostImports({
				lockTryLock: (_key: string, ttl: bigint) => {
					receivedTtl = ttl;
					return true;
				},
			});
			const dispatcher = createHostDispatcher(hostImports);

			const result = await dispatcher.dispatch(HOST_NSID.lockTryLock, {
				key: "resource:42",
				ttlMs: 30000,
			});
			expect(result).toEqual({ acquired: true });
			expect(receivedTtl).toBe(30000n);
		});

		it("identity.resolve returns { did } when found, {} when null", async () => {
			const hostImports = createMockHostImports({
				identityResolve: (nanoid: string) =>
					nanoid === "abc123" ? "did:web:abc123.etzhayyim.com" : null,
			});
			const dispatcher = createHostDispatcher(hostImports);

			expect(
				await dispatcher.dispatch(HOST_NSID.identityResolve, { nanoid: "abc123" }),
			).toEqual({ did: "did:web:abc123.etzhayyim.com" });
			expect(
				await dispatcher.dispatch(HOST_NSID.identityResolve, { nanoid: "missing" }),
			).toEqual({});
		});

		it("governance.registerManifest forwards manifestJson", async () => {
			let captured = "";
			const hostImports = createMockHostImports({
				governanceRegisterManifest: (json: string) => {
					captured = json;
				},
			});
			const dispatcher = createHostDispatcher(hostImports);

			const result = await dispatcher.dispatch(HOST_NSID.governanceRegisterManifest, {
				manifestJson: '{"raci":[]}',
			});
			expect(result).toEqual({ ok: true });
			expect(captured).toBe('{"raci":[]}');
		});
	});

	describe("Coverage — every NSID has a dispatcher case", () => {
		it("no Phase 2 capability throws 'unknown NSID'", async () => {
			const hostImports = createMockHostImports();
			const dispatcher = createHostDispatcher(hostImports);
			const nsids = Object.values(HOST_NSID) as string[];

			for (const nsid of nsids) {
				try {
					// Minimal input; most mocks return noop values. We only assert the
					// dispatcher does NOT throw the 'unknown NSID' error — runtime errors
					// from empty input are fine (they mean the case exists and forwarded).
					await dispatcher.dispatch(nsid, {
						key: "",
						value: "",
						stream: "",
						subject: "",
						payload: "",
						token: "",
						orgId: "",
						role: "",
						permissions: [],
						requiredPermissions: [],
						requiredRoles: [],
						data: "",
						contentType: "",
						bucket: "",
						subdomain: "",
						path: "",
						name: "",
						level: "",
						message: "",
						attributesJson: "{}",
						tagsJson: "{}",
						entryJson: "{}",
						eventJson: "{}",
						topic: "",
						maxMessages: 0,
						ttlMs: 0,
						actorType: "",
						actorId: "",
						method: "",
						paramsJson: "{}",
						userMessage: "",
						llmContextJson: "{}",
						inputJson: "{}",
						taskJson: "{}",
						optionsJson: "{}",
						activitiesJson: "[]",
						batchId: "",
						timeoutMs: 0,
						nanoid: "",
						offset: 0,
						limit: 0,
						tag: null,
						status: null,
						participantsJson: "[]",
						sessionId: "",
						content: "",
						manifestJson: "{}",
						command: "",
						userId: "",
						did: "",
						params: "",
						sql: "",
						messages: [],
						value_: 0,
					});
				} catch (err) {
					const msg = (err as Error).message;
					if (/unknown NSID/.test(msg)) {
						throw new Error(`NSID ${nsid} is in HOST_NSID registry but not wired in host-dispatcher`);
					}
				}
			}
		});
	});
});
