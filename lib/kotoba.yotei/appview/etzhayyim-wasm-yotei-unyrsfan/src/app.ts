// yotei.etzhayyim.com thin facade. Domain logic runs in AgentGateway MCP + pod-side LangServer workers.

type Env = {
  DISPATCHER_URL?: string;
  ASSETS?: { fetch(request: Request): Promise<Response> };
};

const ACTOR = {
  name: "yotei.etzhayyim.com",
  did: "did:web:yotei.etzhayyim.com",
  app: "yotei",
  nanoid: "unyrsfan",
};

const json = (body: unknown, init: ResponseInit = {}) =>
  new Response(JSON.stringify(body), {
    ...init,
    headers: { "content-type": "application/json", ...(init.headers ?? {}) },
  });

const embed = () =>
  new Response(`<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Yotei</title>
</head>
<body style="margin:0;background:#0a0a0a">
  <div id="app"></div>
  <script type="module">
    import('/js/app.js');
    window.parent?.postMessage({type:'etzhayyim:embed:ready',nanoid:'unyrsfan'},'*');
  </script>
</body>
</html>`, { headers: { "content-type": "text/html; charset=utf-8" } });

async function readBody(request: Request): Promise<Record<string, unknown>> {
  if (request.method === "GET" || request.method === "HEAD") {
    return Object.fromEntries(new URL(request.url).searchParams.entries());
  }
  const text = await request.text();
  if (!text) return {};
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

async function dispatch(env: Env, nsid: string, body: Record<string, unknown>, request: Request): Promise<Response> {
  const base = (env.DISPATCHER_URL ?? "https://dispatcher.etzhayyim.com").replace(/\/+$/, "");
  const headers = new Headers({ accept: "application/json", "content-type": "application/json" });
  const auth = request.headers.get("authorization");
  if (auth) headers.set("authorization", auth);
  const activeDid = request.headers.get("x-active-did");
  if (activeDid) headers.set("x-active-did", activeDid);
  const resp = await fetch(`${base}/xrpc/${nsid}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  const outHeaders = new Headers(resp.headers);
  outHeaders.set("access-control-allow-origin", "*");
  return new Response(resp.body, { status: resp.status, headers: outHeaders });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "access-control-allow-origin": "*",
          "access-control-allow-methods": "GET,POST,OPTIONS",
          "access-control-allow-headers": "authorization,content-type,x-active-did",
        },
      });
    }
    if (url.pathname === "/embed") return embed();
    if (url.pathname === "/health") return json({ ok: true, actor: ACTOR.name, did: ACTOR.did });
    if (url.pathname === "/_app/meta") return json(ACTOR);
    if (url.pathname.startsWith("/xrpc/")) {
      const nsid = url.pathname.slice("/xrpc/".length);
      if (!nsid.startsWith("com.etzhayyim.apps.yotei.")) return json({ error: "unsupported_nsid", nsid }, { status: 404 });
      return dispatch(env, nsid, await readBody(request), request);
    }
    if (env.ASSETS) return env.ASSETS.fetch(request);
    return json({ error: "not_found" }, { status: 404 });
  },
};
