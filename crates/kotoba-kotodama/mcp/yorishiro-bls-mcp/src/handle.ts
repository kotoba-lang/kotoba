import type { BlsHandle } from "./tools.js";

export interface DefaultHandleOptions {
  /** Base URL of the kami. Defaults to the spec's servers[0].url at generate time. */
  baseUrl: string;
  /**
   * Extra headers to attach to every outbound request. The yorishiro
   * does NOT persist credentials — callers inject Authorization /
   * X-API-Key / etc per their own auth scope (e.g. an env var read at
   * the caller). User-Agent is set by the handle and is overridden by
   * any same-named entry here.
   */
  headers?: Record<string, string>;
}

export function createDefaultBlsHandle(opts: DefaultHandleOptions): BlsHandle {
  const baseUrl = opts.baseUrl.endsWith("/") ? opts.baseUrl : opts.baseUrl + "/";
  const handle: BlsHandle = {
  async fetch_timeseries(input) {
    const inp = input as Record<string, unknown>;
    const pathKeys: ReadonlySet<string> = new Set<string>([]);
    const queryKeys: ReadonlySet<string> = new Set<string>([]);
    const bodyKeys: ReadonlySet<string> = new Set<string>(["seriesid","startyear","endyear","registrationkey","catalog","calculations","annualaverage"]);
    let path = "/publicAPI/v2/timeseries/data/";
    for (const key of pathKeys) {
      const token = `{${key}}`;
      if (path.includes(token) && inp[key] !== undefined) {
        path = path.split(token).join(String(inp[key]));
      }
    }
    const url = new URL(path, baseUrl);
    for (const key of queryKeys) {
      const v = inp[key];
      if (v === undefined || v === null || v === "") continue;
      url.searchParams.append(key, String(v));
    }
    const bodyObj: Record<string, unknown> = {};
    for (const key of bodyKeys) {
      const v = inp[key];
      if (v !== undefined) bodyObj[key] = v;
    }
    const init: RequestInit = {
      method: "POST",
      headers: {
        "User-Agent": "etzhayyim-yorishiro-bls-mcp/0.1",
        "Content-Type": "application/json",
        ...(opts.headers ?? {}),
      },
      body: JSON.stringify(bodyObj),
    };
    try {
      const res = await fetch(url, init);
      const text = await res.text();
      let json: unknown = undefined;
      try { json = JSON.parse(text); } catch { /* not JSON, keep raw */ }
      return {
        httpStatus: res.status,
        ...(json !== undefined ? { json } : { body: text }),
        ...(res.ok ? {} : { error: text.slice(0, 1000) }),
      };
    } catch (err) {
      return { httpStatus: 0, error: (err as Error).message };
    }
  },
  };
  return handle;
}
