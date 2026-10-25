// SVELTEKIT-BACKEND-PRESERVED: moved out of svelte/ during the cljs migration; not wired.
//
// Extracted verbatim (logic unchanged) from
//   svelte/src/routes/xrpc/[...path]/+server.ts
// during the Svelte -> ClojureScript frontend migration (see ../cljs/).
//
// This is backend/XRPC code, not frontend markup — it is a server-side route
// handler that proxies /xrpc/<nsid> calls to AGENTGATEWAY_MCP_ROUTER_URL as an
// MCP `tools/call` JSON-RPC request. The migration's scope was the frontend
// (the SvelteKit page under svelte/src/routes/+page.svelte, now
// ../cljs/src/site/app.cljs); backend TypeScript was to be left alone. It
// happened to live inside the now-deleted svelte/ tree, so it is moved here
// rather than deleted.
//
// STATUS: not wired to anything. It cannot run as-is:
//   - `import { json, type RequestEvent } from '@sveltejs/kit'` and
//     `import type { RequestHandler } from './$types'` are SvelteKit-only;
//     '@sveltejs/kit' is no longer a dependency of this repo and './$types'
//     was a generated SvelteKit artifact that no longer exists.
//   - Before this migration it only ran as part of the SvelteKit Cloudflare
//     adapter's built worker (`svelte/.svelte-kit/cloudflare/_worker.js`),
//     which `wrangler.jsonc`'s `main` pointed to. That `main` entry has been
//     removed as part of this migration (the frontend is now served as
//     static assets from `./cljs/public`, and `../src/app.ts` — the other,
//     documented dispatcher Worker — does not call `env.ASSETS.fetch()`, so
//     it cannot be substituted as `main` without something else serving the
//     assets).
//
// Whether to revive this AgentGateway MCP router proxy as a plain Workers
// fetch handler (mirroring the shape of ../src/app.ts, which is the
// Internet Clone Gateway dispatcher and has a completely different verb
// surface) is a product decision this migration does not make. It is
// recorded here, unmodified, so the next reader does not have to
// reconstruct it from git history.

import { json, type RequestEvent } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const DEFAULT_MCP_ROUTER_URL = 'https://mcp.etzhayyim.com/xrpc/com.etzhayyim.mcp.message';

type Env = Record<string, unknown> & { AGENTGATEWAY_MCP_ROUTER_URL?: string; MCP_ROUTER_URL?: string };
function envOf(event: RequestEvent): Env { return ((event.platform as { env?: Env } | undefined)?.env ?? {}) as Env; }
function mcpRouterUrl(env: Env): string { const configured = typeof env.AGENTGATEWAY_MCP_ROUTER_URL === 'string' && env.AGENTGATEWAY_MCP_ROUTER_URL.trim() ? env.AGENTGATEWAY_MCP_ROUTER_URL : typeof env.MCP_ROUTER_URL === 'string' && env.MCP_ROUTER_URL.trim() ? env.MCP_ROUTER_URL : DEFAULT_MCP_ROUTER_URL; return configured.replace(/\/+$/, ''); }
function noStore(body: unknown, init: ResponseInit = {}): Response { const headers = new Headers(init.headers); headers.set('cache-control', 'no-store'); return json(body, { ...init, headers }); }
export const POST: RequestHandler = async (event) => { const nsid = event.params.path; if (!nsid) return noStore({ error: 'Missing XRPC method' }, { status: 400 }); const input = await event.request.json().catch(() => ({})); const headers = new Headers(event.request.headers); headers.delete('host'); headers.set('content-type', 'application/json'); headers.set('x-etzhayyim-bff', 'sveltekit-edge-bff'); headers.set('x-etzhayyim-xrpc-method', nsid); const upstream = await fetch(mcpRouterUrl(envOf(event)), { method: 'POST', headers, body: JSON.stringify({ jsonrpc: '2.0', id: crypto.randomUUID(), method: 'tools/call', params: { name: nsid, arguments: input } }) }); const upstreamText = await upstream.text(); let payload: unknown = upstreamText; try { payload = upstreamText ? JSON.parse(upstreamText) : null; } catch { /* Preserve text payload. */ } if (!upstream.ok) return noStore({ error: 'MCP router request failed', upstream: payload }, { status: upstream.status }); if (payload && typeof payload === 'object' && 'error' in payload) { const error = (payload as { error?: { message?: string } }).error; return noStore({ error: error?.message ?? 'MCP router returned an error', upstream: payload }, { status: 502 }); } const result = payload && typeof payload === 'object' && 'result' in payload ? (payload as { result?: unknown }).result : payload; const structured = result && typeof result === 'object' && 'structuredContent' in result ? (result as { structuredContent?: unknown }).structuredContent : result; return noStore(structured ?? {}); };
export const OPTIONS: RequestHandler = async () => new Response(null, { status: 204, headers: { 'access-control-allow-origin': '*', 'access-control-allow-methods': 'POST,OPTIONS', 'access-control-allow-headers': 'content-type,authorization', 'access-control-max-age': '86400' } });
