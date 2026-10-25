// Bluesky Search Ingest thin edge (ADR-2604282300).
//
// Business logic moved to:
//   - BPMN: etzhayyim-root/00-contracts/bpmn/com/etzhayyim/bluesky/{ingestActor,refreshStalest}.bpmn
//   - Python LangServer: kotodama.ingest.bluesky
//
// This Worker now only exposes health/meta and preserves the legacy manual
// XRPC endpoint by forwarding to dispatcher.etzhayyim.com.

interface SecretBinding {
  get(): Promise<string>;
}

interface Env {
  DISPATCHER_URL?: string;
  DISPATCHER_INTERNAL_SECRET?: string | SecretBinding;
  BLUESKY_APPVIEW?: string;
  INGEST_ENABLED?: string;
  REFRESH_BATCH_SIZE?: string;
  APP_NANOID?: string;
}

const ACTOR_DID = "did:web:bluesky.etzhayyim.com";
const INGEST_NSID = "com.etzhayyim.apps.bluesky.ingestActor";

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);

    if (url.pathname === "/health" || url.pathname === "/_app/meta") {
      return json({
        ok: true,
        actor: ACTOR_DID,
        nanoid: env.APP_NANOID ?? "bsky1ngs",
        appview: env.BLUESKY_APPVIEW ?? "https://public.api.bsky.app",
        ingestEnabled: env.INGEST_ENABLED === "1",
        execution: "edge-proxy+agentgateway-mcp+langserver",
        businessLogic: "40-engine/kotoba/crates/kotoba-kotodama/py/src/kotodama/ingest/bluesky.py",
        bpmn: [
          "etzhayyim-root/00-contracts/bpmn/com/etzhayyim/bluesky/ingestActor.bpmn",
          "etzhayyim-root/00-contracts/bpmn/com/etzhayyim/bluesky/refreshStalest.bpmn",
        ],
        adr: "ADR-0037, ADR-2604282300",
      });
    }

    if (url.pathname === `/xrpc/${INGEST_NSID}` && req.method === "POST") {
      const actor = url.searchParams.get("actor");
      let body: Record<string, unknown> = {};
      try {
        const text = await req.text();
        body = text ? JSON.parse(text) : {};
      } catch (e) {
        return json({ ok: false, error: `invalid JSON body: ${e instanceof Error ? e.message : String(e)}` }, 400);
      }
      if (actor && !body.actor) body.actor = actor;
      if (!body.actor) return json({ ok: false, error: "actor param or JSON body.actor required" }, 400);
      if (!body.appview && env.BLUESKY_APPVIEW) body.appview = env.BLUESKY_APPVIEW;
      if (!body.nanoid && env.APP_NANOID) body.nanoid = env.APP_NANOID;
      return proxyToDispatcher(env, INGEST_NSID, body);
    }

    return new Response("Not Found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;

async function proxyToDispatcher(env: Env, nsid: string, body: Record<string, unknown>): Promise<Response> {
  const base = (env.DISPATCHER_URL ?? "https://dispatcher.etzhayyim.com").replace(/\/+$/, "");
  const headers: Record<string, string> = { "content-type": "application/json" };
  const trust = await internalTrustSecret(env);
  if (trust) headers["x-internal-trust"] = trust;

  const resp = await fetch(`${base}/xrpc/${nsid}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  const text = await resp.text();
  return new Response(text, {
    status: resp.status,
    headers: {
      "content-type": resp.headers.get("content-type") ?? "application/json",
      "cache-control": "no-store",
    },
  });
}

async function internalTrustSecret(env: Env): Promise<string> {
  const binding = env.DISPATCHER_INTERNAL_SECRET;
  if (!binding) return "";
  try {
    return typeof binding === "string" ? binding : await binding.get();
  } catch {
    return "";
  }
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}
