// transport.ts — XRPC fetch abstraction for Worker-to-Worker calls.
// BrowserTransport / SSRTransport were pruned 2026-04-23 — browser-side calls
// go through `@atproto/api` via the wproto facade. SSR-style retry/timeout
// semantics collapse into BindingTransport when callers pass AbortSignal.

import type { AuthResolver } from "./auth.js";
import type { XrpcResponse } from "./error.js";
import { parseResponse } from "./error.js";

/** Cloudflare Workers Fetcher interface (service binding). */
export interface Fetcher {
  fetch(input: string | Request, init?: RequestInit): Promise<Response>;
}

/** XRPC call options. */
export interface XrpcCallOpts {
  method?: "GET" | "POST";
  auth?: AuthResolver;
  signal?: AbortSignal;
  timeout?: number;
  /** Query params (GET) or body (POST). */
  params?: Record<string, unknown>;
}

const PDS_INTERNAL = "https://pds.internal";
const PDS_PUBLIC = "https://atproto.etzhayyim.com";

/** Worker host transport: service binding (default) or HTTP fallback. */
export class BindingTransport {
  private binding: Fetcher;
  private _isServiceBinding: boolean;

  constructor(binding: Fetcher | null, private fallbackBase = PDS_PUBLIC) {
    if (binding && typeof binding.fetch === "function") {
      // Infra Worker with real service binding
      this.binding = binding;
      this._isServiceBinding = true;
    } else {
      // Dispatch namespace Worker: HTTP via dispatcher → PDS_SERVICE (standard path)
      this._isServiceBinding = false;
      this.binding = {
        fetch: (input: string | Request, init?: RequestInit) => {
          const url = typeof input === "string" ? input : input.url;
          const publicUrl = url
            .replace(`${PDS_INTERNAL}/xrpc/`, `${this.fallbackBase}/xrpc/`);
          return globalThis.fetch(publicUrl, init);
        },
      };
    }
  }

  get isServiceBinding(): boolean {
    return this._isServiceBinding;
  }

  get fetcher(): Fetcher {
    return this.binding;
  }

  async xrpc<T>(nsid: string, opts?: XrpcCallOpts): Promise<XrpcResponse<T>> {
    const auth = opts?.auth;
    const headers = auth ? await auth.resolve(nsid) : { "content-type": "application/json" };
    const resp = await this.binding!.fetch(`${PDS_INTERNAL}/xrpc/${nsid}`, {
      method: opts?.method ?? "POST",
      headers,
      body: opts?.params ? JSON.stringify(opts.params) : undefined,
      signal: opts?.signal,
    });
    return parseResponse<T>(resp, nsid);
  }
}

