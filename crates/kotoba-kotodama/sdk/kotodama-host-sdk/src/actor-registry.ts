/**
 * actor-registry.ts — Shared helper for graph-native multi-DID actor management.
 *
 * Replaces hardcoded OrgDef[] arrays with graph-seeded data. Provides:
 * - Seed: write actor definitions to graph as domain records
 * - DID registration: chunked path-based DID creation across heartbeats
 * - Query: dynamic graph reads for ingestion, hierarchy, tags
 * - Follow: auto-follow parent/dependency actors
 * - Governance: register manifest for actor capabilities
 *
 * Used by: states (gov orgs), pachinko (machines/stores), ISCO (occupations), etc.
 */

import type { XrpcClient } from "./xrpc-client.js";
// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import { createKyselyDb } from "./kysely.js";
import { str, nowISO } from "./helpers.js";
import { USE_CASE_DEFAULTS } from "./llm-model-registry.js";

// ── Types ──

/** Actor definition for seeding into graph. */
export interface ActorDef {
  path: string;
  name: string;
  nameEn: string;
  tags: string[];
  contract?: string;
  website?: string;
  parentPath?: string;
  metadata?: Record<string, unknown>;
  children?: ActorDef[];
}

/** Configuration for ActorRegistry instance. */
export interface ActorRegistryConfig {
  /** Actor type discriminator (e.g. "gov-org", "machine", "occupation"). */
  actorType: string;
  /** Country/domain code (e.g. "jpn", "pachinko", "isco"). */
  domainCode: string;
  /** Collection prefix for domain records (e.g. "states", "pachinko"). */
  collectionPrefix: string;
  /** App nanoid for orgId/actorId fields. */
  appNanoid: string;
  /** DID host prefix (e.g. "gov-jpn" → did:web:gov-jpn.etzhayyim.com:{path}). */
  didHostPrefix: string;
}

/** Result of a seed operation. */
export interface SeedResult {
  seeded: number;
  total: number;
  offset: number;
  done: boolean;
}

/** Result of a DID registration batch. */
export interface RegisterResult {
  registered: number;
  paths: string[];
}

/** A row from the graph representing a registered actor. */
export interface ActorRow {
  path: string;
  name: string;
  nameEn: string;
  website: string;
  tags: string;
  contract: string;
  parentPath: string;
  didRegistered: string;
  lastIngestedAt?: string;
  lastContentHash?: string;
  lastKyumeiAt?: string;
  lastShinkaAt?: string;
}

/** Result of a delta-aware ingestion. */
export interface IngestDelta {
  path: string;
  changed: boolean;
  contentHash: string;
  prevHash: string;
}

/** Result of per-actor kyumei-koji. */
export interface KyumeiResult {
  path: string;
  factsCount: number;
  summary: string;
}

/** LLM function signature (injected by app, avoids SDK depending on llm.ts circular). */
export type LLMFn = (prompt: string, opts?: { useCase?: string }) => Promise<string>;

/** LLM JSON function signature. */
export type LLMJsonFn = (system: string, user: string, model?: string) => Promise<Record<string, unknown>>;

type AnyRow = Record<string, unknown>;
type KyselyDb = ReturnType<typeof createKyselyDb>;

function normalizeActorRow(row: AnyRow | null | undefined): ActorRow | null {
  if (!row) return null;
  return {
    path: str(row.path),
    name: str(row.name),
    nameEn: str(row.name_en ?? row.nameEn),
    website: str(row.website),
    tags: Array.isArray(row.tags) ? JSON.stringify(row.tags.map((item) => String(item))) : str(row.tags),
    contract: str(row.contract),
    parentPath: str(row.parent_path ?? row.parentPath),
    didRegistered: str(row.did_registered ?? row.didRegistered),
    lastIngestedAt: row.last_ingested_at || row.lastIngestedAt ? String(row.last_ingested_at ?? row.lastIngestedAt) : undefined,
    lastContentHash: row.last_content_hash || row.lastContentHash ? String(row.last_content_hash ?? row.lastContentHash) : undefined,
    lastKyumeiAt: row.last_kyumei_at || row.lastKyumeiAt ? String(row.last_kyumei_at ?? row.lastKyumeiAt) : undefined,
    lastShinkaAt: row.last_shinka_at || row.lastShinkaAt ? String(row.last_shinka_at ?? row.lastShinkaAt) : undefined,
  };
}

function parseStringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item));
  if (typeof value !== "string" || value.length === 0) return [];
  try {
    const parsed = JSON.parse(value) as unknown;
    return Array.isArray(parsed) ? parsed.map((item) => String(item)) : [value];
  } catch {
    return [value];
  }
}

function isTruthyString(value: unknown): boolean {
  return str(value).trim() !== "";
}

function isFalseLike(value: unknown): boolean {
  const normalized = str(value).trim().toLowerCase();
  return normalized === "" || normalized === "false" || normalized === "0" || normalized === "null" || normalized === "undefined";
}

function toMillis(value: unknown): number {
  const n = Number(str(value));
  return Number.isFinite(n) ? n : 0;
}

let db: KyselyDb | null = null;

function getDb(): KyselyDb {
  if (!db) db = createKyselyDb();
  return db;
}

// ── Implementation ──

/** Flatten a tree of ActorDefs into a flat array with computed full paths. */
export function flattenActorDefs(defs: ActorDef[], parentPath = ""): Array<{ path: string; parentPath: string; def: ActorDef }> {
  const result: Array<{ path: string; parentPath: string; def: ActorDef }> = [];
  for (const d of defs) {
    const fullPath = parentPath ? parentPath + ":" + d.path : d.path;
    result.push({ path: fullPath, parentPath: d.parentPath ?? parentPath, def: d });
    if (d.children) result.push(...flattenActorDefs(d.children, fullPath));
  }
  return result;
}

/**
 * ActorRegistry — graph-native multi-DID actor management.
 *
 * ```typescript
 * const actors = new ActorRegistry(sdk.pds, {
 *   actorType: "gov-org", domainCode: "jpn",
 *   collectionPrefix: "states", appNanoid: "g0vjpn01",
 *   didHostPrefix: "gov-jpn",
 * });
 * await actors.seed(ministries, 0, 50);       // seed 50 orgs to graph
 * await actors.registerDids(20);               // register 20 DIDs
 * const next = await actors.nextForIngestion(); // pick next org with website
 * await actors.follow("upstream-nanoid");       // follow dependency
 * ```
 */
export class ActorRegistry {
  private pds: XrpcClient;
  private cfg: ActorRegistryConfig;

  constructor(pds: XrpcClient, config: ActorRegistryConfig) {
    this.pds = pds;
    this.cfg = config;
  }

  private actorCollection(): string {
    return this.cfg.collectionPrefix + "." + this.cfg.actorType.replace(/-/g, "");
  }

  private baseQuery() {
    if (this.cfg.collectionPrefix === "states" && this.cfg.actorType === "gov-org") {
      return getDb()
        .selectFrom("vertex_gov_org" as any)
        .selectAll()
        .where("domain_code" as any, "=", this.cfg.domainCode);
    }
    throw new Error(`ActorRegistry requires a typed table for ${this.actorCollection()}`);
  }

  private async listActorRows(build?: (query: any) => any): Promise<ActorRow[]> {
    let query: any = this.baseQuery();
    if (build) query = build(query);
    const rows = await query.execute();
    return rows.map((row: AnyRow) => normalizeActorRow(row)).filter((row: ActorRow | null): row is ActorRow => row !== null);
  }

  private async firstActorRow(build?: (query: any) => any): Promise<ActorRow | null> {
    const rows = await this.listActorRows((query) => {
      const next = build ? build(query) : query;
      return next.limit(1);
    });
    return rows[0] ?? null;
  }

  // ── Seed ──

  /**
   * Write a batch of ActorDefs to graph as domain records. Idempotent.
   * Returns how many were seeded and whether seeding is complete.
   */
  async seed(defs: ActorDef[], offset = 0, batchSize = 30): Promise<SeedResult> {
    const flat = flattenActorDefs(defs);
    const batch = flat.slice(offset, offset + batchSize);
    let seeded = 0;
    for (const entry of batch) {
      try {
        await this.pds.comAtprotoRepoCreateRecord(this.cfg.collectionPrefix + "." + this.cfg.actorType.replace(/-/g, ""), {
          path: entry.path,
          parentPath: entry.parentPath,
          name: entry.def.name,
          nameEn: entry.def.nameEn,
          contract: entry.def.contract || "",
          tags: entry.def.tags,
          website: entry.def.website || "",
          actorType: this.cfg.actorType,
          domainCode: this.cfg.domainCode,
          didRegistered: false,
          ...(entry.def.metadata || {}),
          orgId: "service",
          userId: "service",
          actorId: this.cfg.appNanoid,
          createdAt: nowISO(),
        });
        seeded++;
      } catch (e) {
        console.warn(`[ActorRegistry.seed] ${entry.path}:`, e);
      }
    }
    return { seeded, total: flat.length, offset: offset + batchSize, done: offset + batchSize >= flat.length };
  }

  // ── DID Registration (chunked) ──

  /** Register path-based DIDs for unregistered actors in graph. */
  async registerDids(batchSize = 10): Promise<RegisterResult> {
    const rows = (await this.listActorRows())
      .filter((row) => isFalseLike(row.didRegistered))
      .sort((a, b) => a.path.localeCompare(b.path))
      .slice(0, Math.max(0, batchSize));
    const paths: string[] = [];
    for (const row of rows) {
      const path = str(row.path);
      if (!path) continue;
      let desc = "[AI Agent — unofficial] " + str(row.nameEn);
      if (row.contract) desc += " — " + str(row.contract);
      try {
        await this.pds.comAtprotoIdentityCreate(path, {
          displayName: str(row.name) + " (" + str(row.nameEn) + ")",
          description: desc,
        });
        paths.push(path);
      } catch (e) {
        console.warn(`[ActorRegistry.registerDids] ${path}:`, e);
      }
    }
    return { registered: paths.length, paths };
  }

  // ── Query ──

  /** Count actors in graph for this domain. */
  async count(): Promise<number> {
    const row = await this.baseQuery()
      .select((db) => db.fn.countAll().as("cnt"))
      .executeTakeFirst();
    return Number((row as AnyRow | undefined)?.cnt ?? 0);
  }

  /** Get next actor with a website for ingestion (round-robin via offset). */
  async nextForIngestion(offset = 0): Promise<ActorRow | null> {
    const rows = (await this.listActorRows())
      .filter((row) => isTruthyString(row.website))
      .sort((a, b) => a.path.localeCompare(b.path));
    return rows[offset] ?? null;
  }

  /** Find an actor by path. */
  async findByPath(path: string): Promise<ActorRow | null> {
    return await this.firstActorRow((query) => query.where("path", "=", path));
  }

  /** List actors by tag. */
  async listByTag(tag: string, limit = 20): Promise<ActorRow[]> {
    return (await this.listActorRows())
      .filter((row) => parseStringArray(row.tags).includes(tag))
      .sort((a, b) => a.path.localeCompare(b.path))
      .slice(0, Math.max(0, limit));
  }

  // ── Follow (dependency management) ──

  /** Follow an upstream actor (e.g. resource-flow provider). */
  async follow(targetNanoid: string): Promise<void> {
    await this.pds.appBskyGraphFollow(targetNanoid);
  }

  // ── Delta-aware ingestion ──

  /**
   * Get next actor that needs ingestion (oldest lastIngestedAt, or never ingested).
   * Prioritizes actors never ingested, then oldest.
   */
  async nextStaleForIngestion(maxAgeMs = 24 * 60 * 60 * 1000): Promise<ActorRow | null> {
    const cutoff = Date.now() - maxAgeMs;
    const rows = (await this.listActorRows()).filter((row) => isTruthyString(row.website));
    const never = rows
      .filter((row) => !isTruthyString(row.lastIngestedAt))
      .sort((a, b) => a.path.localeCompare(b.path));
    if (never.length > 0) return never[0] ?? null;
    const stale = rows
      .filter((row) => toMillis(row.lastIngestedAt) < cutoff)
      .sort((a, b) => toMillis(a.lastIngestedAt) - toMillis(b.lastIngestedAt));
    return stale[0] ?? null;
  }

  /** Simple content hash for delta detection (FNV-1a 32-bit of content string). */
  contentHash(content: string): string {
    let h = 0x811c9dc5;
    for (let i = 0; i < content.length; i++) {
      h ^= content.charCodeAt(i);
      h = Math.imul(h, 0x01000193);
    }
    return (h >>> 0).toString(16);
  }

  /**
   * Record ingestion result with delta tracking.
   * Updates lastIngestedAt + lastContentHash on the actor node.
   * Returns whether content changed since last ingest.
   */
  async recordIngest(path: string, content: string, analysis: string): Promise<IngestDelta> {
    const hash = this.contentHash(content);
    const actor = await this.findByPath(path);
    const prevHash = str(actor?.lastContentHash ?? "");
    const changed = !prevHash || prevHash !== hash;

    // Write ingest result as domain record
    await this.pds.comAtprotoRepoCreateRecord(this.cfg.collectionPrefix + ".ingestResult", {
      actorPath: path, contentHash: hash, prevHash: prevHash,
      changed, analysis: analysis.slice(0, 500),
      ingestedAt: nowISO(),
      orgId: "service", userId: "service", actorId: this.cfg.appNanoid,
      createdAt: nowISO(),
    });

    // Update actor node timestamps via putRecord
    const rkey = path.replace(/:/g, "_");
    await this.pds.comAtprotoRepoPutRecord(
      this.cfg.collectionPrefix + "." + this.cfg.actorType.replace(/-/g, ""),
      rkey,
      { lastIngestedAt: String(Date.now()), lastContentHash: hash },
    );

    return { path, changed, contentHash: hash, prevHash };
  }

  // ── Per-actor Kyumei-Koji (究明工事) ──

  /**
   * Get next actor that needs kyumei-koji (self-information gathering).
   * Prioritizes actors never investigated, then oldest.
   */
  async nextStaleForKyumei(maxAgeMs = 7 * 24 * 60 * 60 * 1000): Promise<ActorRow | null> {
    const cutoff = Date.now() - maxAgeMs;
    const rows = await this.listActorRows();
    const never = rows
      .filter((row) => !isTruthyString(row.lastKyumeiAt))
      .sort((a, b) => a.path.localeCompare(b.path));
    if (never.length > 0) return never[0] ?? null;
    const stale = rows
      .filter((row) => toMillis(row.lastKyumeiAt) < cutoff)
      .sort((a, b) => toMillis(a.lastKyumeiAt) - toMillis(b.lastKyumeiAt));
    return stale[0] ?? null;
  }

  /**
   * Run kyumei-koji for a specific actor: LLM gathers facts → domain record + social post.
   * Requires LLM functions injected from app (avoids SDK circular dependency).
   */
  async runKyumei(actor: ActorRow, llmJson: LLMJsonFn): Promise<KyumeiResult> {
    const actorName = `${str(actor.name)} (${str(actor.nameEn)})`;
    const actorContract = str(actor.contract) || "unknown";
    const did = this.didFor(str(actor.path));

    const result = await llmJson(
      "You are a government/organization research agent. Analyze the given organization and return structured facts. Return JSON: { facts: [{key, value, confidence}], summary: string }",
      `Organization: ${actorName}\nLegal basis: ${actorContract}\nDID: ${did}\nTags: ${str(actor.tags)}\nGather: mandate, jurisdiction, responsibilities, reforms, structure, budget, personnel.`,
      USE_CASE_DEFAULTS["kyumei-koji"],
    );

    const facts = Array.isArray(result.facts) ? result.facts : [];
    const summary = str(result.summary);

    // Write kyumei result as domain record
    await this.pds.comAtprotoRepoCreateRecord(this.cfg.collectionPrefix + ".kyumeiResult", {
      actorPath: str(actor.path), actorName: actorName,
      factsCount: facts.length, factsJson: JSON.stringify(facts),
      summary, gatheredAt: nowISO(),
      orgId: "service", userId: "service", actorId: this.cfg.appNanoid,
      createdAt: nowISO(),
    });

    // Update lastKyumeiAt on actor node
    const rkey = str(actor.path).replace(/:/g, "_");
    await this.pds.comAtprotoRepoPutRecord(
      this.cfg.collectionPrefix + "." + this.cfg.actorType.replace(/-/g, ""),
      rkey,
      { lastKyumeiAt: String(Date.now()) },
    );

    return { path: str(actor.path), factsCount: facts.length, summary };
  }

  // ── Per-actor Shinka (進化) ──

  /**
   * Get next actor due for shinka social evolution post.
   * Rotates through actors, prioritizing those with oldest lastShinkaAt.
   */
  async nextForShinka(maxAgeMs = 4 * 60 * 60 * 1000): Promise<ActorRow | null> {
    const cutoff = Date.now() - maxAgeMs;
    const rows = (await this.listActorRows())
      .filter((row) => !isTruthyString(row.lastShinkaAt) || toMillis(row.lastShinkaAt) < cutoff)
      .sort((a, b) => toMillis(a.lastShinkaAt) - toMillis(b.lastShinkaAt));
    return rows[0] ?? null;
  }

  /**
   * Record that shinka post was made for this actor.
   * Updates lastShinkaAt timestamp.
   */
  async recordShinka(path: string): Promise<void> {
    const rkey = path.replace(/:/g, "_");
    await this.pds.comAtprotoRepoPutRecord(
      this.cfg.collectionPrefix + "." + this.cfg.actorType.replace(/-/g, ""),
      rkey,
      { lastShinkaAt: String(Date.now()) },
    );
  }

  // ── DID helpers ──

  /** Build full DID from actor path. */
  didFor(path: string): string {
    return `did:web:${this.cfg.didHostPrefix}.etzhayyim.com:${path}`;
  }

  /** Build primary (root) DID. */
  primaryDid(): string {
    return `did:web:${this.cfg.didHostPrefix}.etzhayyim.com`;
  }

  /** Get config. */
  get config(): ActorRegistryConfig {
    return this.cfg;
  }
}
