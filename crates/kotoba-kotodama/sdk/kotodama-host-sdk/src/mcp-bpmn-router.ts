// mcp-bpmn-router.ts — Per-tool BPMN routing for MCP tools/call (G4 of the
// 1M-actor architecture: registry-decoupled-from-compute).
//
// When a `vertex_bpmn_lexicon_binding` row exists for an NSID, MCP `tools/call`
// is forwarded to the bpmn-dispatcher (Vultr VKE LangServer pool, ADR-0056) instead
// of the in-process `app.handleXRPC` path. Falls through to in-process when no
// binding exists, so existing T3 actors keep working unchanged.
//
// PDS already has equivalent logic at `50-infra/cloudflare/workers/atproto/src/
// dispatch.ts pipethroughBpmnDispatcher`. This module is the host-sdk side
// for per-actor /mcp endpoints (so a tool call doesn't have to round-trip
// through PDS just to reach the dispatcher).
//
// Cache: 60s per-NSID lookup result (positive AND negative — "no binding"
// is also cached so we don't hit the DB on every cold tool that lives
// in-process). Same TTL as mcp-registry-loader for consistency.
//
// Reuses the dispatcher URL convention from the PDS path:
//   env.BPMN_URL || "https://dispatcher.etzhayyim.com"
//
// On 5xx from dispatcher: returns null so the caller falls through to
// in-process handleXRPC. 4xx and timeouts surface verbatim.

// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import type { Kysely } from "kysely";
import { createKyselyDb } from "./kysely.js";

interface VertexBpmnLexiconBindingRow {
	nsid: string;
	bpmn_process_id: string;
	bpmn_version: number | null;
	result_timeout_ms: number | null;
	status: string | null;
}

export interface BpmnRoute {
	nsid: string;
	bpmnProcessId: string;
	timeoutMs: number;
}

const ROUTING_CACHE_TTL_MS = 60_000;
const DEFAULT_TIMEOUT_MS = 60_000;
const DEFAULT_BPMN_URL = "https://dispatcher.etzhayyim.com";

interface CachedRoute {
	route: BpmnRoute | null;
	expiresAt: number;
}

const routeCache = new Map<string, CachedRoute>();
const inflight = new Map<string, Promise<BpmnRoute | null>>();

export interface LookupOptions {
	hyperdrive: unknown;
	nsid: string;
	noCache?: boolean;
}

async function fetchRoute(opts: LookupOptions): Promise<BpmnRoute | null> {
	const db = createKyselyDb(opts.hyperdrive as never) as unknown as Kysely<{
		vertex_bpmn_lexicon_binding: VertexBpmnLexiconBindingRow;
	}>;

	const rows = await db
		.selectFrom("vertex_bpmn_lexicon_binding")
		.select(["nsid", "bpmn_process_id", "bpmn_version", "result_timeout_ms", "status"])
		.where("nsid", "=", opts.nsid)
		.where((eb) =>
			eb.or([eb("status", "is", null), eb("status", "=", "active")]),
		)
		.limit(1)
		.execute();

	if (rows.length === 0) return null;
	const r = rows[0];
	return {
		nsid: r.nsid,
		bpmnProcessId: r.bpmn_process_id,
		timeoutMs: r.result_timeout_ms ?? DEFAULT_TIMEOUT_MS,
	};
}

/**
 * Look up the BPMN route for an NSID. Returns null if no active binding
 * exists (caller should fall through to in-process handleXRPC). Cached for
 * 60s. Concurrent lookups for the same NSID share the in-flight promise.
 */
export async function lookupBpmnRoute(opts: LookupOptions): Promise<BpmnRoute | null> {
	if (!opts.nsid) return null;
	if (!opts.hyperdrive) return null;

	const now = Date.now();
	if (!opts.noCache) {
		const hit = routeCache.get(opts.nsid);
		if (hit && hit.expiresAt > now) return hit.route;
	}

	const existing = inflight.get(opts.nsid);
	if (existing) return existing;

	const promise = (async () => {
		try {
			const route = await fetchRoute(opts);
			routeCache.set(opts.nsid, { route, expiresAt: Date.now() + ROUTING_CACHE_TTL_MS });
			return route;
		} catch {
			// On DB error, cache a negative result for 5s so we don't loop
			// the cluster — but expire fast so a recovering DB unblocks.
			routeCache.set(opts.nsid, { route: null, expiresAt: Date.now() + 5_000 });
			return null;
		} finally {
			inflight.delete(opts.nsid);
		}
	})();
	inflight.set(opts.nsid, promise);
	return promise;
}

export interface BpmnDispatchOptions {
	bpmnUrl?: string;
	nsid: string;
	args: unknown;
	headers: [string, string][];
	timeoutMs?: number;
	dispatcherSecret?: string;
}

export interface BpmnDispatchResult {
	body: Uint8Array;
	status: number;
	headers: Record<string, string>;
}

const FORWARDED_HEADER_PREFIXES = ["x-etzhayyim-", "atproto-"];
const FORWARDED_HEADERS = new Set(["authorization", "content-type"]);

function buildForwardHeaders(
	incoming: [string, string][],
	dispatcherSecret: string | undefined,
): Record<string, string> {
	const out: Record<string, string> = { "content-type": "application/json" };
	for (const [k, v] of incoming) {
		const lk = k.toLowerCase();
		if (FORWARDED_HEADERS.has(lk) || FORWARDED_HEADER_PREFIXES.some((p) => lk.startsWith(p))) {
			out[lk] = v;
		}
	}
	if (dispatcherSecret) {
		out["x-internal-trust"] = dispatcherSecret;
	}
	return out;
}

/**
 * POST `args` to `{bpmnUrl}/xrpc/{nsid}`. Returns the dispatcher's response
 * verbatim. On 5xx, returns null so the caller can fall through to the
 * in-process handler (defense-in-depth, matches PDS path). 4xx surfaces
 * with the dispatcher's body and status. AbortController enforces timeout.
 */
export async function dispatchToBpmn(
	opts: BpmnDispatchOptions,
): Promise<BpmnDispatchResult | null> {
	const url = `${opts.bpmnUrl ?? DEFAULT_BPMN_URL}/xrpc/${opts.nsid}`;
	const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;
	const ctrl = new AbortController();
	const timer = setTimeout(() => ctrl.abort(), timeoutMs);

	try {
		const resp = await fetch(url, {
			method: "POST",
			headers: buildForwardHeaders(opts.headers, opts.dispatcherSecret),
			body: JSON.stringify(opts.args ?? {}),
			signal: ctrl.signal,
		});
		const text = await resp.text();
		// 5xx → null = fall through to in-process. 4xx → return verbatim.
		if (resp.status >= 500) return null;

		const ctype = resp.headers.get("content-type") || "application/json";
		// PDS unwraps `{ ok, variables }` from Zeebe — replicate so MCP
		// callers see the flat handler shape they would get from in-process.
		let bodyText = text;
		try {
			const parsed = JSON.parse(text) as Record<string, unknown>;
			if (parsed && parsed.ok === true && parsed.variables !== undefined) {
				bodyText = JSON.stringify(parsed.variables);
			}
		} catch {
			// non-JSON body — pass through
		}
		return {
			body: new TextEncoder().encode(bodyText),
			status: resp.status,
			headers: { "content-type": ctype },
		};
	} catch {
		// Network error / timeout / abort → fall through to in-process.
		return null;
	} finally {
		clearTimeout(timer);
	}
}

/** Test helper — drops the in-memory cache. */
export function clearBpmnRouteCache(): void {
	routeCache.clear();
	inflight.clear();
}
