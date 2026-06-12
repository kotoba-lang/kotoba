// mcp-server.ts — JSON-RPC 2.0 handler for Model Context Protocol (ADR-0042).
//
// Implements the server side of MCP Streamable HTTP transport for a single
// kotodama actor. Only the subset needed for LLM agent tool discovery + call:
//
//   initialize          → return protocol version + tools capability
//   notifications/initialized → no-op (client → server notification)
//   ping                → return {}
//   tools/list          → return MCP_TOOLS from manifest
//   tools/call          → delegate to app.handleXRPC("/xrpc/" + name, ...)
//
// The handler returns `application/json` (single response) per MCP spec. SSE
// streaming (progress notifications, long-running tools) is out of scope for
// PR 2 — CF Worker 30s execution limit makes long streams impractical.
//
// Authority / trust: bearer verification happens inside app.handleXRPC via the
// existing XRPC auth path (ADR-0022). The facade does a `lxm` routing guard
// via tools-auth.ts; signature check is downstream.

import type { App } from "./app.js";
import {
	dispatchToBpmn,
	lookupBpmnRoute,
	type BpmnDispatchResult,
	type BpmnRoute,
} from "./mcp-bpmn-router.js";

export interface McpTool {
	name: string;
	description: string;
	inputSchema: Record<string, unknown>;
}

export interface McpManifest {
	appName: string;
	mcpTools: readonly McpTool[];
	/** NSIDs present in the manifest — used to reject tools/call for unknown names. */
	knownNsids: ReadonlySet<string>;
}

/**
 * Optional BPMN routing config. When supplied, MCP `tools/call` checks
 * `vertex_bpmn_lexicon_binding` for the NSID and forwards to the
 * bpmn-dispatcher (Vultr VKE LangServer pool) instead of in-process
 * `app.handleXRPC`. On 5xx / network error from the dispatcher, falls
 * through to in-process so a broken dispatcher doesn't break the actor.
 *
 * Reuses the same env conventions as the PDS path
 * (`50-infra/cloudflare/workers/atproto/src/dispatch.ts`).
 *
 * G4 of ADR-2604261000 follow-up (1M-actor scale): "registry = data,
 * compute = shared FaaS via Zeebe ServiceTask".
 */
export interface BpmnRouterConfig {
	hyperdrive: unknown;
	bpmnUrl?: string;
	dispatcherSecret?: string;
}

/**
 * ADR-2604271400 — `mcp_invoke` action metering hook.
 *
 * Wraps `credits.etzhayyim.com` `CheckSpendAllowed` + `SpendCredits` so the host-sdk
 * has no direct dependency on the credits-mcp Worker. 10% public-fund
 * redistribution is handled inside `SpendCredits` (ADR — see
 * `20-actors/credits/CLAUDE.md`); this layer only reports byte counts and the
 * tool NSID. Optional — if unset, MCP `tools/call` runs unmetered (back-compat
 * for existing host-sdk consumers).
 */
export interface McpMeter {
	checkSpendAllowed(args: {
		userId: string;
		action: "mcp_invoke";
		toolNsid: string;
		payloadBytes: number;
	}): Promise<{ allowed: boolean; reason?: string }>;
	spendCredits(args: {
		userId: string;
		action: "mcp_invoke";
		toolNsid: string;
		actorDid: string;
		reqBytes: number;
		resBytes: number;
	}): Promise<void>;
}

export interface McpServerContext {
	app: App;
	manifest: McpManifest;
	/** HTTP headers from the incoming MCP request, forwarded to app.handleXRPC. */
	headers: [string, string][];
	serverInfo: { name: string; version: string };
	/** ADR-2604261000 G4: optional BPMN dispatcher routing for tools/call. */
	bpmnRouter?: BpmnRouterConfig;
	/** ADR-2604271400: optional `mcp_invoke` metering. */
	meter?: McpMeter;
	/** Caller user_id for credits ledger. Required when `meter` is set. */
	callerUserId?: string;
	/** Actor DID (this MCP server's actor) for SpendCredits metadata. */
	actorDid?: string;
}

type JsonRpcId = string | number | null;

interface JsonRpcRequest {
	jsonrpc: "2.0";
	id?: JsonRpcId;
	method: string;
	params?: unknown;
}

interface JsonRpcResponse {
	jsonrpc: "2.0";
	id: JsonRpcId;
	result?: unknown;
	error?: { code: number; message: string; data?: unknown };
}

// JSON-RPC error codes (MCP reuses standard codes).
const PARSE_ERROR = -32700;
const INVALID_REQUEST = -32600;
const METHOD_NOT_FOUND = -32601;
const INVALID_PARAMS = -32602;
const INTERNAL_ERROR = -32603;
// Implementation-defined (ADR-2604271400): caller has insufficient credits.
const INSUFFICIENT_CREDITS = -32010;

const MCP_PROTOCOL_VERSION = "2025-06-18";

export async function dispatchMcp(
	ctx: McpServerContext,
	rawBody: string,
): Promise<JsonRpcResponse | null> {
	let msg: JsonRpcRequest;
	try {
		msg = JSON.parse(rawBody);
	} catch {
		return errorResp(null, PARSE_ERROR, "invalid JSON");
	}
	if (!msg || msg.jsonrpc !== "2.0" || typeof msg.method !== "string") {
		return errorResp(msg?.id ?? null, INVALID_REQUEST, "malformed JSON-RPC request");
	}

	const id = msg.id ?? null;
	const isNotification = msg.id === undefined;

	try {
		switch (msg.method) {
			case "initialize":
				return resp(id, {
					protocolVersion: MCP_PROTOCOL_VERSION,
					capabilities: { tools: { listChanged: false } },
					serverInfo: ctx.serverInfo,
				});

			case "notifications/initialized":
				// Pure notification — no response.
				return null;

			case "ping":
				return resp(id, {});

			case "tools/list":
				return resp(id, { tools: ctx.manifest.mcpTools });

			case "tools/call": {
				if (isNotification) return null; // tools/call as notification is nonsensical
				const params = msg.params as { name?: unknown; arguments?: unknown } | undefined;
				const name = typeof params?.name === "string" ? params.name : "";
				if (!name) {
					return errorResp(id, INVALID_PARAMS, "missing params.name");
				}
				if (!ctx.manifest.knownNsids.has(name)) {
					return errorResp(id, METHOD_NOT_FOUND, `tool not registered: ${name}`);
				}
				const args = (params?.arguments ?? {}) as unknown;
				const bodyBytes = new TextEncoder().encode(JSON.stringify(args));

				// ADR-2604271400: `mcp_invoke` metering pre-check.
				if (ctx.meter && ctx.callerUserId) {
					const gate = await ctx.meter.checkSpendAllowed({
						userId: ctx.callerUserId,
						action: "mcp_invoke",
						toolNsid: name,
						payloadBytes: bodyBytes.byteLength,
					});
					if (!gate.allowed) {
						return errorResp(
							id,
							INSUFFICIENT_CREDITS,
							gate.reason ?? "insufficient credits for mcp_invoke",
						);
					}
				}

				// G4: try BPMN dispatcher first if configured + binding exists.
				// Falls through to in-process handleXRPC on no-binding or 5xx.
				let result: { body: Uint8Array; status: number } | null = null;
				if (ctx.bpmnRouter) {
					const route: BpmnRoute | null = await lookupBpmnRoute({
						hyperdrive: ctx.bpmnRouter.hyperdrive,
						nsid: name,
					});
					if (route) {
						const dispatched: BpmnDispatchResult | null = await dispatchToBpmn({
							bpmnUrl: ctx.bpmnRouter.bpmnUrl,
							nsid: name,
							args,
							headers: ctx.headers,
							timeoutMs: route.timeoutMs,
							dispatcherSecret: ctx.bpmnRouter.dispatcherSecret,
						});
						if (dispatched !== null) result = dispatched;
					}
				}
				if (result === null) {
					const xrpcResult = await ctx.app.handleXRPC(`/xrpc/${name}`, ctx.headers, bodyBytes);
					result = { body: xrpcResult.body, status: xrpcResult.status };
				}

				// ADR-2604271400: `mcp_invoke` metering post-charge. Bill on success
				// only; SpendCredits failure does not fail the MCP call (logged in
				// credits-mcp as af_event for follow-up).
				if (ctx.meter && ctx.callerUserId && result.status < 400) {
					try {
						await ctx.meter.spendCredits({
							userId: ctx.callerUserId,
							action: "mcp_invoke",
							toolNsid: name,
							actorDid: ctx.actorDid ?? "",
							reqBytes: bodyBytes.byteLength,
							resBytes: result.body.byteLength,
						});
					} catch (e) {
						console.error("[mcp_invoke] SpendCredits failed", e);
					}
				}

				const text = new TextDecoder().decode(result.body);
				const isError = result.status >= 400;
				return resp(id, {
					content: [{ type: "text", text }],
					isError,
				});
			}

			default:
				if (isNotification) return null;
				return errorResp(id, METHOD_NOT_FOUND, `method not found: ${msg.method}`);
		}
	} catch (err: unknown) {
		if (isNotification) return null;
		const message = err instanceof Error ? err.message : String(err);
		return errorResp(id, INTERNAL_ERROR, message.slice(0, 200));
	}
}

function resp(id: JsonRpcId, result: unknown): JsonRpcResponse {
	return { jsonrpc: "2.0", id, result };
}

function errorResp(id: JsonRpcId, code: number, message: string): JsonRpcResponse {
	return { jsonrpc: "2.0", id, error: { code, message } };
}
