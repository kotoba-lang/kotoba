// SVELTEKIT-BACKEND-PRESERVED: moved out of svelte/ during the cljs migration; not wired.
//
// Moved verbatim (only this header comment added) from
// `svelte/src/routes/xrpc/[...path]/+server.ts`, the SvelteKit server-route
// file that was the actual deployed XRPC handler under the old
// `wrangler.jsonc` `main` (which pointed at the SvelteKit Cloudflare
// adapter build output, `svelte/.svelte-kit/cloudflare/_worker.js`). It
// proxies an XRPC method call (any nsid under `/xrpc/*`) to the AgentGateway
// MCP router at `AGENTGATEWAY_MCP_ROUTER_URL` via JSON-RPC `tools/call`.
//
// This repo already has a separate, non-Svelte production Worker facade at
// `src/app.ts` — it implements the 6 `com.etzhayyim.apps.meetingRecorder.*`
// XRPC procedures directly (joinMeeting / leaveMeeting / getSession /
// listSessions / getTranscript / getMinutes) with its own consent/HMAC/DID
// auth, and dispatches to the Vultr media-plane, not to the MCP router this
// file proxies to. `src/app.ts` does NOT call `env.ASSETS.fetch(...)`
// anywhere, so this migration's wrangler.jsonc drops the `main` key
// entirely (see that file's header comment) rather than pointing `main` at
// either Worker — neither of them currently serves the static asset bundle.
//
// This file is NOT wired into wrangler.jsonc as `main`. It still imports
// from `@sveltejs/kit` and `./$types`, neither of which resolves now that
// the SvelteKit toolchain (`svelte/`) has been removed, so it will not run
// as-is. Whether to revive it (e.g. as a `/xrpc/*` catch-all fallback ahead
// of or behind `src/app.ts`'s own routes, reconciling the two upstreams) is
// an open product decision, not made here.
import { json, type RequestEvent } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

const DEFAULT_MCP_ROUTER_URL = 'https://mcp.etzhayyim.com/xrpc/com.etzhayyim.mcp.message';

type Env = Record<string, unknown> & { AGENTGATEWAY_MCP_ROUTER_URL?: string; MCP_ROUTER_URL?: string };
function envOf(event: RequestEvent): Env { return ((event.platform as { env?: Env } | undefined)?.env ?? {}) as Env; }
function mcpRouterUrl(env: Env): string { const configured = typeof env.AGENTGATEWAY_MCP_ROUTER_URL === 'string' && env.AGENTGATEWAY_MCP_ROUTER_URL.trim() ? env.AGENTGATEWAY_MCP_ROUTER_URL : typeof env.MCP_ROUTER_URL === 'string' && env.MCP_ROUTER_URL.trim() ? env.MCP_ROUTER_URL : DEFAULT_MCP_ROUTER_URL; return configured.replace(/\/+$/, ''); }
function noStore(body: unknown, init: ResponseInit = {}): Response { const headers = new Headers(init.headers); headers.set('cache-control', 'no-store'); return json(body, { ...init, headers }); }
export const POST: RequestHandler = async (event) => { const nsid = event.params.path; if (!nsid) return noStore({ error: 'Missing XRPC method' }, { status: 400 }); const input = await event.request.json().catch(() => ({})); const headers = new Headers(event.request.headers); headers.delete('host'); headers.set('content-type', 'application/json'); headers.set('x-etzhayyim-bff', 'sveltekit-edge-bff'); headers.set('x-etzhayyim-xrpc-method', nsid); const upstream = await fetch(mcpRouterUrl(envOf(event)), { method: 'POST', headers, body: JSON.stringify({ jsonrpc: '2.0', id: crypto.randomUUID(), method: 'tools/call', params: { name: nsid, arguments: input } }) }); const upstreamText = await upstream.text(); let payload: unknown = upstreamText; try { payload = upstreamText ? JSON.parse(upstreamText) : null; } catch { /* Preserve text payload. */ } if (!upstream.ok) return noStore({ error: 'MCP router request failed', upstream: payload }, { status: upstream.status }); if (payload && typeof payload === 'object' && 'error' in payload) { const error = (payload as { error?: { message?: string } }).error; return noStore({ error: error?.message ?? 'MCP router returned an error', upstream: payload }, { status: 502 }); } const result = payload && typeof payload === 'object' && 'result' in payload ? (payload as { result?: unknown }).result : payload; const structured = result && typeof result === 'object' && 'structuredContent' in result ? (result as { structuredContent?: unknown }).structuredContent : result; return noStore(structured ?? {}); };
export const OPTIONS: RequestHandler = async () => new Response(null, { status: 204, headers: { 'access-control-allow-origin': '*', 'access-control-allow-methods': 'POST,OPTIONS', 'access-control-allow-headers': 'content-type,authorization', 'access-control-max-age': '86400' } });
