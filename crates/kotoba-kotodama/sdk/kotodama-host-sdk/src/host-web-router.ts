import { Hono } from "hono";
import { cors } from "hono/cors";
import { etag } from "hono/etag";
import { secureHeaders } from "hono/secure-headers";
import type { AppDef, ComAtprotoSyncSubscribeReposCommit } from "./types.js";
import type { App } from "./app.js";
import { dispatchMcp, type McpManifest, type McpMeter } from "./mcp-server.js";
import { buildOpenApiDocument } from "./openapi-facade.js";
import { checkBearerLxm } from "./tools-auth.js";
import { loadMcpManifestFromRegistry } from "./mcp-registry-loader.js";
import type { RouteConfig } from "@hono/zod-openapi";

/**
 * Optional MCP / OpenAPI facade bundle. Per-actor src/app.ts imports its own
 * generated tool-manifest (from `./generated/tool-manifest/{appName}.ts`) and
 * passes it in at SDK init. Tree-shakeable — apps that don't pass one get no
 * facade, no bundle cost.
 */
export interface McpFacadeConfig {
	appName: string;
	routes: readonly RouteConfig[];
	mcpTools: readonly McpManifest["mcpTools"][number][];
	/** Override server URL published in the OpenAPI spec (e.g. "https://lawfirm.etzhayyim.com"). */
	serverUrl?: string;
}

/**
 * ADR-2604261000: registry-backed MCP. Replaces the static `mcpFacade`
 * codegen path with a runtime SELECT from `vertex_mcp_tool_def`. When
 * supplied, `/mcp` is registered and the manifest is loaded per-request
 * (60s in-memory cache, see mcp-registry-loader.ts).
 *
 * `appName` is published in the MCP `serverInfo`. `actorDid` keys the
 * registry SELECT. Both default to env-derived values when omitted.
 *
 * Mutually exclusive with `mcpFacade`. If both are passed, `mcpRegistry`
 * wins and `mcpFacade.routes` is still used to publish OpenAPI 3.0
 * (codegen for OpenAPI is not in this ADR's scope).
 */
export interface McpRegistryConfig {
	appName?: string;
	actorDid?: string;
	/** Override server URL published in the OpenAPI spec. */
	serverUrl?: string;
	/**
	 * G4: opt out of BPMN dispatcher routing for this actor. Default behaviour
	 * is to consult `vertex_bpmn_lexicon_binding` per `tools/call` (60s cache)
	 * and forward to bpmn-dispatcher when a row exists. Set `false` to keep
	 * `tools/call` strictly in-process (debugging, edge cases).
	 */
	bpmnRouting?: boolean;
	/** ADR-2604271400: optional credits metering for `mcp_invoke`. */
	meter?: McpMeter;
	/**
	 * Extract caller user_id from the request for credits ledger.
	 * Required when `meter` is set. Return `undefined` to skip metering
	 * for this request (e.g. internal service calls).
	 */
	callerUserIdFromRequest?: (req: Request) => string | undefined;
}
// genkoEmbedHTML deprecated (2026-04-11) — Svelte appview is prod. draw mode falls through to SPA index.html.

interface HostWitExports {
  wHandler: {
    handleComAtprotoSyncSubscribeReposCommit(commit: ComAtprotoSyncSubscribeReposCommit): { tag: "ok" } | { tag: "err"; val: string };
  };
}

/**
 * Extract the `etzhayyim_session` cookie from request headers.
 * Used to inject session JWT as Authorization header for cross-subdomain SSO on *.etzhayyim.com.
 */
function extractSessionCookie(headers: Headers): string {
  const cookie = headers.get("cookie");
  if (!cookie) return "";
  const match = cookie.match(/(?:^|;\s*)etzhayyim_session=([^\s;]+)/);
  return match?.[1] ?? "";
}

/**
 * Collect request headers as [key, value] pairs for XRPC forwarding.
 * When no Authorization header is present but a `etzhayyim_session` cookie exists,
 * injects `Authorization: Bearer <jwt>` for cross-subdomain SSO on *.etzhayyim.com.
 */
function collectHeadersWithCookieAuth(raw: Headers): [string, string][] {
  const pairs: [string, string][] = [];
  let hasAuth = false;
  raw.forEach((v, k) => {
    pairs.push([k, v]);
    if (k.toLowerCase() === "authorization") hasAuth = true;
  });
  if (!hasAuth) {
    const jwt = extractSessionCookie(raw);
    if (jwt) pairs.push(["authorization", `Bearer ${jwt}`]);
  }
  return pairs;
}

function asBodyInit(bytes: Uint8Array): ArrayBuffer {
  return Uint8Array.from(bytes).buffer;
}

export function createHostWebRouter(args: {
  app: App;
  appDef: AppDef;
  env: Record<string, unknown>;
  witExports: HostWitExports;
  resolveSigningPublicMultikey(env: Record<string, unknown>): Promise<string>;
  /** ADR-0042: optional MCP + OpenAPI facade (codegen path). */
  mcpFacade?: McpFacadeConfig;
  /** ADR-2604261000: registry-backed MCP (Kysely SELECT from vertex_mcp_tool_def). */
  mcpRegistry?: McpRegistryConfig;
}): Hono {
  const { app, appDef, env, witExports, resolveSigningPublicMultikey, mcpFacade, mcpRegistry } = args;

  const router = new Hono();
  const ev = (k: string) => (env as any)[k] ?? "";

  router.onError((err, c) => {
    console.error(`[host-sdk] unhandled error on ${c.req.method} ${c.req.path}:`, err);
    return c.json(
      { error: "InternalServerError", message: err?.message?.slice(0, 200) || "unexpected error" },
      500,
    );
  });

  // Stable metadata endpoints: enable conditional requests + secure defaults.
  router.use("/.well-known/*", etag());
  router.use(
    "/.well-known/*",
    secureHeaders({
      // DID docs are intended to be publicly embeddable/readable by diverse clients.
      xFrameOptions: false,
    }),
  );
  router.use("/_app/meta", etag());
  router.use(
    "/_app/meta",
    secureHeaders({
      xFrameOptions: false,
    }),
  );

  router.get("/.well-known/did.json", async (c) => {
    const appNanoid = ev("APP_NANOID") || appDef.id;
    const appDID = ev("APP_DID") || ev("PERFORMER_DID") || `did:web:${appNanoid}.etzhayyim.com`;
    // ADR-2604231839: serviceEndpoint for this actor's own XRPC surface.
    // Matches the request origin (what the resolver fetched) so spec-compliant
    // clients can route Atproto-Proxy:<did>#etzhayyim_actor back to the same host.
    const selfOrigin = `${new URL(c.req.url).origin}`;
    const caps = (() => {
      try {
        const raw = ev("APP_CAPABILITIES");
        if (!raw) return [] as string[];
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed.map((v: unknown) => String(v)) : [];
      } catch { return [] as string[]; }
    })();
    const appVersion = ev("APP_VERSION");
    const publicKeyMultibase = await resolveSigningPublicMultikey(env);
    const verificationMethod = publicKeyMultibase ? [{
      id: `${appDID}#atproto`, type: "Multikey", controller: appDID, publicKeyMultibase,
    }] : [];
    const authentication = verificationMethod.length > 0 ? [`${appDID}#atproto`] : [];
    return c.json({
      "@context": ["https://www.w3.org/ns/did/v1", "https://w3id.org/security/multikey/v1"],
      id: appDID, verificationMethod, authentication,
      service: [
        {
          id: `${appDID}#atproto-pds`, type: "AtprotoPersonalDataServer",
          serviceEndpoint: "https://atproto.etzhayyim.com",
          ...(caps.length > 0 ? { capabilities: caps } : {}),
          ...(appVersion ? { version: appVersion } : {}),
        },
        {
          id: `${appDID}#etzhayyim_actor`, type: "etzhayyimActor",
          serviceEndpoint: selfOrigin,
        },
      ],
    }, 200, { "Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=300" });
  });

  router.get("/.well-known/atproto-did", (c) => {
    const appNanoid = ev("APP_NANOID") || appDef.id;
    const appDID = ev("APP_DID") || ev("PERFORMER_DID") || `did:web:${appNanoid}.etzhayyim.com`;
    return c.text(`${appDID}\n`, 200, {
      "Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=300",
    });
  });

  router.get("/_app/meta", (c) => {
    const caps = (() => { try { const r = ev("APP_CAPABILITIES"); return r ? JSON.parse(r) : []; } catch { return []; } })();
    const embedUrl = ev("APP_EMBED_URL");
    return c.json({
      appId: ev("APP_NANOID") || appDef.id,
      nanoid: ev("APP_NANOID") || appDef.id,
      displayName: ev("APP_DISPLAY_NAME") || appDef.name,
      description: ev("APP_DESCRIPTION") || appDef.description,
      uiMode: ev("APP_UI_TYPE") || "appview",
      uiType: ev("APP_UI_TYPE") || "appview",
      performerType: ev("APP_PERFORMER_TYPE") || "service",
      version: ev("APP_VERSION"), deploySha: ev("APP_DEPLOY_SHA"),
      capabilities: caps, tools: caps,
      ...(embedUrl ? { embedUrl, playUrl: embedUrl } : {}),
    }, 200, { "Access-Control-Allow-Origin": "*" });
  });

  const commitHandler = async (c: any) => {
    try {
      const commit = await c.req.json();
      const result = witExports.wHandler.handleComAtprotoSyncSubscribeReposCommit({
        seq: BigInt(commit.seq ?? 0), repo: commit.repo ?? "",
        collection: commit.collection ?? "", rkey: commit.rkey ?? "",
        action: commit.action ?? "", cid: commit.cid ?? null,
        rev: commit.rev ?? null, time: commit.time ?? "",
      });
      const ok = result.tag === "ok";
      return c.json(ok ? { ok: true } : { ok: false, error: (result as any).val }, ok ? 200 : 500);
    } catch (e: any) {
      return c.json({ ok: false, error: e?.message ?? "commit error" }, 500);
    }
  };
  router.post("/_commit", commitHandler);

  router.post("/_heartbeat", async (c) => {
    try {
      const result = await app.runDefaultHeartbeat();
      return c.json(result);
    } catch (e: any) {
      return c.json({ ok: false, error: e?.message ?? "heartbeat error" }, 500);
    }
  });

  // AT URI deep-link: /at/{authority}/{collection}/{rkey} → same appview HTML (client resolves)
  router.get("/at/*", async (c) => {
    // All modes (draw/appview) fall through to SPA index.html (Svelte is prod)
    if ((env as any).ASSETS) {
      const assets = (env as any).ASSETS as { fetch(req: Request | string): Promise<globalThis.Response> };
      try {
        const url = new URL(c.req.url);
        const indexResp = await assets.fetch(new URL("/index.html", url.origin).href);
        if (indexResp.status === 200) {
          return new globalThis.Response(indexResp.body, { status: 200, headers: { "Content-Type": "text/html;charset=utf-8" } });
        }
      } catch { /* fall through */ }
    }
    return c.json({ error: "not found" }, 404);
  });

  router.get("/", async (c) => {
    const uiType = ev("APP_UI_TYPE") || "appview";
    const embedMode = ev("APP_EMBED_MODE") || "";
    if (!c.req.query("embed")) {
      // No embed query — try ASSETS fallback (index.html, then APP_PLAY_URL)
      if ((env as any).ASSETS) {
        const assets = (env as any).ASSETS as { fetch(req: Request | string): Promise<globalThis.Response> };
        try {
          const assetsResp = await assets.fetch(c.req.raw);
          if (assetsResp.status !== 404) return assetsResp;
          const url = new URL(c.req.url);
          const indexResp = await assets.fetch(new URL("/index.html", url.origin).href);
          if (indexResp.status === 200) {
            return new globalThis.Response(indexResp.body, { status: 200, headers: { "Content-Type": "text/html;charset=utf-8" } });
          }
          // Fallback: APP_PLAY_URL (e.g. "isekai.htm") for game apps without index.html
          const playUrl = ev("APP_PLAY_URL");
          if (playUrl) {
            const playResp = await assets.fetch(new URL("/" + playUrl.replace(/^\//, ""), url.origin).href);
            if (playResp.status === 200) {
              return new globalThis.Response(playResp.body, { status: 200, headers: { "Content-Type": "text/html;charset=utf-8" } });
            }
          }
        } catch { /* fall through */ }
      }
      return c.json({ error: "not found" }, 404);
    }
    // appview with embed: render default card (SvelteKit removed)
    if (uiType === "appview") {
      const name = ev("APP_DISPLAY_NAME") || appDef.name || "App";
      const nid = ev("APP_NANOID") || appDef.id || "";
      const desc = ev("APP_DESCRIPTION") || appDef.description || "";
      const caps = (() => { try { return JSON.parse(ev("APP_CAPABILITIES") || "[]"); } catch { return []; } })();
      return c.html(appviewEmbedHTML(name, nid, desc, caps), 200, { "Access-Control-Allow-Origin": "*" });
    }
    if (uiType !== "game") {
      return c.json({
        appId: ev("APP_NANOID") || appDef.id,
        nanoid: ev("APP_NANOID") || appDef.id,
        displayName: ev("APP_DISPLAY_NAME") || appDef.name,
        description: ev("APP_DESCRIPTION") || appDef.description,
        uiType,
        embed: true,
      }, 200, { "Access-Control-Allow-Origin": "*" });
    }
    const name = ev("APP_DISPLAY_NAME") || appDef.name || "App";
    const nid = ev("APP_NANOID") || appDef.id || "";
    const desc = ev("APP_DESCRIPTION") || appDef.description || "";
    return c.html(embedHTML(name, nid, desc), 200, { "Access-Control-Allow-Origin": "*" });
  });

  router.get("/health", (c) => c.json({ status: "ok", app: appDef.id }));
  router.get("/healthz", (c) => c.json({ status: "ok", app: appDef.id }));

  // ── ADR-0042 + ADR-2604261000: MCP + OpenAPI facade ──
  // Two paths share the same /mcp endpoint:
  //   mcpRegistry (Kysely-backed) — DEFAULT; manifest loaded from
  //     vertex_mcp_tool_def per request (60s cache).
  //   mcpFacade   (codegen)        — legacy; manifest baked into bundle
  //     by gen-tool-manifest.mjs.
  // mcpRegistry wins when both are present. OpenAPI 3.0 is published only
  // when mcpFacade.routes is supplied (registry-side OpenAPI codegen is
  // out of scope for ADR-2604261000).
  if (mcpRegistry || mcpFacade) {
    const registryAppName = mcpRegistry?.appName
      || ev("APP_NANOID")
      || appDef.id
      || mcpFacade?.appName
      || "actor";
    // ADR-2604261000 §F1: prefer APP_ACTOR_HANDLE over APP_NANOID so the
    // default did:web:{handle}.etzhayyim.com matches sync-mcp-registry.py keying
    // (NSID 4th segment, e.g. "lawfirm"). etzhayyim deploy injects
    // APP_ACTOR_HANDLE from kotodama.jsonld profile.handle or component dir
    // slug etzhayyim-wasm-{slug}-{nanoid}.
    const registryActorDid = mcpRegistry?.actorDid
      || ev("APP_DID")
      || ev("PERFORMER_DID")
      || (ev("APP_ACTOR_HANDLE")
          ? `did:web:${ev("APP_ACTOR_HANDLE")}.etzhayyim.com`
          : `did:web:${ev("APP_NANOID") || appDef.id}.etzhayyim.com`);
    const facadeAppName = mcpFacade?.appName ?? registryAppName;

    router.use("/mcp", cors({ origin: "*", allowHeaders: ["authorization", "content-type"], allowMethods: ["GET", "POST", "OPTIONS"] }));

    router.post("/mcp", async (c) => {
      const rawBody = await c.req.text();
      const headers = collectHeadersWithCookieAuth(c.req.raw.headers);

      let manifest: McpManifest;
      if (mcpRegistry) {
        try {
          manifest = await loadMcpManifestFromRegistry({
            hyperdrive: (env as any).HYPERDRIVE,
            actorDid: registryActorDid,
            appName: registryAppName,
          });
        } catch (err: any) {
          return c.json(
            {
              jsonrpc: "2.0",
              id: null,
              error: { code: -32603, message: `mcp registry unavailable: ${err?.message ?? "unknown"}`.slice(0, 200) },
            },
            500,
          );
        }
      } else if (mcpFacade) {
        const knownNsids: ReadonlySet<string> = new Set(mcpFacade.mcpTools.map((t) => t.name));
        manifest = { appName: facadeAppName, mcpTools: mcpFacade.mcpTools, knownNsids };
      } else {
        return c.json({ error: "mcp not configured" }, 503);
      }

      // Routing guard: if tools/call, pre-check bearer lxm matches requested tool name.
      try {
        const peek = JSON.parse(rawBody) as { method?: string; params?: { name?: string } };
        if (peek?.method === "tools/call" && typeof peek.params?.name === "string") {
          const mismatch = checkBearerLxm(c.req.header("authorization"), peek.params.name);
          if (mismatch) return c.json(mismatch, 403);
        }
      } catch { /* JSON parse error is handled by dispatchMcp */ }

      // G4 (ADR-2604261000 follow-up): consult vertex_bpmn_lexicon_binding
      // per tools/call. When a row exists, forward to bpmn-dispatcher; on 5xx
      // / network error, fall through to in-process handleXRPC. Active when
      // mcpRegistry is in use and Hyperdrive binding is wired. Per-actor
      // opt-out via mcpRegistry.bpmnRouting === false.
      const bpmnRoutingEnabled = !!mcpRegistry
        && mcpRegistry.bpmnRouting !== false
        && !!(env as any).HYPERDRIVE;
      const dispatcherSecret = await (async () => {
        const sec = (env as any).SS_DISPATCHER_INTERNAL_SECRET ?? (env as any).DISPATCHER_INTERNAL_SECRET;
        if (!sec) return undefined;
        if (typeof sec === "string") return sec;
        if (typeof sec.get === "function") {
          try { return await sec.get(); } catch { return undefined; }
        }
        return undefined;
      })();
      const callerUserId = mcpRegistry?.callerUserIdFromRequest?.(c.req.raw);
      const response = await dispatchMcp(
        {
          app,
          manifest,
          headers,
          serverInfo: { name: `kotodama-${manifest.appName}`, version: ev("APP_VERSION") || "1.0.0" },
          bpmnRouter: bpmnRoutingEnabled
            ? {
                hyperdrive: (env as any).HYPERDRIVE,
                bpmnUrl: ev("BPMN_URL") || undefined,
                dispatcherSecret,
              }
            : undefined,
          meter: mcpRegistry?.meter,
          callerUserId,
        },
        rawBody,
      );
      if (response === null) return new globalThis.Response(null, { status: 202 });
      return c.json(response);
    });

    // SSE stream open — not supported; return 405 per MCP spec allowance.
    router.get("/mcp", (c) => c.text("", 405, { allow: "POST" }));

    if (mcpFacade) {
      const openApiDoc = buildOpenApiDocument({
        appName: mcpFacade.appName,
        routes: mcpFacade.routes,
        version: ev("APP_VERSION") || "1.0.0",
        serverUrl: mcpFacade.serverUrl ?? mcpRegistry?.serverUrl,
      });
      router.use("/.well-known/openapi.json", cors({ origin: "*" }));
      router.get("/.well-known/openapi.json", (c) => c.json(openApiDoc));
    }
  }

  router.post("/xrpc/:nsid", async (c) => {
    const headers = collectHeadersWithCookieAuth(c.req.raw.headers);
    const body = new Uint8Array(await c.req.arrayBuffer());
    const result = await app.handleXRPC("/xrpc/" + c.req.param("nsid"), headers, body);
    return new globalThis.Response(asBodyInit(result.body), { status: result.status, headers: result.headers });
  });

  router.get("/xrpc/:nsid", async (c) => {
    const nsid = c.req.param("nsid");
    if (!app.hasQuery(nsid)) {
      return c.json({ error: `xrpc method requires POST: ${nsid}` }, 405);
    }
    const headers = collectHeadersWithCookieAuth(c.req.raw.headers);
    const url = new URL(c.req.url);
    const payload = Object.fromEntries(url.searchParams.entries());
    const body = new TextEncoder().encode(JSON.stringify(payload));
    const result = await app.handleXRPC("/xrpc/" + nsid, headers, body);
    return new globalThis.Response(asBodyInit(result.body), { status: result.status, headers: result.headers });
  });

  router.post("/:methodName", async (c) => {
    const headers = collectHeadersWithCookieAuth(c.req.raw.headers);
    const body = new Uint8Array(await c.req.arrayBuffer());
    const result = await app.handleCommand(c.req.param("methodName"), headers, body);
    return new globalThis.Response(asBodyInit(result.body), { status: result.status, headers: result.headers });
  });

  // Static assets fallback: ASSETS binding → static assets → index.html
  router.notFound(async (c) => {
    if (c.req.method === "GET" && c.req.path.startsWith("/xrpc/")) {
      const nsid = c.req.path.replace(/^\/xrpc\//, "");
      if (!app.hasQuery(nsid)) {
        return c.json({ error: `xrpc method requires POST: ${nsid}` }, 405);
      }
      const headers = collectHeadersWithCookieAuth(c.req.raw.headers);
      const url = new URL(c.req.url);
      const payload = Object.fromEntries(url.searchParams.entries());
      const body = new TextEncoder().encode(JSON.stringify(payload));
      const result = await app.handleXRPC("/xrpc/" + nsid, headers, body);
      return new globalThis.Response(asBodyInit(result.body), { status: result.status, headers: result.headers });
    }

    if ((env as any).ASSETS) {
      const assets = (env as any).ASSETS as { fetch(req: Request | string): Promise<globalThis.Response> };
      try {
        const assetsResp = await assets.fetch(c.req.raw);
        if (assetsResp.status !== 404) return assetsResp;
        const url = new URL(c.req.url);
        const indexResp = await assets.fetch(new URL("/index.html", url.origin).href);
        if (indexResp.status === 200) {
          return new globalThis.Response(indexResp.body, { status: 200, headers: { "Content-Type": "text/html;charset=utf-8" } });
        }
      } catch { /* fall through */ }
    }
    return c.json({ error: "not found" }, 404);
  });

  return router;
}

// drawCanvasEmbedHTML removed (2026-04-11) — genkoEmbedHTML deprecated, Svelte appview is prod.
/**
 * Default appview embed card HTML — app name, description, and capability badges.
 * Used when uiType is "appview" and `?embed=1` is requested (SvelteKit fallthrough removed).
 */
function appviewEmbedHTML(name: string, nanoid: string, desc: string, caps: string[]): string {
  const capBadges = caps.map(c => `<span class="cap">${c}</span>`).join("");
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${name}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;background:#0d1117;color:#e6edf3;font-family:system-ui,-apple-system,sans-serif}
.card{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:100%;padding:24px;text-align:center;gap:12px}
.avatar{width:56px;height:56px;border-radius:14px;background:#21262d;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:700;color:#58a6ff}
h1{font-size:20px;font-weight:600}
p{font-size:14px;color:#8b949e;max-width:400px;line-height:1.5}
.caps{display:flex;flex-wrap:wrap;gap:6px;justify-content:center}
.cap{padding:4px 10px;border-radius:12px;background:#161b22;border:1px solid #30363d;font-size:12px;color:#8b949e}
</style></head><body>
<div class="card">
<div class="avatar">${name.slice(0, 2).toUpperCase()}</div>
<h1>${name}</h1>
<p>${desc}</p>
${capBadges ? `<div class="caps">${capBadges}</div>` : ""}
</div>
<script>window.parent?.postMessage({type:'etzhayyim:embed:ready',nanoid:'${nanoid}'},'*')</script>
</body></html>`;
}
/** KAMI Engine WebGPU embed HTML — dual canvas split view (VRM left, Hybrid right). */
function embedHTML(name: string, nanoid: string, _desc: string): string {
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${name}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}html,body{width:100%;height:100%;overflow:hidden;background:#0a0a0f;font-family:system-ui}
.split{display:flex;width:100%;height:100%}
.pane{flex:1;position:relative;overflow:hidden}
.pane+.pane{border-left:1px solid #222}
canvas{width:100%;height:100%;display:block}
.label{position:absolute;top:8px;left:8px;background:rgba(0,0,0,0.6);color:#e8e8f0;font-size:11px;padding:3px 8px;border-radius:4px;z-index:5;pointer-events:none}
.load{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#e8e8f0;background:#0a0a0f;z-index:10;transition:opacity .6s}
.load.done{opacity:0;pointer-events:none}
.sp{width:28px;height:28px;border:2px solid #222;border-top-color:#f472b6;border-radius:50%;animation:r .7s linear infinite}
@keyframes r{to{transform:rotate(360deg)}}
.nm{margin-top:.6rem;font-size:.75rem;opacity:.6}
.err{color:#f472b6;font-size:.7rem;padding:.5rem;text-align:center}
</style></head><body>
<div class="split">
  <div class="pane">
    <div class="label">FF Groups (6 SDF)</div>
    <div class="load" id="L1"><div class="sp"></div><div class="nm">Loading...</div></div>
    <canvas id="kami1"></canvas>
  </div>
  <div class="pane">
    <div class="label">Hybrid (SDF + 3DGS)</div>
    <div class="load" id="L2"><div class="sp"></div><div class="nm">Loading Hybrid...</div></div>
    <canvas id="kami2"></canvas>
  </div>
</div>
<div id="ver" style="position:fixed;bottom:8px;left:0;right:0;text-align:center;font-size:18px;font-weight:bold;color:#f472b6;z-index:20;pointer-events:none;text-shadow:0 1px 4px rgba(0,0,0,0.8)"></div>
<script type="module">
const WASM_VER='a59ae469';
const K='https://cdn.etzhayyim.com/kami-web/'+WASM_VER;
document.getElementById('ver').textContent='KAMI '+WASM_VER+' | ${nanoid} | '+new Date().toISOString().slice(0,19);
const O=location.origin;

async function loadPane(canvasId, loadId, sceneEndpoint, label) {
  const ld = document.getElementById(loadId);
  try {
    const {default:init, runEmbed} = await import(K+'/kamiWeb.js');
    // init is idempotent after first call
    try { await init(K+'/kamiWebBg.wasm'); } catch(e) { if (!String(e).includes('already')) throw e; }
    const r = await fetch(O+'/xrpc/'+sceneEndpoint, {method:'POST',headers:{'content-type':'application/json'},body:'{}'});
    if (!r.ok) throw new Error(label+' scene '+r.status);
    const d = await r.json();
    const sc = typeof d==='string' ? d : (d.scene ? JSON.stringify(d.scene) : JSON.stringify(d));
    await runEmbed(canvasId, sc);
    ld.classList.add('done');
  } catch(e) {
    console.error(label+':', e);
    ld.innerHTML = '<p class="err">'+label+': '+String(e)+'</p>';
  }
}

// Load both panes in parallel
await Promise.allSettled([
  loadPane('kami1', 'L1', 'GetScene', 'FF Groups'),
  loadPane('kami2', 'L2', 'GetScene', 'FF Groups (R)'),
]);

window.parent?.postMessage({type:'etzhayyim:embed:ready',nanoid:'${nanoid}'},'*');
</script></body></html>`;
}
