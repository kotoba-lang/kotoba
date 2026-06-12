// langserver-actor.ts — Kotodama actor wrapper around a per-taxonomy
// LangGraph Pregel langserver. See ADR-2605180900.
//
// The actor is a thin HTTP client targeting an in-cluster langserver
// Service DNS. Each method corresponds 1:1 to a lexicon under
// `00-contracts/lexicons/com/etzhayyim/apps/{taxonomy}/`, so request shapes
// stay drift-free with the XRPC and MCP surfaces.
//
//   const unispsc = createUnispscActor({
//     endpoint: "http://lg-open-unispsc.lg-open-unispsc.svc:80",
//   });
//   const { candidates } = await unispsc.classify({ description: "..." });
//   const result = await unispsc.invokeAgent({ code: "10101501", payload: {...} });
//
// `fetcher` defaults to global fetch. CF Worker callers pass a Service
// binding via `fetcher: env.LG_OPEN_UNISPSC` so the call stays on the
// internal network without DNS resolution.

export type Taxonomy = "unispsc" | "isic";

export type ModelHint = "haiku-4.5" | "sonnet-4.6" | "auto";

export interface LangserverActorConfig {
  /** Taxonomy this actor speaks to. */
  taxonomy: Taxonomy;
  /** Base URL of the langserver Service. No trailing slash. */
  endpoint: string;
  /** Optional fetcher (Service binding or test mock). Defaults to global fetch. */
  fetcher?: { fetch: typeof fetch };
  /** Default request timeout in ms (8s). */
  timeoutMs?: number;
}

export interface ClassifyInput {
  description: string;
  topK?: number;
  modelHint?: ModelHint;
  confidenceThreshold?: number;
}

export interface CandidateOut {
  code: string;
  confidence: number;
  title: string;
  reasoning?: string;
}

export interface ClassifyOutput {
  candidates: CandidateOut[];
  modelUsed: string;
  escalated: boolean;
  elapsedMs: number;
}

export interface IsicCandidateOut {
  classCode: string;
  confidence: number;
  title: string;
  reasoning?: string;
}

export interface IsicClassifyOutput {
  candidates: IsicCandidateOut[];
  modelUsed: string;
  escalated: boolean;
  elapsedMs: number;
}

export interface IsicHierarchicalInput {
  description: string;
  stopAt?: "section" | "division" | "group" | "class";
  modelHint?: ModelHint;
  confidenceThreshold?: number;
}

export interface IsicHierarchicalOutput {
  path: {
    section?: { code: string; title: string; confidence: number };
    division?: { code: string; title: string; confidence: number };
    group?: { code: string; title: string; confidence: number };
    class?: { code: string; title: string; confidence: number };
  };
  modelUsed: string;
  escalated: boolean;
  elapsedMs: number;
}

export interface InvokeAgentInput {
  code?: string;
  classCode?: string;
  payload: Record<string, unknown>;
  modelHint?: ModelHint;
  timeoutMs?: number;
}

export interface InvokeAgentOutput {
  ok: boolean;
  result?: Record<string, unknown>;
  modelUsed?: string;
  elapsedMs?: number;
  error?: string;
}

export interface ListAgentsInput {
  prefix?: string;
  divisionPrefix?: string;
  section?: string;
  limit?: number;
  cursor?: string;
}

export interface ListedAgent {
  code?: string;
  classCode?: string;
  title?: string;
  module?: string;
  loaded?: boolean;
  section?: string;
  division?: string;
  group?: string;
}

export interface ListAgentsOutput {
  agents: ListedAgent[];
  totalCount: number;
  cursor?: string;
}

export interface HealthOutput {
  status: "healthy" | "degraded" | "starting" | "unhealthy";
  registryReady: boolean;
  agentCount: number;
  warmAgents?: number;
  modelsAvailable?: string[];
  uptimeMs?: number;
  taxonomy?: string;
}

export class LangserverActorError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "LangserverActorError";
  }
}

const DEFAULT_TIMEOUT_MS = 8_000;

function nsidPath(taxonomy: Taxonomy, action: string): string {
  return `/xrpc/com.etzhayyim.apps.${taxonomy}.${action}`;
}

function urlWithQuery(base: string, params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    search.set(k, String(v));
  }
  const qs = search.toString();
  return qs ? `${base}?${qs}` : base;
}

async function timedFetch(
  fetcher: { fetch: typeof fetch },
  url: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const ac = new AbortController();
  const handle = setTimeout(() => ac.abort(), timeoutMs);
  try {
    return await fetcher.fetch(url, { ...init, signal: ac.signal });
  } finally {
    clearTimeout(handle);
  }
}

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: unknown = undefined;
    try {
      detail = await res.json();
    } catch {
      try {
        detail = await res.text();
      } catch {
        /* swallow */
      }
    }
    const msg =
      typeof detail === "object" && detail && "detail" in detail
        ? String((detail as { detail: unknown }).detail)
        : `HTTP ${res.status}`;
    throw new LangserverActorError(msg, res.status, detail);
  }
  return (await res.json()) as T;
}

/** Base actor — generic over taxonomy. Use {@link createUnispscActor}
 *  or {@link createIsicActor} unless you need the raw HTTP surface. */
export class LangserverActor {
  protected readonly fetcher: { fetch: typeof fetch };
  protected readonly timeoutMs: number;
  protected readonly endpoint: string;
  public readonly taxonomy: Taxonomy;

  constructor(config: LangserverActorConfig) {
    this.taxonomy = config.taxonomy;
    this.endpoint = config.endpoint.replace(/\/+$/, "");
    this.fetcher = config.fetcher ?? { fetch: globalThis.fetch.bind(globalThis) };
    this.timeoutMs = config.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  }

  async health(): Promise<HealthOutput> {
    const url = this.endpoint + nsidPath(this.taxonomy, "health");
    const res = await timedFetch(
      this.fetcher,
      url,
      { method: "GET" },
      this.timeoutMs,
    );
    return readJson<HealthOutput>(res);
  }

  async listAgents(input: ListAgentsInput = {}): Promise<ListAgentsOutput> {
    const url = urlWithQuery(
      this.endpoint + nsidPath(this.taxonomy, "listAgents"),
      input as Record<string, unknown>,
    );
    const res = await timedFetch(
      this.fetcher,
      url,
      { method: "GET" },
      this.timeoutMs,
    );
    return readJson<ListAgentsOutput>(res);
  }

  async invokeAgent(input: InvokeAgentInput): Promise<InvokeAgentOutput> {
    const url = this.endpoint + nsidPath(this.taxonomy, "invokeAgent");
    const res = await timedFetch(
      this.fetcher,
      url,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(input),
      },
      this.timeoutMs + 5_000,
    );
    return readJson<InvokeAgentOutput>(res);
  }

  protected async classifyRaw<T>(input: ClassifyInput): Promise<T> {
    const url = this.endpoint + nsidPath(this.taxonomy, "classify");
    const res = await timedFetch(
      this.fetcher,
      url,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(input),
      },
      this.timeoutMs,
    );
    return readJson<T>(res);
  }
}

// ── UNSPSC wrapper ──────────────────────────────────────────────────────────

export class UnispscActor extends LangserverActor {
  constructor(config: Omit<LangserverActorConfig, "taxonomy">) {
    super({ ...config, taxonomy: "unispsc" });
  }

  async classify(input: ClassifyInput): Promise<ClassifyOutput> {
    return this.classifyRaw<ClassifyOutput>(input);
  }
}

export function createUnispscActor(
  config: Omit<LangserverActorConfig, "taxonomy">,
): UnispscActor {
  return new UnispscActor(config);
}

// ── ISIC wrapper ────────────────────────────────────────────────────────────

export class IsicActor extends LangserverActor {
  constructor(config: Omit<LangserverActorConfig, "taxonomy">) {
    super({ ...config, taxonomy: "isic" });
  }

  async classify(input: ClassifyInput): Promise<IsicClassifyOutput> {
    return this.classifyRaw<IsicClassifyOutput>(input);
  }

  async hierarchicalClassify(
    input: IsicHierarchicalInput,
  ): Promise<IsicHierarchicalOutput> {
    const url = this.endpoint + nsidPath("isic", "hierarchicalClassify");
    const res = await timedFetch(
      this.fetcher,
      url,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(input),
      },
      this.timeoutMs,
    );
    return readJson<IsicHierarchicalOutput>(res);
  }
}

export function createIsicActor(
  config: Omit<LangserverActorConfig, "taxonomy">,
): IsicActor {
  return new IsicActor(config);
}

// ── Convenience constructor used by Kotodama host-sdk ──────────────────────
// Resolves taxonomy → in-cluster Service DNS by convention, allowing apps to
// call `actor.unispsc()` without knowing the endpoint URL. Environments that
// run outside the cluster pass an explicit `endpoint`.

const DEFAULT_ENDPOINTS: Record<Taxonomy, string> = {
  unispsc: "http://lg-open-unispsc.lg-open-unispsc.svc:80",
  isic: "http://lg-open-isic.lg-open-isic.svc:80",
};

export function createLangserverActor<T extends Taxonomy>(
  taxonomy: T,
  config: Partial<LangserverActorConfig> = {},
): T extends "unispsc" ? UnispscActor : IsicActor {
  const endpoint = config.endpoint ?? DEFAULT_ENDPOINTS[taxonomy];
  const ctorArgs = { endpoint, fetcher: config.fetcher, timeoutMs: config.timeoutMs };
  const actor =
    taxonomy === "unispsc" ? new UnispscActor(ctorArgs) : new IsicActor(ctorArgs);
  return actor as T extends "unispsc" ? UnispscActor : IsicActor;
}
