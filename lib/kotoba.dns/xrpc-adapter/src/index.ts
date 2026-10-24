/**
 * dns XRPC adapter — CF Worker.
 *
 * Wires the kotoba reference impl (6 pure TS functions) into a deployable
 * CF Worker that exposes each function as an XRPC endpoint at
 * https://dns.etzhayyim.com/xrpc/com.etzhayyim.dns.<cmd>
 *
 * Per ADR-2605210000 first execution-layer demonstration. Instantiates the
 * Etzhayyim SDK from env bindings (PDS_URL + session), calls the kotoba
 * function with parsed input, returns the result as JSON, and maps status
 * codes to HTTP responses.
 *
 * Single-file principle: all routing and handler logic here.
 */

import {
  createAuthedEtzhayyim,
  extractBearerToken,
  type Etzhayyim,
} from "@etzhayyim/sdk-auth";
import * as dnsRwFree from "@etzhayyim/dns-kotoba";

interface Env {
  ACTOR_DID: string;
  PDS_URL: string;
  L2_RPC_URL: string;
  PDS_ACCESS_JWT?: string;
  PDS_REFRESH_JWT?: string;
}

type Handler = (e: Etzhayyim, input: unknown) => Promise<unknown>;

const NSID_BASE = "com.etzhayyim.dns";

interface RouteConfig {
  method: "POST" | "GET";
  handler: Handler;
}

const routes: Record<string, RouteConfig> = {
  [`${NSID_BASE}.createTransferRequest`]: {
    method: "POST",
    handler: (e, input) => dnsRwFree.createTransferRequest(e, input as Record<string, unknown>),
  },
  [`${NSID_BASE}.getTransferRequest`]: {
    method: "GET",
    handler: (e, input) => dnsRwFree.getTransferRequest(e, input as Record<string, unknown>),
  },
  [`${NSID_BASE}.transferFromSquarespace`]: {
    method: "POST",
    handler: (e, input) => dnsRwFree.transferFromSquarespace(e, input as Record<string, unknown>),
  },
  [`${NSID_BASE}.putTransferStep`]: {
    method: "POST",
    handler: (e, input) => dnsRwFree.putTransferStep(e, input as Record<string, unknown>),
  },
  [`${NSID_BASE}.listTransferSteps`]: {
    method: "GET",
    handler: (e, input) => dnsRwFree.listTransferSteps(e, input as Record<string, unknown>),
  },
  [`${NSID_BASE}.putTransferOutcome`]: {
    method: "POST",
    handler: (e, input) => dnsRwFree.putTransferOutcome(e, input as Record<string, unknown>),
  },
};

function mapStatus(status?: string): number {
  if (status === "rejected") return 400;
  if (status === "notFound") return 404;
  if (status === "alreadyExists" || status === "alreadyProcessed") return 200;
  return 200;
}

function jsonResponse(
  body: unknown,
  status: number = 200,
  init?: ResponseInit
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json",
      ...init?.headers,
    },
    ...init,
  });
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);

    if (!url.pathname.startsWith("/xrpc/")) {
      return jsonResponse({ error: "NotFound" }, 404);
    }

    const nsid = url.pathname.slice("/xrpc/".length);
    const route = routes[nsid];

    if (!route) {
      return jsonResponse({ error: "MethodNotFound", nsid }, 404);
    }

    if (req.method !== route.method) {
      return jsonResponse({ error: "MethodNotAllowed" }, 405);
    }

    const e = new Etzhayyim({
      did: env.ACTOR_DID,
      pdsUrl: env.PDS_URL,
      l2RpcUrl: env.L2_RPC_URL,
    });

    let input: unknown;
    try {
      if (route.method === "POST") {
        input = await req.json().catch(() => ({}));
      } else {
        input = Object.fromEntries(url.searchParams.entries());
        const typed = input as Record<string, unknown>;
        if (typed.limit) typed.limit = Number(typed.limit);
        if (typed.offset) typed.offset = Number(typed.offset);
        if (typed.maxScan) typed.maxScan = Number(typed.maxScan);
      }
    } catch (err) {
      return jsonResponse(
        {
          error: "InvalidInput",
          message: `Failed to parse ${route.method === "POST" ? "JSON" : "query params"}`,
        },
        400
      );
    }

    try {
      const result = await route.handler(e, input);
      const status = mapStatus((result as Record<string, unknown>)?.status as string | undefined);
      return jsonResponse(result, status);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      return jsonResponse(
        {
          error: "InternalError",
          message,
          nsid,
        },
        500
      );
    }
  },
} satisfies ExportedHandler<Env>;
