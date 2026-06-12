/**
 * consent-helpers.ts — High-level consent workflow helpers.
 *
 * Wraps the low-level hostImports consent + governance WIT with typed
 * convenience functions for human-in-the-loop approval flows.
 * Any App can use these to submit actions for human approval.
 */
import type { HostImports } from "./types.js";
import { genID, nowISO } from "./helpers.js";
// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import { createKyselyDb } from "./kysely.js";
import type { XrpcClient } from "./xrpc-client.js";

type AnyRow = Record<string, unknown>;
type KyselyDb = ReturnType<typeof createKyselyDb>;

function normalizeRequestRow(row: AnyRow | null | undefined): ConsentRequestRecord | null {
  if (!row) return null;
  return {
    requestId: String(row.request_id ?? row.requestId ?? ""),
    agentDid: String(row.agent_did ?? row.agentDid ?? ""),
    action: String(row.action ?? ""),
    riskTier: String(row.risk_tier ?? row.riskTier ?? ""),
    estimatedCost: Number(row.estimated_cost ?? row.estimatedCost ?? 0),
    context: String(row.context_json ?? row.context ?? "{}"),
    status: String(row.status ?? "pending") as ConsentRequestRecord["status"],
    createdAt: String(row.created_at ?? row.createdAt ?? ""),
  };
}

let db: KyselyDb | null = null;

function getDb(): KyselyDb {
  if (!db) db = createKyselyDb();
  return db;
}

async function listConsentRequests(appNanoid: string, limit: number): Promise<ConsentRequestRecord[]> {
  const rows = await getDb()
    .selectFrom("vertex_os_consent_request" as any)
    .selectAll()
    .where("actor_id" as any, "=", appNanoid)
    .orderBy("created_at" as any, "desc")
    .limit(Math.max(0, limit))
    .execute();
  return rows.map((row) => normalizeRequestRow(row as AnyRow)).filter(Boolean) as ConsentRequestRecord[];
}

/** Consent request input. */
export interface ConsentSubmitInput {
  /** Agent DID requesting consent. */
  agentDid: string;
  /** Human-readable action description. */
  action: string;
  /** Risk tier: "low" | "medium" | "high" | "critical". */
  riskTier: string;
  /** Estimated cost in GCC tokens. */
  estimatedCost?: number;
  /** Additional context (JSON string). */
  context?: string;
}

/** Consent request record stored in graph. */
export interface ConsentRequestRecord {
  requestId: string;
  agentDid: string;
  action: string;
  riskTier: string;
  estimatedCost: number;
  context: string;
  status: "pending" | "approved" | "denied";
  createdAt: string;
}

/** Consent resolution result. */
export interface ConsentVerdict {
  requestId: string;
  verdict: "approved" | "denied";
  reason?: string;
  resolvedAt: string;
}

/** High-level consent workflow helper. Constructed via `createConsentHelper()`. */
export interface ConsentHelper {
  /** Submit an action for human consent approval. Returns the requestId. */
  submit(input: ConsentSubmitInput): Promise<string>;
  /** Approve a pending consent request. */
  approve(requestId: string): Promise<ConsentVerdict>;
  /** Deny a pending consent request with optional reason. */
  deny(requestId: string, reason?: string): Promise<ConsentVerdict>;
  /** List pending consent requests for this app. */
  pending(limit?: number): Promise<ConsentRequestRecord[]>;
  /** Get a specific consent request by ID. */
  get(requestId: string): Promise<ConsentRequestRecord | null>;
  /** Count pending consent requests. */
  pendingCount(): Promise<number>;
}

/**
 * Create a consent workflow helper bound to an SDK instance.
 *
 * @param pds - XrpcClient for dispatching AT records
 * @param hostImports - Host imports for low-level consent WIT calls
 * @param appNanoid - This app's nanoid (for actor_id in RLS columns)
 */
export function createConsentHelper(
  pds: XrpcClient,
  hostImports: HostImports,
  appNanoid: string,
): ConsentHelper {
  return {
    async submit(input: ConsentSubmitInput): Promise<string> {
      const requestId = genID("consent");
      const ts = nowISO();

      // Dispatch consent grant via WIT
      hostImports.consentCreate(
        JSON.stringify({
          requestId,
          agentDid: input.agentDid,
          action: input.action,
          riskTier: input.riskTier,
          estimatedCost: input.estimatedCost ?? 0,
          context: input.context ?? "{}",
          status: "pending",
        }),
      );

      // Persist as AT record for graph query
      await pds.dispatch({
        type: "com.atproto.repo.createRecord",
        payload: { collection: "com.etzhayyim.consent.request", record: {
          requestId,
          agentDid: input.agentDid,
          action: input.action,
          riskTier: input.riskTier,
          estimatedCost: input.estimatedCost ?? 0,
          context: input.context ?? "{}",
          status: "pending",
          org_id: "anon",
          user_id: "anon",
          actor_id: appNanoid,
          created_at: ts,
        } },
      });

      return requestId;
    },

    async approve(requestId: string): Promise<ConsentVerdict> {
      const ts = nowISO();
      await pds.dispatch({
        type: "com.atproto.repo.createRecord",
        payload: { collection: "com.etzhayyim.consent.response", record: {
          requestId,
          verdict: "approved",
          org_id: "anon",
          user_id: "anon",
          actor_id: appNanoid,
          created_at: ts,
        } },
      });
      return { requestId, verdict: "approved", resolvedAt: ts };
    },

    async deny(requestId: string, reason?: string): Promise<ConsentVerdict> {
      const ts = nowISO();
      await pds.dispatch({
        type: "com.atproto.repo.createRecord",
        payload: { collection: "com.etzhayyim.consent.response", record: {
          requestId,
          verdict: "denied",
          reason: reason ?? "",
          org_id: "anon",
          user_id: "anon",
          actor_id: appNanoid,
          created_at: ts,
        } },
      });
      return { requestId, verdict: "denied", reason, resolvedAt: ts };
    },

    async pending(limit = 50): Promise<ConsentRequestRecord[]> {
      const rows = await listConsentRequests(appNanoid, limit);
      return rows.filter((row) => row.status === "pending").slice(0, Math.max(0, limit));
    },

    async get(requestId: string): Promise<ConsentRequestRecord | null> {
      const rows = await listConsentRequests(appNanoid, 200);
      return rows.find((row) => row.requestId === requestId) ?? null;
    },

    async pendingCount(): Promise<number> {
      const rows = await listConsentRequests(appNanoid, 500);
      return rows.filter((row) => row.status === "pending").length;
    },
  };
}
