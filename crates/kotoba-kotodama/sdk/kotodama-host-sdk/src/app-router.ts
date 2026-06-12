import { isWellFormedNsid, resolveXrpcMethod } from "@etzhayyim/xrpc/dispatch";
import { parseUrl, respondJson } from "./helpers.js";

export type HeaderPair = [string, string];

export interface BinaryHttpResponse {
  status: number;
  headers: HeaderPair[];
  body: Uint8Array;
}

export type MethodMap<TCtx> = Map<string, (ctx: TCtx, body: Uint8Array) => Promise<unknown> | unknown>;

function encodeResult(result: unknown): Uint8Array {
  if (result instanceof Uint8Array) return result;
  return new TextEncoder().encode(JSON.stringify(result));
}

export async function handleXrpcRoute<TCtx>(args: {
  path: string;
  headers: HeaderPair[];
  body: Uint8Array;
  methodMap: MethodMap<TCtx>;
  resolveContext(headers: HeaderPair[]): TCtx;
}): Promise<BinaryHttpResponse> {
  const nsid = args.path.replace(/^\/xrpc\//, "");
  // Reject malformed NSIDs early per AT Protocol spec (@atproto/syntax).
  // Well-formed-but-unknown → 404; malformed → 400 InvalidRequest.
  if (nsid.includes(".") && !isWellFormedNsid(nsid)) {
    return respondJson(400, { error: "InvalidRequest", message: `malformed xrpc nsid: ${nsid}` });
  }
  const ctx = args.resolveContext(args.headers);
  const handler = resolveXrpcMethod(nsid, args.methodMap);
  if (!handler) return respondJson(404, { error: `unknown xrpc method: ${nsid}` });

  try {
    const result = await handler(ctx, args.body);
    return {
      status: 200,
      headers: [["content-type", "application/json"]],
      body: encodeResult(result),
    };
  } catch (e) {
    return respondJson(500, { error: String(e) });
  }
}

export async function handleCommandRoute<TCtx>(args: {
  methodName: string;
  headers: HeaderPair[];
  body: Uint8Array;
  methodMap: MethodMap<TCtx>;
  resolveContext(headers: HeaderPair[]): TCtx;
}): Promise<BinaryHttpResponse> {
  const handler = args.methodMap.get(args.methodName);
  if (!handler) return respondJson(404, { error: "not found" });
  const ctx = args.resolveContext(args.headers);
  try {
    const result = await handler(ctx, args.body);
    return {
      status: 200,
      headers: [["content-type", "application/json"]],
      body: encodeResult(result),
    };
  } catch (e) {
    return respondJson(500, { error: String(e) });
  }
}

export async function handleHttpRoute<TCtx>(args: {
  method: string;
  url: string;
  headers: HeaderPair[];
  body: Uint8Array;
  appId: string;
  methodMap: MethodMap<TCtx>;
  resolveContext(headers: HeaderPair[]): TCtx;
}): Promise<BinaryHttpResponse> {
  const parsed = parseUrl(args.url);

  if (parsed.path === "/health" || parsed.path === "/healthz") {
    return respondJson(200, { status: "ok", app: args.appId });
  }

  if (args.method === "POST" && parsed.path.startsWith("/xrpc/")) {
    return handleXrpcRoute({
      path: parsed.path,
      headers: args.headers,
      body: args.body,
      methodMap: args.methodMap,
      resolveContext: args.resolveContext,
    });
  }

  if (args.method === "POST") {
    const methodName = parsed.path.replace(/^\//, "");
    return handleCommandRoute({
      methodName,
      headers: args.headers,
      body: args.body,
      methodMap: args.methodMap,
      resolveContext: args.resolveContext,
    });
  }

  return respondJson(404, { error: "not found" });
}
