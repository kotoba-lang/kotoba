// langserver-xrpc-handler.ts — Hono routes that expose a UNSPSC or ISIC
// langserver as XRPC. Per ADR-2605180900 Phase 7.
//
// The handler mounts under `/xrpc/com.etzhayyim.apps.{taxonomy}.{action}` and
// delegates each route to the per-taxonomy actor wrapper (Phase 6). The
// AppView Worker hosts this handler at a public domain
// (unispsc.etzhayyim.com / isic.etzhayyim.com); the langserver itself
// stays in-cluster.
//
//   const app = createLangserverXrpcHandler({ taxonomy: "unispsc", endpoint: env.LG_UNISPSC });
//   export default { fetch: app.fetch };

import { Hono } from "hono";

import {
  createIsicActor,
  createUnispscActor,
  IsicActor,
  LangserverActor,
  LangserverActorError,
  type Taxonomy,
  UnispscActor,
} from "./langserver-actor.js";

export interface LangserverXrpcHandlerConfig {
  taxonomy: Taxonomy;
  /** Base URL of the langserver (in-cluster Service or public DNS). */
  endpoint: string;
  /** Optional custom fetcher (CF Service binding, traced fetch, test mock). */
  fetcher?: { fetch: typeof fetch };
  /** Default request timeout in ms (8s). */
  timeoutMs?: number;
  /** Pre-built actor (overrides endpoint+fetcher; mostly for tests). */
  actor?: LangserverActor;
}

interface ActorBinding {
  taxonomy: Taxonomy;
  unispsc?: UnispscActor;
  isic?: IsicActor;
}

function buildActor(config: LangserverXrpcHandlerConfig): ActorBinding {
  if (config.actor) {
    if (config.taxonomy === "unispsc") {
      return { taxonomy: "unispsc", unispsc: config.actor as UnispscActor };
    }
    return { taxonomy: "isic", isic: config.actor as IsicActor };
  }
  const base = {
    endpoint: config.endpoint,
    fetcher: config.fetcher,
    timeoutMs: config.timeoutMs,
  };
  if (config.taxonomy === "unispsc") {
    return { taxonomy: "unispsc", unispsc: createUnispscActor(base) };
  }
  return { taxonomy: "isic", isic: createIsicActor(base) };
}

function toErrorResponse(err: unknown): { status: number; body: { error: string; detail?: unknown } } {
  if (err instanceof LangserverActorError) {
    return { status: err.status, body: { error: err.message, detail: err.detail } };
  }
  const msg = err instanceof Error ? err.message : String(err);
  return { status: 500, body: { error: msg } };
}

/** Build a Hono app that exposes one taxonomy's langserver as XRPC. */
export function createLangserverXrpcHandler(
  config: LangserverXrpcHandlerConfig,
): Hono {
  const app = new Hono();
  const binding = buildActor(config);
  const taxonomy = binding.taxonomy;

  app.get("/", (c) =>
    c.json({
      service: `appview-open-${taxonomy}`,
      taxonomy,
      lexicons: [
        `com.etzhayyim.apps.${taxonomy}.classify`,
        `com.etzhayyim.apps.${taxonomy}.invokeAgent`,
        `com.etzhayyim.apps.${taxonomy}.listAgents`,
        `com.etzhayyim.apps.${taxonomy}.health`,
        ...(taxonomy === "isic"
          ? [`com.etzhayyim.apps.isic.hierarchicalClassify`]
          : []),
      ],
    }),
  );

  app.get("/health", async (c) => {
    try {
      const actor = (binding.unispsc ?? binding.isic) as LangserverActor;
      const out = await actor.health();
      return c.json(out);
    } catch (err) {
      const e = toErrorResponse(err);
      return c.json(e.body, e.status as never);
    }
  });

  // ── Lexicon-shaped XRPC endpoints ─────────────────────────────────────────

  const nsid = (action: string) => `/xrpc/com.etzhayyim.apps.${taxonomy}.${action}`;

  // classify (procedure)
  app.post(nsid("classify"), async (c) => {
    let body: Record<string, unknown> = {};
    try {
      body = (await c.req.json()) as Record<string, unknown>;
    } catch {
      return c.json({ error: "InvalidJSON" }, 400);
    }
    const description = (body.description as string | undefined) ?? "";
    if (!description) return c.json({ error: "DescriptionEmpty" }, 400);

    try {
      const actor = (binding.unispsc ?? binding.isic) as LangserverActor;
      const result = await (actor as UnispscActor | IsicActor).classify({
        description,
        topK: body.topK as number | undefined,
        modelHint: body.modelHint as "haiku-4.5" | "sonnet-4.6" | "auto" | undefined,
        confidenceThreshold: body.confidenceThreshold as number | undefined,
      });
      return c.json(result);
    } catch (err) {
      const e = toErrorResponse(err);
      return c.json(e.body, e.status as never);
    }
  });

  // invokeAgent (procedure)
  app.post(nsid("invokeAgent"), async (c) => {
    let body: Record<string, unknown> = {};
    try {
      body = (await c.req.json()) as Record<string, unknown>;
    } catch {
      return c.json({ error: "InvalidJSON" }, 400);
    }
    const codeField = taxonomy === "isic" ? "classCode" : "code";
    const code = body[codeField] as string | undefined;
    const payload = body.payload as Record<string, unknown> | undefined;
    if (!code || payload === undefined) {
      return c.json(
        { error: `required fields: ${codeField}, payload` },
        400,
      );
    }
    try {
      const actor = (binding.unispsc ?? binding.isic) as LangserverActor;
      const input = {
        [codeField]: code,
        payload,
        modelHint: body.modelHint as "haiku-4.5" | "sonnet-4.6" | "auto" | undefined,
        timeoutMs: body.timeoutMs as number | undefined,
      };
      const result = await actor.invokeAgent(input as never);
      return c.json(result);
    } catch (err) {
      const e = toErrorResponse(err);
      return c.json(e.body, e.status as never);
    }
  });

  // listAgents (query)
  app.get(nsid("listAgents"), async (c) => {
    const url = new URL(c.req.url);
    const limit = parseInt(url.searchParams.get("limit") ?? "100", 10);
    const cursor = url.searchParams.get("cursor") ?? undefined;
    const prefix = url.searchParams.get("prefix") ?? undefined;
    const divisionPrefix =
      url.searchParams.get("divisionPrefix") ?? undefined;
    const section = url.searchParams.get("section") ?? undefined;
    try {
      const actor = (binding.unispsc ?? binding.isic) as LangserverActor;
      const result = await actor.listAgents({
        limit: Number.isFinite(limit) ? limit : 100,
        cursor,
        prefix,
        divisionPrefix,
        section,
      });
      return c.json(result);
    } catch (err) {
      const e = toErrorResponse(err);
      return c.json(e.body, e.status as never);
    }
  });

  // health (query) — same body as /health
  app.get(nsid("health"), async (c) => {
    try {
      const actor = (binding.unispsc ?? binding.isic) as LangserverActor;
      const out = await actor.health();
      return c.json(out);
    } catch (err) {
      const e = toErrorResponse(err);
      return c.json(e.body, e.status as never);
    }
  });

  // ISIC-only: hierarchicalClassify (procedure)
  if (taxonomy === "isic") {
    app.post(nsid("hierarchicalClassify"), async (c) => {
      let body: Record<string, unknown> = {};
      try {
        body = (await c.req.json()) as Record<string, unknown>;
      } catch {
        return c.json({ error: "InvalidJSON" }, 400);
      }
      const description = (body.description as string | undefined) ?? "";
      if (!description) return c.json({ error: "DescriptionEmpty" }, 400);
      try {
        const isic = binding.isic as IsicActor;
        const result = await isic.hierarchicalClassify({
          description,
          stopAt: body.stopAt as
            | "section"
            | "division"
            | "group"
            | "class"
            | undefined,
          modelHint: body.modelHint as
            | "haiku-4.5"
            | "sonnet-4.6"
            | "auto"
            | undefined,
          confidenceThreshold: body.confidenceThreshold as number | undefined,
        });
        return c.json(result);
      } catch (err) {
        const e = toErrorResponse(err);
        return c.json(e.body, e.status as never);
      }
    });
  }

  return app;
}
