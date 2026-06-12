/**
 * agent-lifecycle.ts — High-level agent lifecycle management.
 *
 * Wraps the low-level workflow WIT (start/pause/resume/terminate) and
 * virtual-actor WIT with a typed Agent abstraction. Any App that
 * manages sub-agents (briefing actors, mangaka actors, OS agents) can use
 * these helpers instead of raw workflow dispatch.
 */
import type { HostImports } from "./types.js";
import { genID, nowISO } from "./helpers.js";
// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import { createKyselyDb } from "./kysely.js";
import type { XrpcClient } from "./xrpc-client.js";

type AnyRow = Record<string, unknown>;
type KyselyDb = ReturnType<typeof createKyselyDb>;

function parseTags(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item));
  if (typeof value !== "string" || value.length === 0) return [];
  try {
    const parsed = JSON.parse(value) as unknown;
    return Array.isArray(parsed) ? parsed.map((item) => String(item)) : [];
  } catch {
    return [];
  }
}

function normalizeAgentRow(row: AnyRow | null | undefined): AgentRecord | null {
  if (!row) return null;
  return {
    agentId: String(row.agent_id ?? row.agentId ?? ""),
    did: String(row.did ?? ""),
    appId: String(row.app_id ?? row.appId ?? ""),
    name: String(row.name ?? ""),
    status: String(row.status ?? "active") as AgentStatus,
    tags: parseTags(row.config_json ?? row.tags),
    createdAt: String(row.created_at ?? row.createdAt ?? ""),
  };
}

let db: KyselyDb | null = null;

function getDb(): KyselyDb {
  if (!db) db = createKyselyDb();
  return db;
}

async function listAgentRows(appNanoid: string, limit: number): Promise<AgentRecord[]> {
  const rows = await getDb()
    .selectFrom("vertex_os_agent" as any)
    .selectAll()
    .where("actor_id" as any, "=", appNanoid)
    .orderBy("created_at" as any, "desc")
    .limit(Math.max(0, limit))
    .execute();
  return rows.map((row) => normalizeAgentRow(row as AnyRow)).filter(Boolean) as AgentRecord[];
}

/** Agent status. */
export type AgentStatus = "active" | "paused" | "stopped" | "migrating" | "error";

/** Agent configuration for spawning. */
export interface AgentSpawnConfig {
  /** App ID (nanoid) of the agent to spawn. */
  appId: string;
  /** Display name. */
  name: string;
  /** Agent capabilities/tags for directory discovery. */
  tags?: string[];
  /** Initial configuration (JSON-serializable). */
  config?: Record<string, unknown>;
}

/** Agent instance record. */
export interface AgentRecord {
  agentId: string;
  did: string;
  appId: string;
  name: string;
  status: AgentStatus;
  tags: string[];
  createdAt: string;
}

/** Agent lifecycle event. */
export interface AgentEvent {
  agentId: string;
  event: "spawn" | "stop" | "pause" | "resume" | "migrate" | "error";
  target?: string;
  detail?: string;
  timestamp: string;
}

/** High-level agent lifecycle helper. Constructed via `createAgentLifecycle()`. */
export interface AgentLifecycle {
  /** Spawn a new agent. Returns the agent record. */
  spawn(config: AgentSpawnConfig): Promise<AgentRecord>;
  /** Stop an agent (clean shutdown). */
  stop(agentId: string, reason?: string): Promise<AgentEvent>;
  /** Pause an agent (freeze compute, retain state). */
  pause(agentId: string): Promise<AgentEvent>;
  /** Resume a paused agent. */
  resume(agentId: string): Promise<AgentEvent>;
  /** Migrate an agent between local and cloud. */
  migrate(agentId: string, target: "local" | "cloud"): Promise<AgentEvent>;
  /** List agents managed by this app. */
  list(options?: { status?: AgentStatus; limit?: number }): Promise<AgentRecord[]>;
  /** Get a specific agent by ID. */
  get(agentId: string): Promise<AgentRecord | null>;
  /** Count agents by status. */
  count(status?: AgentStatus): Promise<number>;
}

/**
 * Create an agent lifecycle helper bound to an SDK instance.
 *
 * @param pds - XrpcClient for dispatching AT records
 * @param hostImports - Host imports for workflow WIT calls
 * @param appNanoid - This app's nanoid (for actor_id in RLS columns)
 */
export function createAgentLifecycle(
  pds: XrpcClient,
  hostImports: HostImports,
  appNanoid: string,
): AgentLifecycle {

  async function emitEvent(
    agentId: string,
    event: AgentEvent["event"],
    extra?: { target?: string; detail?: string },
  ): Promise<AgentEvent> {
    const ts = nowISO();
    const evt: AgentEvent = { agentId, event, timestamp: ts, ...extra };

    await pds.dispatch({
      type: "com.atproto.repo.createRecord",
      payload: { collection: "com.etzhayyim.agent.event", record: {
        agentId,
        event,
        target: extra?.target ?? "",
        detail: extra?.detail ?? "",
        org_id: "anon",
        user_id: "anon",
        actor_id: appNanoid,
        created_at: ts,
      } },
    });

    return evt;
  }

  return {
    async spawn(config: AgentSpawnConfig): Promise<AgentRecord> {
      const agentId = genID("agent");
      const did = `did:web:${config.appId}.etzhayyim.com`;
      const ts = nowISO();
      const tags = config.tags ?? [];

      // Start a workflow for the agent lifecycle
      hostImports.workflowStart(
        `agent:${agentId}`,
        JSON.stringify({ appId: config.appId, name: config.name, config: config.config ?? {} }),
        JSON.stringify({ agentId, did }),
      );

      // Persist agent record
      await pds.dispatch({
        type: "com.atproto.repo.createRecord",
        payload: { collection: "com.etzhayyim.agent.instance", record: {
          agentId,
          did,
          appId: config.appId,
          name: config.name,
          status: "active",
          tags: JSON.stringify(tags),
          org_id: "anon",
          user_id: "anon",
          actor_id: appNanoid,
          created_at: ts,
          updated_at: ts,
        } },
      });

      await emitEvent(agentId, "spawn");

      return { agentId, did, appId: config.appId, name: config.name, status: "active", tags, createdAt: ts };
    },

    async stop(agentId: string, reason?: string): Promise<AgentEvent> {
      hostImports.workflowTerminate(`agent:${agentId}`);
      return emitEvent(agentId, "stop", { detail: reason });
    },

    async pause(agentId: string): Promise<AgentEvent> {
      hostImports.workflowPause(`agent:${agentId}`);
      return emitEvent(agentId, "pause");
    },

    async resume(agentId: string): Promise<AgentEvent> {
      hostImports.workflowResume(`agent:${agentId}`);
      return emitEvent(agentId, "resume");
    },

    async migrate(agentId: string, target: "local" | "cloud"): Promise<AgentEvent> {
      hostImports.workflowSignal(`agent:${agentId}`, "migrate", JSON.stringify({ target }));
      return emitEvent(agentId, "migrate", { target });
    },

    async list(options?: { status?: AgentStatus; limit?: number }): Promise<AgentRecord[]> {
      const limit = options?.limit ?? 100;
      const rows = await listAgentRows(appNanoid, limit);
      return options?.status ? rows.filter((row) => row.status === options.status) : rows;
    },

    async get(agentId: string): Promise<AgentRecord | null> {
      const rows = await listAgentRows(appNanoid, 200);
      return rows.find((row) => row.agentId === agentId) ?? null;
    },

    async count(status?: AgentStatus): Promise<number> {
      const rows = await listAgentRows(appNanoid, 500);
      return status ? rows.filter((row) => row.status === status).length : rows.length;
    },
  };
}
