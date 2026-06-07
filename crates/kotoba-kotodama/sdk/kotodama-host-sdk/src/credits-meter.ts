// credits-meter.ts — `McpMeter` factory for ADR-2604271400.
//
// Implements `checkSpendAllowed` + `spendCredits` by calling the credits-mcp
// XRPC endpoints. Supports two transport modes (mirroring XrpcClient):
//
//   Service binding (preferred, zero-RTT):
//     env.CREDITS_SERVICE is a CF Worker service binding (Fetcher)
//
//   HTTP (fallback):
//     env.CREDITS_MCP_URL is "https://credits.etzhayyim.com" (or staging URL)
//
// Usage in src/app.ts:
//
//   import { createCreditsMeter, createWorkerExport } from "@etzhayyim/kotodama-host-sdk";
//
//   export default createWorkerExport((sdk) => {
//     // wire mcpRegistry with meter opt-in
//   }, { mcpRegistry: { meter: (env) => createCreditsMeter(env) } });
//
// The factory is intentionally dependency-free (no import from XrpcClient) so
// it can be used in contexts where the full SDK is not available.

import type { McpMeter } from "./mcp-server.js";

type Fetcher = { fetch(input: RequestInfo, init?: RequestInit): Promise<Response> };

export interface CreditsMeterEnv {
	/** CF Worker service binding to credits-mcp (preferred). */
	CREDITS_SERVICE?: Fetcher;
	/** HTTP base URL fallback: "https://credits.etzhayyim.com". */
	CREDITS_MCP_URL?: string;
	/** Service Auth bearer token for credits-mcp. */
	CREDITS_INTERNAL_TOKEN?: string;
}

const CHECK_NSID = "com.etzhayyim.apps.credits.checkSpendAllowed";
const SPEND_NSID = "com.etzhayyim.apps.credits.spendCredits";

async function xrpcPost(
	env: CreditsMeterEnv,
	nsid: string,
	body: unknown,
): Promise<unknown> {
	const payload = JSON.stringify(body);
	const headers: Record<string, string> = {
		"content-type": "application/json",
		accept: "application/json",
	};
	if (env.CREDITS_INTERNAL_TOKEN) {
		headers["authorization"] = `Bearer ${env.CREDITS_INTERNAL_TOKEN}`;
	}

	let res: Response;
	if (env.CREDITS_SERVICE) {
		res = await env.CREDITS_SERVICE.fetch(`/xrpc/${nsid}`, {
			method: "POST",
			headers,
			body: payload,
		});
	} else {
		const base = (env.CREDITS_MCP_URL ?? "https://credits.etzhayyim.com").replace(/\/$/, "");
		res = await fetch(`${base}/xrpc/${nsid}`, {
			method: "POST",
			headers,
			body: payload,
		});
	}

	if (!res.ok) {
		const text = await res.text().catch(() => "");
		throw new Error(`credits-mcp ${nsid} HTTP ${res.status}: ${text.slice(0, 120)}`);
	}
	return res.json();
}

/**
 * Creates an `McpMeter` that calls credits-mcp XRPC endpoints.
 *
 * Pass the result to `McpServerContext.meter` (via `McpRegistryConfig` or
 * `McpFacadeConfig`) to enable `mcp_invoke` metering on `tools/call`.
 *
 * @example
 * ```ts
 * import { createCreditsMeter } from "@etzhayyim/kotodama-host-sdk";
 *
 * export default createWorkerExport((sdk) => { ... }, {
 *   mcpRegistry: {
 *     meter: createCreditsMeter(sdk.env as CreditsMeterEnv),
 *     callerUserIdFromRequest: (req) => req.headers.get("x-etzhayyim-user-id") ?? undefined,
 *   },
 * });
 * ```
 */
export function createCreditsMeter(env: CreditsMeterEnv): McpMeter {
	return {
		async checkSpendAllowed({ userId, action, toolNsid, payloadBytes }) {
			try {
				const res = (await xrpcPost(env, CHECK_NSID, {
					userId,
					action,
					toolNsid,
					payloadBytes,
				})) as { allowed: boolean; reason?: string };
				return { allowed: res.allowed, reason: res.reason };
			} catch (e) {
				// On transport error, fail open so infra issues don't block all MCP calls.
				console.error("[credits-meter] checkSpendAllowed failed", e);
				return { allowed: true };
			}
		},

		async spendCredits({ userId, action, toolNsid, actorDid, reqBytes, resBytes }) {
			const res = (await xrpcPost(env, SPEND_NSID, {
				userId,
				action,
				toolNsid,
				actorDid,
				reqBytes,
				resBytes,
			})) as { txId?: string };
			void res; // caller doesn't need the txId; errors propagate
		},
	};
}
