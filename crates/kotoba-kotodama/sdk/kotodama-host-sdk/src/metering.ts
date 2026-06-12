// metering.ts — billing v2 retail cloud usage event emitter (ADR-2605080000 P2).
//
// Emits `vertex_billing_event` rows via Hyperdrive direct INSERT (ADR-0036).
// Fire-and-forget via `ctx.waitUntil` so request latency is unaffected.
//
// Two surfaces:
//
//   1. `recordUsageEvent(env, ctx, params)` — one-shot emit. Use when a
//      Worker handler needs to count something specific (LLM tokens,
//      bytes uploaded, GPU seconds).
//
//   2. `createMeteringMiddleware()` — Hono middleware that auto-emits one
//      `api_request` event per inbound request. Wire once at the top of
//      the router; bypasses metering for unauthenticated / public traffic
//      and for `com.etzhayyim.apps.billing.*` calls (avoid recursion).
//
// Pricing & cost registries are kept server-side in
// `40-engine/kotoba/crates/kotoba-kotodama/py/src/kotodama/primitives/billing.py` (the
// authoritative SSoT). Worker-side this module ships only the list price
// in JPY-micro because the unit cost is etzhayyim-internal and not relevant
// to the row written from a customer Worker (the billing primitive
// recomputes both at rollup time anyway).
//
// Direct INSERT pattern (ADR-0036):
//   db.insertInto('vertex_billing_event').values({...}).execute()
//
// `applied_discount_pct` resolution is cached per-org for 60s in a
// per-isolate Map. Uncached lookup hits `vertex_billing_org_plan`. Unknown
// orgs default to 0% discount.
//
// Opt-out: env.etzhayyim_METERING_DISABLED === '1'.

// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import { createKyselyDb, type Hyperdrive, type KyselyDb } from "./kysely.js";

// ──────────────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────────────

/** Metric names — must match `_LIST_PRICE_JPY_MICRO` keys in billing.py. */
export type BillingMetric =
  | "storage_gb_hour"
  | "egress_gb"
  | "llm_input_tokens"
  | "llm_output_tokens"
  | "gpu_hour"
  | "api_request"
  | "mcp_call"
  | "did_mint"
  | "yata_node_hour"
  | "yata_edge_hour"
  | "yata_query_cu_ms"
  | "yata_reasoning_run"
  | "obj_class_a"
  | "obj_class_b";

export type BillingProduct = "yata" | "obj" | "gateway" | "platform";

export interface MeteringEnv {
  HYPERDRIVE?: Hyperdrive;
  /** Set to "1" to disable metering (smoke-test, dev). */
  etzhayyim_METERING_DISABLED?: string;
}

export interface MeteringContext {
  /** CF Workers ExecutionContext.waitUntil — required for fire-and-forget. */
  waitUntil(promise: Promise<unknown>): void;
}

export interface RecordUsageEventParams {
  orgDid: string;
  /** Optional sub-actor DID inside the org for cost split. */
  actorDid?: string;
  /** Defaults to Date.now(). */
  tsMs?: number;
  metric: BillingMetric;
  qty: number;
  product: BillingProduct;
  /** Bucket / database / NSID called — feeds per-resource breakdown. */
  refResource?: string;
}

// ──────────────────────────────────────────────────────────────────────
// JPY-micro list prices (mirror of billing.py _LIST_PRICE_JPY_MICRO)
// ──────────────────────────────────────────────────────────────────────

const JPY_MICRO = 1_000_000;

const LIST_PRICE_JPY_MICRO: Record<BillingMetric, number> = {
  storage_gb_hour:    Math.round(10 * JPY_MICRO / (30 * 24)),
  egress_gb:          15 * JPY_MICRO,
  llm_input_tokens:   Math.round(0.50 * JPY_MICRO / 1000),
  llm_output_tokens:  Math.round(1.50 * JPY_MICRO / 1000),
  gpu_hour:           300 * JPY_MICRO,
  api_request:        Math.round(2.0 * JPY_MICRO / 10000),
  mcp_call:           Math.round(3.0 * JPY_MICRO / 100),
  did_mint:           300 * JPY_MICRO,
  yata_node_hour:     Math.round(1000 * JPY_MICRO / (1_000_000 * 24 * 30)),
  yata_edge_hour:     Math.round(500 * JPY_MICRO / (1_000_000 * 24 * 30)),
  yata_query_cu_ms:   Math.round(300 * JPY_MICRO / (1000 * 60 * 60 * 1000)),
  yata_reasoning_run: 500 * JPY_MICRO,
  obj_class_a:        Math.round(10 * JPY_MICRO / 1_000_000),
  obj_class_b:        Math.round(1 * JPY_MICRO / 1_000_000),
};

// ──────────────────────────────────────────────────────────────────────
// Discount cache (per-isolate, 60s TTL)
// ──────────────────────────────────────────────────────────────────────

interface DiscountEntry {
  pct: number;
  at: number;
}

const _discountCache = new Map<string, DiscountEntry>();
const DISCOUNT_CACHE_TTL = 60_000;

async function resolveDiscountPctCached(
  db: KyselyDb,
  orgDid: string,
): Promise<number> {
  const cached = _discountCache.get(orgDid);
  if (cached && Date.now() - cached.at < DISCOUNT_CACHE_TTL) return cached.pct;
  try {
    const row = await db
      .selectFrom("vertex_billing_org_plan" as never)
      .select(["applied_discount_pct" as never])
      .where("org_did" as never, "=", orgDid)
      .where("status" as never, "=", "active")
      .limit(1)
      .executeTakeFirst() as { applied_discount_pct?: number | null } | undefined;
    const pct = Number(row?.applied_discount_pct ?? 0);
    _discountCache.set(orgDid, { pct, at: Date.now() });
    return pct;
  } catch (e) {
    console.warn("[metering] discount lookup failed:", e);
    _discountCache.set(orgDid, { pct: 0, at: Date.now() });
    return 0;
  }
}

// ──────────────────────────────────────────────────────────────────────
// Content-addressed PK (ADR-0041, mirrors billing.py _content_pk)
// ──────────────────────────────────────────────────────────────────────

async function contentPk(parts: string[]): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(parts.join("|")));
  const hex = Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, 32);
  return `at://did:web:billing.etzhayyim.com/com.etzhayyim.apps.billing.event/${hex}`;
}

// ──────────────────────────────────────────────────────────────────────
// One-shot emit
// ──────────────────────────────────────────────────────────────────────

/**
 * Record a single usage event. Fire-and-forget via `ctx.waitUntil`.
 * Returns immediately; the actual INSERT runs after the response is sent.
 *
 * Drops silently when:
 *   - env.etzhayyim_METERING_DISABLED === '1'
 *   - env.HYPERDRIVE is missing
 *   - orgDid is empty / not a DID
 *   - qty <= 0
 *   - metric is unknown
 */
export function recordUsageEvent(
  env: MeteringEnv,
  ctx: MeteringContext,
  params: RecordUsageEventParams,
): void {
  if (env.etzhayyim_METERING_DISABLED === "1") return;
  if (!env.HYPERDRIVE) return;
  if (!params.orgDid || !params.orgDid.startsWith("did:")) return;
  if (!Number.isFinite(params.qty) || params.qty <= 0) return;
  const listPrice = LIST_PRICE_JPY_MICRO[params.metric];
  if (typeof listPrice !== "number") return;

  ctx.waitUntil((async () => {
    try {
      const db = createKyselyDb(env.HYPERDRIVE!);
      const tsMs = params.tsMs ?? Date.now();
      const refResource = params.refResource ?? "";
      const actorDid = params.actorDid ?? "";
      const vertexId = await contentPk([
        params.orgDid, params.metric, String(tsMs), refResource, actorDid,
      ]);
      const discountPct = await resolveDiscountPctCached(db, params.orgDid);
      const billed = Math.round(listPrice * params.qty * (100 - discountPct) / 100);
      const today = new Date(tsMs).toISOString().slice(0, 10);
      const nowIso = new Date().toISOString();

      await db.insertInto("vertex_billing_event" as never).values({
        vertex_id: vertexId,
        created_date: today,
        sensitivity_ord: 2,
        owner_did: "did:web:billing.etzhayyim.com",
        org_did: params.orgDid,
        actor_did: params.actorDid ?? null,
        ts_ms: tsMs,
        metric: params.metric,
        qty: params.qty,
        product: params.product,
        ref_resource: refResource || null,
        unit_cost_jpy_micro: null,
        list_price_jpy_micro: listPrice,
        applied_discount_pct: discountPct,
        billed_amount_jpy_micro: billed,
        created_at: nowIso,
        org_id: params.orgDid,
        user_id: params.actorDid ?? params.orgDid,
        actor_id: "sys.billing.meter.host-sdk",
      } as never).execute();
    } catch (e) {
      console.warn("[metering] event INSERT failed:", e);
    }
  })());
}

// ──────────────────────────────────────────────────────────────────────
// Hono middleware — auto-emit one api_request per inbound request
// ──────────────────────────────────────────────────────────────────────

interface MeteringMiddlewareOptions {
  /** Default product label for events emitted by this middleware. */
  product: BillingProduct;
  /**
   * NSID prefixes whose requests should NOT be metered (avoid recursion
   * on billing.* calls + skip non-business endpoints like /health).
   * Defaults to ["com.etzhayyim.apps.billing.", "_app/"].
   */
  skipPrefixes?: string[];
}

/**
 * Create a Hono middleware that emits one `api_request` event per
 * authenticated inbound request. Bypasses unauthenticated traffic and
 * `com.etzhayyim.apps.billing.*` to prevent recursion.
 *
 * Wire it once at the top of `createWorkerExport`:
 *
 *   app.use("*", createMeteringMiddleware({ product: "yata" }));
 *
 * The middleware reads `c.var.auth` (set by the standard auth middleware)
 * for orgDid + actorDid. If the auth context is not yet attached the
 * event is skipped silently.
 */
export function createMeteringMiddleware(
  options: MeteringMiddlewareOptions,
) {
  const skipPrefixes = options.skipPrefixes ?? ["com.etzhayyim.apps.billing.", "_app/"];
  return async function meteringMiddleware(c: any, next: () => Promise<void>) {
    await next();
    try {
      const env = c.env as MeteringEnv;
      if (env.etzhayyim_METERING_DISABLED === "1") return;
      const path = String(c.req?.path ?? "");
      const xrpcMatch = path.match(/^\/xrpc\/([^/?#]+)/);
      const nsid = xrpcMatch?.[1] ?? "";
      if (nsid && skipPrefixes.some(p => nsid.startsWith(p))) return;
      const auth = c.var?.auth ?? c.get?.("auth");
      const orgDid = String(auth?.orgDid ?? auth?.accountDid ?? auth?.did ?? "");
      if (!orgDid.startsWith("did:")) return;
      const actorDid = String(auth?.activeDid ?? auth?.userDid ?? "") || undefined;
      const ctx = c.executionCtx as MeteringContext | undefined;
      if (!ctx?.waitUntil) return;
      recordUsageEvent(env, ctx, {
        orgDid,
        actorDid,
        metric: "api_request",
        qty: 1,
        product: options.product,
        refResource: nsid || path,
      });
    } catch (e) {
      console.warn("[metering] middleware failed:", e);
    }
  };
}
