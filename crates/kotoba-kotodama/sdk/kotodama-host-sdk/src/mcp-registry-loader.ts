// mcp-registry-loader.ts — Kysely-backed MCP tool manifest (ADR-2604261000).
//
// Replaces the build-time codegen manifest (`generated/tool-manifest/<app>.ts`)
// with a runtime SELECT from `vertex_mcp_tool_def`. Same downstream shape as
// `McpManifest` so `dispatchMcp` is unchanged.
//
// Runtime validation of `tools/call` arguments stays where it was: inside
// `app.handleXRPC` → handler → `parseLexiconInput(nsid, body)` against the
// generated `LEXICON_INPUT_SCHEMA` (separate codegen we still keep). The DB
// `input_schema` column is the MCP-published surface; the TS validator is
// runtime enforcement. Both come from the same lexicon JSON.
//
// Caching: a 60s in-memory cache per actor_did, keyed by Hyperdrive instance.
// First request after expiry refetches; concurrent requests share the
// in-flight promise to avoid N parallel SELECTs on cold cache.
//
// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
// See: 90-docs/adr/2604261000-mcp-registry-via-kysely-schema.md

import type { Kysely } from "kysely";
import { createKyselyDb } from "./kysely.js";
import type { McpManifest } from "./mcp-server.js";

interface VertexMcpToolDefRow {
	nsid: string;
	description: string | null;
	input_schema: string | null;
}

interface CachedManifest {
	manifest: McpManifest;
	expiresAt: number;
}

const CACHE_TTL_MS = 60_000;

// Cache key = actor_did. Per-isolate, not shared across Worker isolates.
const cache = new Map<string, CachedManifest>();
const inflight = new Map<string, Promise<McpManifest>>();

export interface LoadOptions {
	hyperdrive: unknown;
	actorDid: string;
	appName: string;
	/** Bypass cache (useful for tests). */
	noCache?: boolean;
}

function parseSchemaJson(raw: string | null): Record<string, unknown> {
	if (!raw) return { type: "object", properties: {}, required: [] };
	try {
		const parsed = JSON.parse(raw);
		return typeof parsed === "object" && parsed !== null
			? (parsed as Record<string, unknown>)
			: { type: "object", properties: {}, required: [] };
	} catch {
		return { type: "object", properties: {}, required: [] };
	}
}

async function fetchFromDb(opts: LoadOptions): Promise<McpManifest> {
	const db = createKyselyDb(opts.hyperdrive as never) as unknown as Kysely<{
		vertex_mcp_tool_def: VertexMcpToolDefRow & {
			actor_did: string;
			enabled: boolean | null;
		};
	}>;

	const rows = await db
		.selectFrom("vertex_mcp_tool_def")
		.select(["nsid", "description", "input_schema"])
		.where("actor_did", "=", opts.actorDid)
		.where((eb) =>
			eb.or([eb("enabled", "is", null), eb("enabled", "=", true)]),
		)
		.execute();

	if (rows.length === 0) {
		// 0 rows usually means actorDid mismatch with sync-mcp-registry.py keying.
		// Sync uses NSID 4th-segment slug → did:web:{slug}.etzhayyim.com (e.g.
		// did:web:lawfirm.etzhayyim.com), but env-default falls back to APP_NANOID
		// → did:web:{nanoid}.etzhayyim.com (e.g. did:web:lf1rm8k0.etzhayyim.com). When this
		// happens, set mcpRegistry: { actorDid: "did:web:{actorSlug}.etzhayyim.com" }
		// in createWorkerExport. See ADR-2604261000 §Pilot findings.
		console.warn(
			`[mcp-registry] 0 tools for actor_did=${opts.actorDid} (appName=${opts.appName}). ` +
				"Verify mcpRegistry.actorDid matches sync-mcp-registry.py keying " +
				"(typically did:web:{actorSlug}.etzhayyim.com from NSID 4th segment, not APP_NANOID).",
		);
	}

	const tools = rows.map((r) => ({
		name: r.nsid,
		description: r.description ?? "",
		inputSchema: parseSchemaJson(r.input_schema),
	}));
	const knownNsids: ReadonlySet<string> = new Set(tools.map((t) => t.name));
	return {
		appName: opts.appName,
		mcpTools: tools,
		knownNsids,
	};
}

/**
 * Load the per-actor MCP manifest from `vertex_mcp_tool_def`. Backed by a
 * 60s in-memory cache; concurrent calls share the in-flight promise.
 */
export async function loadMcpManifestFromRegistry(opts: LoadOptions): Promise<McpManifest> {
	if (!opts.actorDid) {
		throw new Error("loadMcpManifestFromRegistry: actorDid is required");
	}
	if (!opts.hyperdrive) {
		throw new Error("loadMcpManifestFromRegistry: env.HYPERDRIVE binding is required");
	}

	const key = opts.actorDid;
	const now = Date.now();

	if (!opts.noCache) {
		const hit = cache.get(key);
		if (hit && hit.expiresAt > now) return hit.manifest;
	}

	const existing = inflight.get(key);
	if (existing) return existing;

	const promise = (async () => {
		try {
			const manifest = await fetchFromDb(opts);
			cache.set(key, { manifest, expiresAt: Date.now() + CACHE_TTL_MS });
			return manifest;
		} finally {
			inflight.delete(key);
		}
	})();
	inflight.set(key, promise);
	return promise;
}

/** Test helper — drops the in-memory cache. */
export function clearMcpRegistryCache(): void {
	cache.clear();
	inflight.clear();
}
