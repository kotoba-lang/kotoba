// tasks.etzhayyim.com thin edge facade. OAuth/sync/cron run in AgentGateway MCP + pod-side LangServer.

interface SecretBinding { get(): Promise<string>; }
interface Env { ASSETS?: Fetcher; DISPATCHER_URL?: string; DISPATCHER_INTERNAL_SECRET?: string | SecretBinding; APP_NANOID?: string; }
const APP = "tasks";
const NSID_PREFIX = "com.etzhayyim.apps.tasks.";

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    if (url.pathname === "/health" || url.pathname === "/_app/meta") return json({ ok: true, actor: "did:web:tasks.etzhayyim.com", nanoid: env.APP_NANOID ?? "tasks-mcp", execution: "edge-proxy+agentgateway-mcp+langserver", businessLogic: "40-engine/kotoba/crates/kotoba-kotodama/py/src/kotodama/ingest/gworkspace_lite.py", bpmn: "etzhayyim-root/00-contracts/bpmn/com/etzhayyim/tasks" });
    if (url.pathname === "/oauth/callback") return htmlFromDispatcher(env, `${NSID_PREFIX}oauthCallback`, Object.fromEntries(url.searchParams));
    const nsid = url.pathname.startsWith("/xrpc/") ? url.pathname.slice("/xrpc/".length) : "";
    if (nsid.startsWith(NSID_PREFIX) && (req.method === "POST" || req.method === "GET")) {
      const body = await bodyWithQuery(req, url);
      if (body.__invalidJson) return json({ error: "InvalidJson" }, 400);
      return proxyToDispatcher(env, nsid, body);
    }
    if (env.ASSETS) return env.ASSETS.fetch(req);
    return json({ error: "NotFound", message: `${APP} not found` }, 404);
  },
} satisfies ExportedHandler<Env>;

async function bodyWithQuery(req: Request, url: URL): Promise<Record<string, unknown>> { let body: Record<string, unknown> = {}; if (req.method === "POST") { const text = await req.text(); try { body = text ? JSON.parse(text) : {}; } catch { return { __invalidJson: true }; } } for (const [k, v] of url.searchParams) if (!(k in body)) body[k] = v; return body; }
async function htmlFromDispatcher(env: Env, nsid: string, body: Record<string, unknown>): Promise<Response> { const r = await proxyToDispatcher(env, nsid, body); const text = await r.text(); let html = text; try { html = (JSON.parse(text) as { html?: string }).html ?? text; } catch {} return new Response(html, { status: r.status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } }); }
async function proxyToDispatcher(env: Env, nsid: string, body: Record<string, unknown>): Promise<Response> { const base = (env.DISPATCHER_URL ?? "https://dispatcher.etzhayyim.com").replace(/\/+$/, ""); const headers: Record<string, string> = { "content-type": "application/json" }; const trust = await internalTrustSecret(env); if (trust) headers["x-internal-trust"] = trust; const resp = await fetch(`${base}/xrpc/${nsid}`, { method: "POST", headers, body: JSON.stringify(body) }); const text = await resp.text(); return new Response(text, { status: resp.status, headers: { "content-type": resp.headers.get("content-type") ?? "application/json", "cache-control": "no-store" } }); }
async function internalTrustSecret(env: Env): Promise<string> { const binding = env.DISPATCHER_INTERNAL_SECRET; if (!binding) return ""; try { return typeof binding === "string" ? binding : await binding.get(); } catch { return ""; } }
function json(body: unknown, status = 200): Response { return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } }); }
