import type { FueleconomyHandle } from "./tools.js";

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

export function createDefaultFueleconomyHandle(opts: DefaultHandleOptions): FueleconomyHandle {
  const baseUrl = opts.baseUrl.endsWith("/") ? opts.baseUrl : opts.baseUrl + "/";
  const handle: FueleconomyHandle = {
  async download_vehicles_csv(input) {
    const inp = input as Record<string, unknown>;
    const pathKeys: ReadonlySet<string> = new Set<string>([]);
    const queryKeys: ReadonlySet<string> = new Set<string>([]);
    const bodyKeys: ReadonlySet<string> = new Set<string>([]);
    let path = "/feg/epadata/vehicles.csv";
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
    const bodyObj: Record<string, unknown> | undefined = undefined;
    const init: RequestInit = {
      method: "GET",
      headers: {
        "User-Agent": "etzhayyim-yorishiro-fueleconomy-mcp/0.1",
        
        ...(opts.headers ?? {}),
      },
      
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
