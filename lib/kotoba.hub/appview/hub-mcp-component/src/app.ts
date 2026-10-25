// hub.etzhayyim.com — Integration Hub & API Gateway Platform
// Thin-edge dispatcher: business logic in AgentGateway MCP + pod-side LangServer.
// 8 methods: registerEndpoint / listEndpoints / routeRequest / getRouteStatus /
//            createWebhook / listWebhooks / testConnection / getMetrics

interface SecretBinding { get(): Promise<string>; }
interface Env {
  DISPATCHER_URL?: string;
  DISPATCHER_INTERNAL_SECRET?: string | SecretBinding;
  APP_NANOID?: string;
}
interface ExportedHandler<E> { fetch(req: Request, env: E): Promise<Response>; }

const NSID_PREFIX = "com.etzhayyim.apps.hub.";
const ACTOR_DID = "did:web:hub.etzhayyim.com";

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    if (url.pathname === "/health" || url.pathname === "/_app/meta") {
      return json({
        ok: true,
        actor: ACTOR_DID,
        nanoid: env.APP_NANOID ?? "n5t2lqyz",
        execution: "edge-proxy+agentgateway-mcp+langserver",
        bpmn: "60-apps/etzhayyim-project-hub/bpmn",
        methods: [
          "registerEndpoint", "listEndpoints", "routeRequest", "getRouteStatus",
          "createWebhook", "listWebhooks", "testConnection", "getMetrics",
        ],
      });
    }

    const nsid = url.pathname.startsWith("/xrpc/") ? url.pathname.slice("/xrpc/".length) : "";
    if (nsid.startsWith(NSID_PREFIX) && (req.method === "POST" || req.method === "GET")) {
      const body = await bodyWithQuery(req, url);
      if (body.__invalidJson) return json({ error: "InvalidJson" }, 400);
      return proxyToDispatcher(env, nsid, body);
    }

    return json({ error: "NotFound" }, 404);
  },
} satisfies ExportedHandler<Env>;

async function bodyWithQuery(req: Request, url: URL): Promise<Record<string, unknown>> {
  let body: Record<string, unknown> = {};
  if (req.method === "POST") {
    const text = await req.text();
    try { body = text ? (JSON.parse(text) as Record<string, unknown>) : {}; }
    catch { return { __invalidJson: true }; }
  }
  for (const [k, v] of url.searchParams.entries()) {
    if (!(k in body)) body[k] = v;
  }
  return body;
}

async function proxyToDispatcher(env: Env, nsid: string, body: Record<string, unknown>): Promise<Response> {
  const dispatcherUrl = env.DISPATCHER_URL ?? "https://dispatcher.etzhayyim.com";
  const secret = typeof env.DISPATCHER_INTERNAL_SECRET === "object"
    ? await env.DISPATCHER_INTERNAL_SECRET.get()
    : (env.DISPATCHER_INTERNAL_SECRET ?? "");
  const res = await fetch(`${dispatcherUrl}/xrpc/${nsid}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-internal-secret": secret },
    body: JSON.stringify(body),
  });
  const data = await res.text();
  return new Response(data, { status: res.status, headers: { "Content-Type": "application/json" } });
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
