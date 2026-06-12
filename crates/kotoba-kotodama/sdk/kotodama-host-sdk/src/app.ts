// app.ts — App lifecycle, command routing, auto-registration.
//
// Single source of SDK business logic. Replaces duplicated App class across 4 guest SDKs.
// Runs in the Worker V8 runtime (host side), not inside a guest component.

import type {
  AppDef,
  AppContext,
  RLSMeta,
  CommandHandler,
  ConversationHandler,
  RemoteCallHandler,
  ComAtprotoSyncSubscribeReposCommit,
  ConversationMessage,
  HostImports,
} from "./types.js";
import { toSnake, toKebab, decodeJson, genID, nowISO, rlsDefaults, str, parseUrl, respondJson } from "./helpers.js";
// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import { createKyselyDb } from "./kysely.js";
import { llmAsk } from "./llm.js";
import { resolveHeartbeatCadence, createCadenceState, createInboxBuffer, type CadenceState, type InboxBuffer, type InboundCommit, type InboundReaction, type HeartbeatCadence } from "./heartbeat-cadence.js";
import { conversationSecureDecrypt, reply, say } from "./conversation.js";
import { agentConverseAsync } from "./llm.js";
import { agentReact, type AgentTool } from "./react.js";
import type { XrpcClient } from "./xrpc-client.js";
import { resolveAutoCrudConvention } from "@etzhayyim/xrpc/app-convention";
import { registerCommand, registerQuery } from "@etzhayyim/xrpc/command-dsl";
import { resolveXrpcMethod } from "@etzhayyim/xrpc/dispatch";
import {
  createCommandEntry,
  asAgentTool,
  withCapabilityTags,
  withSignalEncrypt,
  withCapabilityPhase,
  withWLexicon,
  responsible,
  accountable,
  consulted,
  informed,
  requireApproval,
  withBPMNTask,
  withOCELEvent,
} from "./app-options.js";
import type { CommandEntry, QueryEntry, CommandOption } from "./app-options.js";
import type { StrictCommandNSID, StrictQueryNSID } from "./generated/lexicon-nsid-types.js";
import {
  buildGovernanceManifestFromCommands,
  buildDefaultAgentSystemPrompt,
} from "./app-metadata.js";
import { resolveAppContext } from "./app-auth-context.js";

export {
  asAgentTool,
  withCapabilityTags,
  withSignalEncrypt,
  withCapabilityPhase,
  withWLexicon,
  responsible,
  accountable,
  consulted,
  informed,
  requireApproval,
  withBPMNTask,
  withOCELEvent,
};
export type { CommandEntry, QueryEntry, CommandOption };

// ── RLS helper ──────────────────────────────────────────────────────────

export function makeRLSMeta(ctx: AppContext): RLSMeta {
  return {
    'orgId': ctx.orgId,
    'userId': ctx.userId,
    'actorId': ctx.actorId,
    'createdAt': ctx.now,
    'updatedAt': ctx.now,
  };
}

type AnyRow = Record<string, unknown>;
type KyselyDb = ReturnType<typeof createKyselyDb>;

let db: KyselyDb | null = null;

function getDb(): KyselyDb {
  if (!db) db = createKyselyDb();
  return db;
}

function normalizeVertexOther(row: AnyRow | null | undefined): AnyRow {
  if (!row) return {};
  let props: AnyRow = {};
  if (typeof row.props === "string" && row.props.length > 0) {
    try {
      const parsed = JSON.parse(row.props) as unknown;
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) props = parsed as AnyRow;
    } catch {
      props = {};
    }
  }
  return { ...props, ...row };
}

function rowField(row: AnyRow, ...keys: string[]): unknown {
  for (const key of keys) {
    if (row[key] != null && row[key] !== "") return row[key];
  }
  return undefined;
}

function sortByCreatedAt(rows: AnyRow[], desc = true): AnyRow[] {
  const instant = (row: AnyRow): number => {
    const value = rowField(row, "createdAt", "created_at");
    if (typeof value !== "string" || value.length === 0) return 0;
    const ts = Date.parse(value);
    return Number.isFinite(ts) ? ts : 0;
  };
  return [...rows].sort((a, b) => desc ? instant(b) - instant(a) : instant(a) - instant(b));
}

function filterBySearch(rows: AnyRow[], q: string, fields: string[]): AnyRow[] {
  const needle = q.trim().toLowerCase();
  if (!needle) return rows;
  return rows.filter((row) => fields.some((field) => String(rowField(row, field) ?? "").toLowerCase().includes(needle)));
}

function filterByActor(rows: AnyRow[], nanoid: string): AnyRow[] {
  return rows.filter((row) => String(rowField(row, "actorId", "actor_id") ?? "") === nanoid);
}

async function listCollectionRows(table: string, build?: (query: any) => any): Promise<AnyRow[]> {
  let query: any = getDb().selectFrom(table as any).selectAll();
  if (build) query = build(query);
  const rows = await query.execute();
  return rows.map((row: AnyRow) => normalizeVertexOther(row));
}

async function getCollectionRow(table: string, build?: (query: any) => any): Promise<AnyRow | null> {
  const rows = await listCollectionRows(table, (query) => {
    const next = build ? build(query) : query;
    return next.limit(1);
  });
  return rows[0] ?? null;
}

// ── AutoCrud config ────────────────────────────────────────────────────

/** Configuration for autoCrud() — auto-registers standard CRUD + utility commands. */
export interface AutoCrudConfig {
  /** App domain name (e.g. "oshi", "news"). Used for NSID: com.etzhayyim.apps.{domain}.* */
  domain: string;
  /** Primary SQL node label (e.g. "Creator", "NewsArticle"). */
  label: string;
  /** Collection name for AT records (defaults to com.etzhayyim.apps.{domain}.{camelLabel}). */
  collection?: string;
  /** Typed read table for autoCrud queries. Defaults to vertex_{domain}_{label}. */
  readTable?: string;
  /** Statuses for validation (defaults to standard set). */
  statuses?: string[];
  /** Extra searchable fields for WHERE CONTAINS (defaults to ["name", "description"]). */
  searchFields?: string[];
}

/** Heartbeat hook — receives resolved cadence, returns extra actions. */
export type HeartbeatHook = (cadence: HeartbeatCadence, sdk: { pds: XrpcClient; hostImports: HostImports }) => Promise<Array<Record<string, unknown>>>;

interface ManagedCommandError {
  code: string;
  message: string;
  status: number;
  retryable: boolean;
  details?: Record<string, unknown>;
}

function queryFailurePayload(action: string, error: unknown): Record<string, unknown> {
  const message = error instanceof Error ? error.message : String(error);
  return {
    error: "UpstreamQueryFailed",
    message: `Failed to ${action}`,
    retryable: true,
    details: { cause: message },
  };
}

function defaultXrpcOcelEventType(nsid: string): string {
  return `xrpc.${nsid}`;
}

function toSuccessResponse(result: unknown): { status: number; headers: [string, string][]; body: Uint8Array } {
  if (result instanceof Uint8Array) {
    return {
      status: 200,
      headers: [["content-type", "application/json"]],
      body: result,
    };
  }
  return respondJson(200, result);
}

// ── App class ───────────────────────────────────────────────────────────

export class App {
  readonly def: AppDef;
  private host: HostImports;
  private pdsClient: XrpcClient | null;
  private commands: CommandEntry[] = [];
  private queries: QueryEntry[] = [];
  private wRoutes = new Map<string, string>();
  private methodMap = new Map<string, CommandHandler>();
  private remoteHandlers = new Map<string, RemoteCallHandler>();
  private _conversationHandler: ConversationHandler | null = null;
  private _commitHandler: ((commit: ComAtprotoSyncSubscribeReposCommit) => void | Promise<void>) | null = null;
  private _served = false;
  private _heartbeatHook: HeartbeatHook | null = null;
  private _cadenceState: CadenceState = createCadenceState();
  private _inbox: InboxBuffer = createInboxBuffer();
  private _autoCrudConfig: AutoCrudConfig | null = null;

  /** App-specific fetch handler for custom non-XRPC routes (e.g. /v1/* OpenAI compat).
   *  Return a Response to handle the request, or null to fall through to default 404. */
  customFetch: ((request: Request) => Promise<globalThis.Response | null>) | null = null;

  constructor(def: AppDef, host: HostImports, pdsClient?: XrpcClient | null) {
    this.def = def;
    this.host = host;
    this.pdsClient = pdsClient ?? null;
  }

  private resolveManagedError(error: unknown, fallbackCode: string): ManagedCommandError {
    if (error && typeof error === "object") {
      const obj = error as Record<string, unknown>;
      const code = typeof obj.code === "string" && obj.code ? obj.code : fallbackCode;
      const message =
        typeof obj.message === "string" && obj.message
          ? obj.message
          : error instanceof Error
            ? error.message
            : String(error);
      const status =
        typeof obj.status === "number" && Number.isFinite(obj.status) && obj.status >= 400 && obj.status <= 599
          ? obj.status
          : 500;
      const retryable = typeof obj.retryable === "boolean" ? obj.retryable : status >= 500;
      const details = obj.details && typeof obj.details === "object"
        ? (obj.details as Record<string, unknown>)
        : undefined;
      return { code, message, status, retryable, details };
    }
    const message = error instanceof Error ? error.message : String(error);
    return { code: fallbackCode, message, status: 500, retryable: true };
  }

  private findCommandEntryByHandler(handler: CommandHandler): CommandEntry | undefined {
    return this.commands.find((entry) => entry.handler === handler);
  }

  private emitOcelV2(
    entry: CommandEntry | undefined,
    phase: "start" | "success" | "error",
    context: AppContext,
    methodName: string,
    status: "started" | "ok" | "error",
    durationMs?: number,
    managedError?: ManagedCommandError,
    eventTypeOverride?: string,
  ): void {
    const eventType = eventTypeOverride ?? entry?.ocelEventType ?? "";
    if (!eventType) return;
    const payload: Record<string, unknown> = {
      specVersion: "ocel.v2",
      eventType,
      phase,
      status,
      appId: this.def.id,
      command: methodName,
      actorDid: context.actorId,
      orgId: context.orgId,
      ts: new Date().toISOString(),
    };
    if (typeof durationMs === "number") payload.durationMs = durationMs;
    if (managedError) {
      payload.error = {
        code: managedError.code,
        message: managedError.message,
        retryable: managedError.retryable,
      };
    }
    try {
      this.host.ocelEmitEvent(JSON.stringify(payload));
    } catch (emitError) {
      console.warn("[ocel.v2] failed to emit event:", emitError);
    }
  }

  private async executeCommand(
    methodName: string,
    handler: CommandHandler,
    context: AppContext,
    body: Uint8Array,
    eventTypeOverride?: string,
  ): Promise<unknown> {
    const commandEntry = this.findCommandEntryByHandler(handler);
    const startedAt = Date.now();
    this.emitOcelV2(commandEntry, "start", context, methodName, "started", undefined, undefined, eventTypeOverride);
    try {
      const result = await handler(context, body);
      this.emitOcelV2(commandEntry, "success", context, methodName, "ok", Date.now() - startedAt, undefined, eventTypeOverride);
      return result;
    } catch (error) {
      const managed = this.resolveManagedError(error, "APP_COMMAND_FAILED");
      this.emitOcelV2(commandEntry, "error", context, methodName, "error", Date.now() - startedAt, managed, eventTypeOverride);
      throw managed;
    }
  }

  // F-Plan F2 (2026-04-13): `command` / `query` are now strictly typed. The NSID must
  // exist as a lexicon procedure / query in 00-contracts/lexicons/. Legacy loose
  // AssertCommandNSID / AssertQueryNSID paths were archived on 2026-04-13 — see
  // _archive/40-engine/kotoba/crates/kotoba-kotodama/sdk/kotodama-host-sdk-legacy-nsid-assert-260413/.
  //
  // Apps that use template-literal NSIDs or short non-AT-Protocol NSIDs need to either
  // (a) create the corresponding lexicon JSON and regenerate gen-lexicon-nsid-types.mjs,
  // or (b) migrate to a known NSID pattern com.etzhayyim.apps.{app}.{method}.
  command<Name extends string>(name: StrictCommandNSID<Name>, handler: CommandHandler, ...opts: CommandOption[]): App {
    const entry = createCommandEntry(name as string, handler);
    registerCommand({
      entries: this.commands,
      methodMap: this.methodMap,
      wRoutes: this.wRoutes,
      entry,
      opts,
    });
    return this;
  }

  query<Name extends string>(name: StrictQueryNSID<Name>, handler: CommandHandler): App {
    registerQuery({
      entries: this.queries,
      methodMap: this.methodMap,
      entry: { name: name as string, handler },
    });
    return this;
  }

  // `lexiconCommand` / `lexiconQuery` deprecated aliases removed 2026-04-13 (F-Plan F2 archive
  // step). 198/198 apps migrated back to `.command(nsid(...))` / `.query(nsid(...))` via
  // reverse codemod. `command`/`query` are now the only supported strict-typed forms.

  hasQuery(name: string): boolean {
    return this.queries.some((q) => q.name === name);
  }

  /** Auto-register standard CRUD + utility commands for a domain.
   *  Eliminates ~100 lines of boilerplate per app. Commands registered:
   *  - list, get, search, create (CRUD)
   *  - health, describe, stats, export, summarize, ingest, audit (utility) */
  autoCrud(config: AutoCrudConfig): App {
    this._autoCrudConfig = config;
    const { domain } = config;
    const conv = resolveAutoCrudConvention(config);
    const { ns, collection, fields, statuses, command } = conv;
    const readTable = config.readTable ?? `vertex_${toSnake(domain)}_${toSnake(config.label)}`;
    const nanoid = this.host.configGet("PERFORMER_ID") ?? this.host.configGet("APP_NANOID") ?? this.def.id;

    // ── CRUD commands ──

    this.command(command.list as any, async (_ctx, body) => {
      const args = decodeJson(body, {} as Record<string, unknown>);
      const limit = Math.min(Number(args.limit) || 50, 200);
      const offset = Number(args.offset) || 0;
      try {
        const rows = await listCollectionRows(readTable, (query) =>
          query.orderBy("_seq", "desc").offset(offset).limit(limit),
        );
        return { items: rows, offset, limit };
      } catch (error) {
        return queryFailurePayload(`list ${domain} records`, error);
      }
    }, asAgentTool(`List ${domain} records`), withCapabilityTags("query", domain));

    this.command(command.get as any, async (_ctx, body) => {
      const args = decodeJson(body, {} as Record<string, unknown>);
      const id = str(args.id ?? "");
      if (!id) return { error: "id required" };
      try {
        const row = await getCollectionRow(readTable, (query) =>
          query.where((eb: any) => eb.or([
            eb("id", "=", id),
            eb("rkey", "=", id),
            eb("vertex_id", "=", id),
          ])),
        );
        return row ?? { error: "not found" };
      } catch (error) {
        return queryFailurePayload(`get ${domain} record`, error);
      }
    }, asAgentTool(`Get ${domain} record by ID`), withCapabilityTags("query", domain));

    this.command(command.search as any, async (_ctx, body) => {
      const args = decodeJson(body, {} as Record<string, unknown>);
      const q = str(args.q ?? "");
      const limit = Math.min(Number(args.limit) || 20, 100);
      if (!q) return { items: [] };
      try {
        const rows = filterBySearch(
          sortByCreatedAt(await listCollectionRows(readTable, (query) => query.orderBy("_seq", "desc").limit(Math.min(limit * 10, 500)))),
          q,
          fields,
        ).slice(0, limit);
        return { items: rows };
      } catch (error) {
        return queryFailurePayload(`search ${domain} records`, error);
      }
    }, asAgentTool(`Search ${domain} records`), withCapabilityTags("search", domain));

    this.command(command.create as any, async (_ctx, body) => {
      const args = decodeJson(body, {} as Record<string, unknown>);
      const id = genID(domain);
      const record = { id, ...args, createdAt: nowISO(), ...rlsDefaults(nanoid) };
      if (this.pdsClient) {
        await this.pdsClient.comAtprotoRepoCreateRecord(collection, record);
      }
      return { id, status: "created" };
    }, asAgentTool(`Create ${domain} record`), withCapabilityTags("write", domain));

    // ── Utility commands ──

    this.command(command.health as any, (_ctx, _body) => ({
      status: "healthy", agent: domain, nanoid,
      did: `did:web:${nanoid}.etzhayyim.com`, ts: nowISO(),
    }), asAgentTool(`Health check for ${domain}`), withCapabilityTags("system", domain));

    this.command(command.describe as any, (_ctx, _body) => ({
      name: this.def.name, did: `did:web:${nanoid}.etzhayyim.com`, nanoid, domain,
      capabilities: this.commands.map((c) => c.name),
      protocols: ["xrpc", "w-protocol"],
    }), asAgentTool(`Describe ${domain} agent`), withCapabilityTags("system", domain));

    this.command(command.stats as any, async (_ctx, _body) => {
      try {
        const rows = filterByActor(await listCollectionRows(readTable), nanoid);
        const latestRow = sortByCreatedAt(rows)[0] ?? null;
        return {
          domain,
          nanoid,
          ts: nowISO(),
          total: rows.length,
          latest: latestRow ? rowField(latestRow, "createdAt", "created_at") ?? null : null,
        };
      } catch (error) {
        return queryFailurePayload(`get ${domain} stats`, error);
      }
    }, asAgentTool(`Get ${domain} stats`), withCapabilityTags("query", domain));

    this.command(command.export as any, async (_ctx, body) => {
      const args = decodeJson(body, {} as Record<string, unknown>);
      const limit = Math.min(Number(args.limit) || 100, 1000);
      try {
        const rows = sortByCreatedAt(filterByActor(await listCollectionRows(readTable), nanoid)).slice(0, limit);
        return { items: rows, count: rows.length, exportedAt: nowISO() };
      } catch (error) {
        return queryFailurePayload(`export ${domain} data`, error);
      }
    }, asAgentTool(`Export ${domain} data`), withCapabilityTags("query", domain));

    this.command(command.summarize as any, async (_ctx, body) => {
      const args = decodeJson(body, {} as Record<string, unknown>);
      const limit = Math.min(Number(args.limit) || 20, 50);
      try {
        const rows = sortByCreatedAt(filterByActor(await listCollectionRows(readTable), nanoid)).slice(0, limit);
        const summary = await llmAsk(`Summarize the following ${domain} data in 2-3 sentences: ${JSON.stringify(rows)}`);
        return { summary, recordCount: rows.length, ts: nowISO() };
      } catch (error) {
        return queryFailurePayload(`summarize ${domain} records`, error);
      }
    }, asAgentTool(`Summarize ${domain} records`), withCapabilityTags("query", domain));

    this.command(command.ingest as any, async (_ctx, body) => {
      const args = decodeJson(body, {} as Record<string, unknown>);
      const jobId = genID("ingest");
      const record = { id: jobId, domain, source: str(args.source ?? "manual"), status: "queued", createdAt: nowISO(), ...rlsDefaults(nanoid) };
      if (this.pdsClient) {
        await this.pdsClient.comAtprotoRepoCreateRecord(`${ns}.ingestJob`, record);
      }
      return { jobId, status: "queued" };
    }, asAgentTool(`Trigger ${domain} data ingest`), withCapabilityTags("write", domain));

    this.command(command.audit as any, async (_ctx, body) => {
      const args = decodeJson(body, {} as Record<string, unknown>);
      const limit = Math.min(Number(args.limit) || 50, 200);
      try {
        let rows = sortByCreatedAt(filterByActor(await listCollectionRows(readTable), nanoid));
        if (args.since) {
          const sinceTs = Date.parse(str(args.since));
          if (Number.isFinite(sinceTs)) {
            rows = rows.filter((row) => {
              const createdAt = rowField(row, "createdAt", "created_at");
              if (typeof createdAt !== "string") return false;
              const createdTs = Date.parse(createdAt);
              return Number.isFinite(createdTs) && createdTs >= sinceTs;
            });
          }
        }
        if (args.status) {
          const status = str(args.status);
          rows = rows.filter((row) => String(rowField(row, "status") ?? "") === status);
        }
        rows = rows.slice(0, limit);
        return { items: rows, count: rows.length, queriedAt: nowISO() };
      } catch (error) {
        return queryFailurePayload(`audit ${domain} records`, error);
      }
    }, asAgentTool(`Audit ${domain} records`), withCapabilityTags("query", domain));

    this.command(command.validate as any, (_ctx, body) => {
      const record = decodeJson(body, {} as Record<string, unknown>);
      const errors: string[] = [];
      if (!record.id) errors.push("id is required");
      if (typeof record.id === "string" && (record.id as string).length > 128) errors.push("id exceeds 128 chars");
      if (record.orgId && typeof record.orgId !== "string") errors.push("orgId must be string");
      if (record.createdAt && typeof record.createdAt === "string") {
        if (isNaN(Date.parse(record.createdAt as string))) errors.push("createdAt is not valid ISO date");
      }
      if (record.status && !statuses.includes(record.status as string)) {
        errors.push(`status must be one of: ${statuses.join(", ")}`);
      }
      return { valid: errors.length === 0, errors };
    }, asAgentTool(`Validate ${domain} record`), withCapabilityTags("system", domain));

    this.command(command.wave as any, (_ctx, body) => {
      const args = decodeJson(body, {} as Record<string, unknown>);
      const msg = str(args.message ?? "Hello");
      if (this.pdsClient) {
        this.pdsClient.dispatch({ type: "app.bsky.feed.post", payload: { text: `\u{1f44b} ${msg} \u2014 ${domain} agent reporting in!` } });
      }
      return { ok: true, agent: domain, nanoid };
    }, asAgentTool(`Send wave greeting from ${domain}`), withCapabilityTags("social", domain));

    return this;
  }

  /** Register a heartbeat hook — called after cadence resolution with extra domain-specific logic. */
  onHeartbeat(hook: HeartbeatHook): App {
    this._heartbeatHook = hook;
    return this;
  }

  /** Push inbound commit to inbox buffer (for cadence resolution). */
  pushInboundCommit(commit: InboundCommit): void {
    if (this._inbox.inboundCommits.length < 100) {
      this._inbox.inboundCommits.push(commit);
    }
  }

  /** Push inbound reaction to inbox buffer. */
  pushInboundReaction(reaction: InboundReaction): void {
    if (this._inbox.reactions.length < 50) {
      this._inbox.reactions.push(reaction);
    }
  }

  /** Run default heartbeat — joucho cadence + follower rewards + optional hook.
   *  Called by shinkaHandler.onHeartbeat in index.ts. Apps no longer need to export runHeartbeat(). */
  async runDefaultHeartbeat(): Promise<{ ok: boolean; actions: Array<Record<string, unknown>> }> {
    const actions: Array<Record<string, unknown>> = [];
    const ts = nowISO();
    const nanoid = this.host.configGet("PERFORMER_ID") ?? this.host.configGet("APP_NANOID") ?? this.def.id;
    const did = `did:web:${nanoid}.etzhayyim.com`;

    // Check own profile completeness before cadence resolution
    try {
      const profileRow = await getDb()
        .selectFrom("vertex_profile")
        .selectAll()
        .where((eb: any) => eb.or([
          eb("repo", "=", did),
          eb("did", "=", did),
        ]))
        .limit(1)
        .executeTakeFirst();
      this._inbox.profileIncomplete = !profileRow;
      if (this._inbox.profileIncomplete) {
        console.warn(`[heartbeat] profileIncomplete did=${did}`);
        try {
          this.host.ocelEmitEvent(JSON.stringify({
            specVersion: "ocel.v2", eventType: "agent.profileIncomplete",
            phase: "start", status: "started", appId: this.def.id,
            command: "dataRepair", actorDid: did, ts: nowISO(),
          }));
        } catch { /* best-effort */ }
      }
    } catch (e) {
      console.warn("heartbeat profile check:", e);
    }

    const cadence = await resolveHeartbeatCadence(did, this._cadenceState, this._inbox);
    actions.push({ action: "cadenceResolved", mood: cadence.mood, reason: cadence.reason, ts, profileIncomplete: this._inbox.profileIncomplete });

    if (cadence.shouldPost && cadence.contentSource.type !== "none" && this.pdsClient) {
      try {
        const domain = this._autoCrudConfig?.domain ?? this.def.name ?? nanoid;
        const source = cadence.contentSource;
        const taskPrompt = source.type === "inbound"
          ? `You received new data from: ${(source as { detail?: string }).detail ?? "unknown"}.
Step 1: Inspect your current records using the app's available read paths.
Step 2: Call post to share an insight about this update with your followers.
You MUST inspect data before posting and then call post.`
          : `You are an AI agent for "${domain}" (DID: did:web:${nanoid}.etzhayyim.com).
Step 1: Inspect your current data using the app's available read paths.
Step 2: Based on the results, call post to share a useful insight about "${domain}" with your followers. If no data exists, post about what you plan to investigate.
You MUST inspect data before posting and then call post.`;
        const result = await agentReact(taskPrompt, {
          systemPrompt: this.defaultAgentSystemPrompt(),
          model: this.def.agent?.model,
          maxIterations: 5,
        });
        this._cadenceState.lastPostAt = Date.now();
        actions.push({ action: "post", source: source.type, iterations: result.iterations, tools: result.toolCallLog.map(t => t.name), ts });
      } catch (e) {
        console.warn("heartbeat post:", e);
        actions.push({ action: "post_failed", error: String(e), ts });
      }
    }

    if (cadence.shouldEngage && cadence.followerRewards.length > 0 && this.pdsClient) {
      for (const reward of cadence.followerRewards.slice(0, 5)) {
        try {
          if (reward.latestPostUri) {
            await this.pdsClient.comAtprotoRepoCreateRecord("app.bsky.feed.like", {
              subject: { uri: reward.latestPostUri, cid: "" },
              createdAt: nowISO(),
            });
            actions.push({ action: "followerReward", did: reward.did, type: reward.rewardType });
          }
        } catch (e) { console.warn("followerReward:", e); }
      }
      this._cadenceState.lastEngageAt = Date.now();
    }

    if (cadence.shouldDrill) {
      try {
        const domain = this._autoCrudConfig?.domain ?? this.def.name ?? nanoid;
        const result = await agentReact(
          `You are an AI agent for "${domain}" (DID: did:web:${nanoid}.etzhayyim.com). Perform kyumei-koji (究明工事) — self-information gathering.

Step 1: Inspect your current records using the app's available read paths.
Step 2: Call web_fetch to gather domain knowledge. Fetch a relevant source URL for "${domain}" (e.g. a Wikipedia page, industry report, or news source).
Step 3: Call create_record to persist your findings as a kyumei result:
  collection: "com.etzhayyim.apps.${domain}.kyumeiResult"
  record: { topic: "<what you investigated>", source: "<URL>", summary: "<key findings>", gaps: "<what's still missing>", createdAt: "<ISO timestamp>" }
Step 4: Call post to announce your findings to followers.

You MUST inspect data, then call web_fetch, create_record, and post in that order.`,
          { systemPrompt: this.defaultAgentSystemPrompt(), model: this.def.agent?.model, maxIterations: 8 },
        );
        this._cadenceState.lastDrillAt = Date.now();
        actions.push({ action: "drill", insight: result.content.slice(0, 500), iterations: result.iterations, tools: result.toolCallLog.map(t => t.name), ts });
      } catch (e) { console.warn("drill:", e); }
    }

    if (cadence.shouldRepair && this.pdsClient) {
      try {
        const domain = this._autoCrudConfig?.domain ?? this.def.name ?? nanoid;
        const result = await agentReact(
          `You are an AI agent for "${domain}" (DID: did:web:${nanoid}.etzhayyim.com). Your profile data is MISSING — you need to repair it immediately.

Step 1: Inspect your current records using the app's available read paths.
Step 2: Call web_fetch to investigate your domain "${domain}" and gather information for your profile.
Step 3: Call put_profile to set your profile:
  displayName: "<appropriate name for ${domain}>"
  description: "<what this agent does, based on your research>"
Step 4: Call post to announce that you have initialized your profile.

You MUST inspect data, then call the repair tools.`,
          { systemPrompt: this.defaultAgentSystemPrompt(), model: this.def.agent?.model, maxIterations: 8 },
        );
        this._inbox.profileIncomplete = false;
        actions.push({ action: "dataRepair", iterations: result.iterations, tools: result.toolCallLog.map(t => t.name), ts });
        try {
          this.host.ocelEmitEvent(JSON.stringify({
            specVersion: "ocel.v2", eventType: "agent.dataRepairCompleted",
            phase: "success", status: "ok", appId: this.def.id,
            command: "dataRepair", actorDid: did, ts: nowISO(),
            iterations: result.iterations,
          }));
        } catch { /* best-effort */ }
      } catch (e) {
        console.warn("dataRepair:", e);
        actions.push({ action: "dataRepair_failed", error: String(e), ts });
        try {
          this.host.ocelEmitEvent(JSON.stringify({
            specVersion: "ocel.v2", eventType: "agent.dataRepairFailed",
            phase: "error", status: "error", appId: this.def.id,
            command: "dataRepair", actorDid: did, ts: nowISO(),
            error: String(e),
          }));
        } catch { /* best-effort */ }
      }
    }

    if (cadence.shouldAnalyze && this._autoCrudConfig) {
      try {
        const collection = resolveAutoCrudConvention(this._autoCrudConfig).collection;
        const readTable = this._autoCrudConfig.readTable ?? `vertex_${toSnake(this._autoCrudConfig.domain)}_${toSnake(this._autoCrudConfig.label)}`;
        const rows = filterByActor(await listCollectionRows(readTable), nanoid);
        this._cadenceState.lastAnalyzeAt = Date.now();
        actions.push({
          action: "analyze",
          stats: {
            total: rows.length,
            latest: sortByCreatedAt(rows)[0] ? rowField(sortByCreatedAt(rows)[0], "createdAt", "created_at") : null,
          },
          ts,
        });
      } catch (e) { console.warn("analyze:", e); }
    }

    if (cadence.shouldValidate && this._autoCrudConfig) {
      try {
        const collection = resolveAutoCrudConvention(this._autoCrudConfig).collection;
        const readTable = this._autoCrudConfig.readTable ?? `vertex_${toSnake(this._autoCrudConfig.domain)}_${toSnake(this._autoCrudConfig.label)}`;
        const weekAgo = new Date(Date.now() - 7 * 24 * 3600_000).toISOString();
        const stale = filterByActor(await listCollectionRows(readTable), nanoid).filter((row) => {
          const createdAt = rowField(row, "createdAt", "created_at");
          return typeof createdAt === "string" && createdAt < weekAgo;
        });
        this._cadenceState.lastValidateAt = Date.now();
        const cnt = stale.length;
        if (cnt > 0) actions.push({ action: "validate", staleCount: cnt, ts });
      } catch (e) { console.warn("validate:", e); }
    }

    // Run app-specific hook if registered
    if (this._heartbeatHook && this.pdsClient) {
      try {
        const extra = await this._heartbeatHook(cadence, { pds: this.pdsClient, hostImports: this.host });
        actions.push(...extra);
      } catch (e) { console.warn("heartbeatHook:", e); }
    }

    if (actions.length === 1) actions.push({ action: "noop", mood: cadence.mood, ts });
    return { ok: true, actions };
  }

  /** Register a generic commit handler called for every incoming AT commit. */
  onCommit(handler: (commit: ComAtprotoSyncSubscribeReposCommit) => void | Promise<void>): App {
    this._commitHandler = handler;
    return this;
  }

  /** Default commit handler — buffers inbound commits for cadence, returns ok.
   *  Apps can override with custom logic via wHandler. */
  handleDefaultCommit(commit: ComAtprotoSyncSubscribeReposCommit): { ok: true; detail: string } {
    if (commit.action === "create") {
      this.pushInboundCommit({
        collection: commit.collection,
        repo: commit.repo,
        rkey: commit.rkey,
        time: commit.time,
      });
    }
    // Call registered onCommit handler
    if (this._commitHandler) {
      try {
        const r = this._commitHandler(commit);
        if (r instanceof Promise) r.catch((e) => console.warn("[onCommit] handler error:", e));
      } catch (e) {
        console.warn("[onCommit] handler error:", e);
      }
    }
    // Delegate to registered wRoutes (existing behavior)
    const existing = this.comAtprotoSyncSubscribeRepos(commit);
    if (existing) return { ok: true, detail: existing };

    const domain = this._autoCrudConfig?.domain ?? "";
    if (domain && commit.collection.startsWith(`com.etzhayyim.apps.${domain}.`)) {
      return { ok: true, detail: `processed ${commit.collection}` };
    }
    if (commit.collection === "app.bsky.feed.like") {
      return { ok: true, detail: "engagement noted" };
    }
    return { ok: true, detail: "commit accepted" };
  }

  handleConversationMessage(fn: ConversationHandler): App {
    this._conversationHandler = fn;
    return this;
  }

  handleRemoteCall(iface: string, fn: string, handler: RemoteCallHandler): App {
    this.remoteHandlers.set(`${iface}/${fn}`, handler);
    return this;
  }

  /** Async registration via XrpcClient (awaited, errors propagate). */
  async serveAsync(): Promise<void> {
    if (this._served) return;
    this._served = true;
    if (this.pdsClient) {
      await this.registerGovernanceManifest();
    } else {
      console.error("[serveAsync] XrpcClient is null — governance manifest registration skipped.");
    }
  }

  private async registerGovernanceManifest(): Promise<void> {
    const pds = this.pdsClient!;
    await pds.governanceRegisterManifest(JSON.stringify(buildGovernanceManifestFromCommands(this.def, this.commands)));
  }

  // ── HTTP handling ───────────────────────────────────────────────────

  /** XRPC dispatch: POST /xrpc/{NSID}. */
  async handleXRPC(
    path: string, headers: [string, string][], body: Uint8Array,
  ): Promise<{ status: number; headers: [string, string][]; body: Uint8Array }> {
    const nsid = path.replace(/^\/xrpc\//, "");
    const eventType = defaultXrpcOcelEventType(nsid);
    const context = this.resolveContext(headers);
    const handler = resolveXrpcMethod(nsid, this.methodMap);
    if (!handler) {
      const managed: ManagedCommandError = {
        code: "XRPC_UNKNOWN_METHOD",
        message: `unknown xrpc method: ${nsid}`,
        status: 404,
        retryable: false,
      };
      this.emitOcelV2(undefined, "start", context, nsid, "started", undefined, undefined, eventType);
      this.emitOcelV2(undefined, "error", context, nsid, "error", 0, managed, eventType);
      return respondJson(404, {
        error: managed.message,
        errorCode: managed.code,
        retryable: managed.retryable,
      });
    }
    const methodName = this.findCommandEntryByHandler(handler)?.name ?? nsid;
    try {
      // Hard wall-clock timeout so a handler that never resolves (Hyperdrive
      // pool stall, PDS service binding hang) returns 504 instead of leaving
      // the Worker runtime to trip its "code had hung" detector and kill the
      // entire request. Default 25s — keeps us under CF's 30s fetch cap.
      const TIMEOUT_MS = 25_000;
      const result = await Promise.race([
        this.executeCommand(methodName, handler, context, body, eventType),
        new Promise<never>((_, reject) =>
          setTimeout(
            () => reject(Object.assign(new Error(`xrpc timeout: ${methodName}`), { status: 504, code: "XRPC_TIMEOUT" })),
            TIMEOUT_MS,
          ),
        ),
      ]);
      return toSuccessResponse(result);
    } catch (error) {
      const managed = this.resolveManagedError(error, "XRPC_HANDLER_FAILED");
      return respondJson(managed.status, {
        error: managed.message,
        errorCode: managed.code,
        retryable: managed.retryable,
        ...(managed.details ? { details: managed.details } : {}),
      });
    }
  }

  /** Direct command dispatch by method name (POST /{methodName}). */
  async handleCommand(
    methodName: string, headers: [string, string][], body: Uint8Array,
  ): Promise<{ status: number; headers: [string, string][]; body: Uint8Array }> {
    const handler = this.methodMap.get(methodName);
    if (!handler) return respondJson(404, { error: "not found" });
    const context = this.resolveContext(headers);
    try {
      const result = await this.executeCommand(methodName, handler, context, body);
      return toSuccessResponse(result);
    } catch (error) {
      const managed = this.resolveManagedError(error, "COMMAND_HANDLER_FAILED");
      return respondJson(managed.status, {
        error: managed.message,
        errorCode: managed.code,
        retryable: managed.retryable,
        ...(managed.details ? { details: managed.details } : {}),
      });
    }
  }

  // ── AT Protocol repo commit handling ─────────────────────────────

  comAtprotoSyncSubscribeRepos(commit: ComAtprotoSyncSubscribeReposCommit): string | null {
    if (commit.collection === "com.etzhayyim.convo.message" && commit.action === "create") {
      return this.dispatchConversationCommit(commit);
    }

    const methodName = this.wRoutes.get(commit.collection);
    if (!methodName) return null;

    const handler = this.methodMap.get(methodName);
    if (!handler) return null;

    const histJson = this.host.conversationGetHistory(commit.rkey);
    const ctx: AppContext = {
      orgId: "anon", userId: "anon", actorId: commit.repo,
      convoId: "", appId: this.def.id, now: new Date().toISOString(),
    };

    try {
      handler(ctx, new TextEncoder().encode(histJson));
      return null;
    } catch (e) {
      return String(e);
    }
  }

  dispatchRemoteCall(
    iface: string, fn: string, paramsCbor: Uint8Array, callerDid: string, callerOrgId: string,
  ): Uint8Array {
    const remoteHandler = this.remoteHandlers.get(`${iface}/${fn}`)
      ?? this.remoteHandlers.get(`${iface}/${toSnake(fn)}`)
      ?? this.remoteHandlers.get(`${iface}/${toKebab(fn)}`);

    if (remoteHandler) return remoteHandler(paramsCbor, callerDid, callerOrgId);

    const commandHandler = this.methodMap.get(fn)
      ?? this.methodMap.get(toSnake(fn))
      ?? this.methodMap.get(toKebab(fn));

    if (!commandHandler) throw new Error(`unknown remote function: ${iface}/${fn}`);

    const ctx: AppContext = {
      orgId: callerOrgId || "anon", userId: callerDid || "anon",
      actorId: callerDid || "anon", convoId: "",
      appId: this.def.id, now: new Date().toISOString(),
    };
    return commandHandler(ctx, paramsCbor) as unknown as Uint8Array;
  }

  private dispatchConversationCommit(commit: ComAtprotoSyncSubscribeReposCommit): string | null {
    let plainJson: Uint8Array;
    try {
      const histJson = this.host.conversationGetHistory(commit.rkey);
      plainJson = conversationSecureDecrypt(commit.rkey, new TextEncoder().encode(histJson)) as Uint8Array;
    } catch (e) {
      return String(e);
    }

    let msg: ConversationMessage;
    try { msg = JSON.parse(new TextDecoder().decode(plainJson)); }
    catch (e) { return `conversation: unmarshal message: ${e}`; }

    const myNanoid = this.host.configGet("PERFORMER_ID") ?? this.host.configGet("APP_NANOID") ?? "";
    if (msg.from === myNanoid) return null;

    const ctx: AppContext = {
      orgId: "anon", userId: "anon", actorId: msg.from,
      convoId: "", appId: this.def.id, now: new Date().toISOString(),
    };

    try {
      const handler = this._conversationHandler ?? ((c, m) => this.defaultConversationHandler(c, m));
      handler(ctx, msg);
      return null;
    } catch (e) {
      return String(e);
    }
  }

  private defaultConversationHandler(_ctx: AppContext, msg: ConversationMessage): void {
    const content = msg.content.trim();
    if (!content) return;

    const model = this.def.agent?.model?.trim();

    // ReAct loop: agent can think, call tools, observe, and respond autonomously.
    void agentReact(content, {
      systemPrompt: this.defaultAgentSystemPrompt(),
      model,
      maxIterations: 5,
      llmOptions: { contextId: msg.sessionId, scrubPii: true },
    }).then((result) => {
      const answer = result.content.trim();
      if (!answer) return;
      if (msg.messageId) { reply(msg.sessionId, answer, msg.messageId); return; }
      say(msg.sessionId, answer);
    }).catch((e) => console.warn("conversation handler:", e));
  }

  // ── Context resolution ────────────────────────────────────────────

  private resolveContext(headers: [string, string][]): AppContext {
    return resolveAppContext(this.def.id, this.host, headers);
  }

  private defaultAgentSystemPrompt(): string {
    return buildDefaultAgentSystemPrompt(this.def, this.commands);
  }
}
