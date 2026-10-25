// SVELTEKIT-BACKEND-PRESERVED: moved out of svelte/ during the cljs migration; not wired.
//
// Moved verbatim (only this header comment was added; the code below is
// byte-for-byte from before the move) from
// `svelte/src/routes/xrpc/[...path]/+server.ts`, the SvelteKit server-route
// handler that this repo's wrangler.jsonc `main` pointed at before this
// migration (via `svelte/.svelte-kit/cloudflare/_worker.js`, SvelteKit's
// build output for this file). It proxied any `/xrpc/<nsid>` request to the
// AgentGateway MCP router (`AGENTGATEWAY_MCP_ROUTER_URL`) as a JSON-RPC
// `tools/call`.
//
// This migration repoints wrangler.jsonc's `main` at `src/app.ts` instead
// (see that file and this repo's wrangler.jsonc header comment) because
// `src/app.ts` — unlike this file before it — calls `env.ASSETS.fetch`, so
// it can serve both the cljs static bundle and its own `/xrpc/` routes.
// `src/app.ts` already has its own `/xrpc/com.etzhayyim.apps.meet.*` handler
// that proxies to `DISPATCHER_URL`, which is a *different* mechanism than
// this file's `/xrpc/[...path]` → MCP-router proxy: different upstream,
// different envelope (JSON-RPC `tools/call` here vs. a plain JSON POST
// there). This file's mechanism is not reachable through the deployed
// Worker after this migration.
//
// It still imports from '@sveltejs/kit' and './$types' (SvelteKit's
// codegen'd route types), neither of which resolves now that the SvelteKit
// toolchain (`svelte/`) has been removed, so this file will NOT run as-is.
// Whether to revive it — e.g. rewritten as a plain Worker fetch handler and
// wired into `src/app.ts` — is an open product decision this migration does
// not make.
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
