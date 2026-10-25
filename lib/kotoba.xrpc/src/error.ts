// error.ts — Unified XRPC error types and response handlers.

/** AT Protocol / W Protocol XRPC error (wire format). */
export interface WRPCError {
  error: string;
  message: string;
  status: number;
}

/** XRPC response wrapper — all transports return this shape. */
export interface XrpcResponse<T = unknown> {
  ok: boolean;
  status: number;
  data: T;
  error?: WRPCError;
}

/** Parse a fetch Response into XrpcResponse. */
export async function parseResponse<T>(res: Response, nsid: string): Promise<XrpcResponse<T>> {
  if (!res.ok) {
    let errBody: Partial<WRPCError> = {};
    try { errBody = await res.json(); } catch { /* ignore parse errors */ }
    return {
      ok: false,
      status: res.status,
      data: undefined as T,
      error: {
        error: errBody.error ?? "XRPCError",
        message: errBody.message ?? (errBody.error ? `${nsid}: ${errBody.error}` : `${nsid}: HTTP ${res.status}`),
        status: res.status,
      },
    };
  }
  if (res.status === 200 && res.headers.get("content-length") === "0") {
    return { ok: true, status: 200, data: {} as T };
  }
  const data = await res.json() as T;
  return { ok: true, status: res.status, data };
}

/** Extract data or throw WRPCError (client/SDK pattern). */
export async function throwOnError<T>(p: Promise<XrpcResponse<T>>): Promise<T> {
  const r = await p;
  if (!r.ok) {
    throw r.error ?? { error: "XRPCError", message: `HTTP ${r.status}`, status: r.status };
  }
  return r.data;
}

// Pruned 2026-04-23 (zero external consumers):
// - okResponse / errResponse: constructors were inline-only inside xrpc
// - nullOnError: SSR-only helper; SSR transport itself was pruned
// - withSessionRefresh: browser-only retry helper; browser uses @atproto/api now
