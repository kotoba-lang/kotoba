// SVELTEKIT-BACKEND-PRESERVED: moved out of svelte/ during the cljs migration; not wired.
//
// Moved verbatim from
// `svelte/src/routes/xrpc/[...path]/+server.ts`, the SvelteKit server-route
// file that was this repo's XRPC-to-MCP-router proxy (POST /xrpc/*
// forwards to AGENTGATEWAY_MCP_ROUTER_URL / MCP_ROUTER_URL as a JSON-RPC 2.0
// tools/call envelope). Only this header comment was added; the handler
// logic below is byte-for-byte unchanged.
//
// This migration's wrangler.jsonc drops `main` entirely (see that file's
// header comment): with `main` gone, this handler is not deployed from this
// config, and it still imports from '@sveltejs/kit' and './$types' — neither
// of which resolves now that the SvelteKit toolchain (`svelte/`) has been
// removed, so it will NOT run as-is. Whether/how to revive it (e.g. as a
// plain Cloudflare Worker fetch handler) is an open product decision, not
// made by this migration.
import { json, type RequestEvent } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const DEFAULT_MCP_ROUTER_URL = 'https://mcp.etzhayyim.com/xrpc/com.etzhayyim.mcp.message';

type Env = Record<string, unknown> & { AGENTGATEWAY_MCP_ROUTER_URL?: string; MCP_ROUTER_URL?: string };

function envOf(event: RequestEvent): Env { return ((event.platform as { env?: Env } | undefined)?.env ?? {}) as Env; }

function mcpRouterUrl(env: Env): string {
  const configured = typeof env.AGENTGATEWAY_MCP_ROUTER_URL === 'string' && env.AGENTGATEWAY_MCP_ROUTER_URL.trim()
    ? env.AGENTGATEWAY_MCP_ROUTER_URL
    : typeof env.MCP_ROUTER_URL === 'string' && env.MCP_ROUTER_URL.trim()
      ? env.MCP_ROUTER_URL
      : DEFAULT_MCP_ROUTER_URL;
  return configured.replace(/\/+$/, '');
}

function noStore(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers);
  headers.set('cache-control', 'no-store');
  return json(body, { ...init, headers });
}

export const POST: RequestHandler = async (event) => {
  const nsid = event.params.path;
  if (!nsid) return noStore({ error: 'Missing XRPC method' }, { status: 400 });
  const input = await event.request.json().catch(() => ({}));
  const headers = new Headers(event.request.headers);
  headers.delete('host');
  headers.set('content-type', 'application/json');
  headers.set('x-etzhayyim-bff', 'sveltekit-edge-bff');
  headers.set('x-etzhayyim-xrpc-method', nsid);
  const upstream = await fetch(mcpRouterUrl(envOf(event)), {
    method: 'POST',
    headers,
    body: JSON.stringify({ jsonrpc: '2.0', id: crypto.randomUUID(), method: 'tools/call', params: { name: nsid, arguments: input } })
  });
  const upstreamText = await upstream.text();
  let payload: unknown = upstreamText;
  try { payload = upstreamText ? JSON.parse(upstreamText) : null; } catch { /* Preserve text payload. */ }
  if (!upstream.ok) return noStore({ error: 'MCP router request failed', upstream: payload }, { status: upstream.status });
  if (payload && typeof payload === 'object' && 'error' in payload) {
    const error = (payload as { error?: { message?: string } }).error;
    return noStore({ error: error?.message ?? 'MCP router returned an error', upstream: payload }, { status: 502 });
  }
  const result = payload && typeof payload === 'object' && 'result' in payload ? (payload as { result?: unknown }).result : payload;
  const structured = result && typeof result === 'object' && 'structuredContent' in result ? (result as { structuredContent?: unknown }).structuredContent : result;
  return noStore(structured ?? {});
};

export const OPTIONS: RequestHandler = async () => new Response(null, {
  status: 204,
  headers: {
    'access-control-allow-origin': '*',
    'access-control-allow-methods': 'POST,OPTIONS',
    'access-control-allow-headers': 'content-type,authorization',
    'access-control-max-age': '86400'
  }
});
