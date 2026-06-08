// index.ts — Main entry point for @etzhayyim/kotodama-host-sdk.
//
// TS Native + Lexicon Contract runtime.
// Routing: Hono default SmartRouter (RegExpRouter + TrieRouter).
//   1. Lexicon-derived host capability client + in-process dispatcher
//   2. App lifecycle (identity, capability, governance auto-registration)
//   3. XrpcClient (direct async PDS RPC + XRPC)
//   4. Legacy compatibility wrappers kept only for remaining container/WIT paths

import { Hono } from "hono";
import type { AppDef, HostImports, Request, Response, ComAtprotoSyncSubscribeReposCommit, WProtoCaller } from "./types.js";
import { App } from "./app.js";
import { XrpcClient } from "./xrpc-client.js";
import { createHostImports } from "./host-imports.js";
import { createHostDispatcher } from "./host-dispatcher.js";
import { createM365Capability } from "./capabilities/m365.js";
import { setHostDispatcher } from "./generated/host-client.js";
import { setConversationHost } from "./conversation.js";
import { setRemoteHost } from "./remote.js";
import { setLLMFetch, setLLMPdsGateway } from "./llm.js";
import { setReactPdsClient } from "./react.js";
import { createHostWebRouter, type McpFacadeConfig, type McpRegistryConfig } from "./host-web-router.js";
// ADR-2605111200: Worker-direct DB connection is prohibited.
// `setKyselyHyperdrive` is kept as a no-op for backwards compatibility with createHostSDK callers.
// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import { setKyselyHyperdrive } from "./kysely.js";

export interface HostSDKConfig {
  appDef: AppDef;
  env: Record<string, unknown>;
  pdsRpc?: { fetch(input: string | Request, init?: RequestInit): Promise<globalThis.Response> } | null;
  /** @deprecated Query reads are Kysely/Hyperdrive-backed; retained for older callers. */
  pdsQueryRpc?: unknown;
  internalToken?: string;
  hostOverrides?: Partial<HostImports>;
  /**
   * ADR-0042: opt-in MCP + OpenAPI tool facade. Per-actor `src/app.ts` imports
   * its generated manifest from `@etzhayyim/kotodama-host-sdk/generated/tool-manifest/<app>`
   * and passes it here. When omitted, `/mcp` and `/.well-known/openapi.json`
   * are not registered (no bundle cost, no behaviour change).
   */
  mcpFacade?: McpFacadeConfig;
  /**
   * ADR-2604261000: Kysely-backed MCP registry. Replaces the static `mcpFacade`
   * codegen path with a runtime SELECT from `vertex_mcp_tool_def` (60s cache).
   * When supplied, `/mcp` is registered and the manifest is loaded per-request.
   * `appName` and `actorDid` default to env-derived values.
   */
  mcpRegistry?: McpRegistryConfig;
}

export type { McpFacadeConfig, McpRegistryConfig } from "./host-web-router.js";

export interface HostSDK {
  app: App;
  env: Record<string, unknown>;
  hostImports: HostImports;
  pds: XrpcClient;
  /** Hono app instance — exposed for testing and composition. */
  router: Hono;

  handleRequest(request: Request): Promise<globalThis.Response>;

  witExports: {
    httpHandler: { handle(req: Request): Promise<globalThis.Response> };
    wHandler: { handleComAtprotoSyncSubscribeReposCommit(commit: ComAtprotoSyncSubscribeReposCommit): { tag: "ok" } | { tag: "err"; val: string } };
    serveHandler: {
      handle(method: string, params: Uint8Array, caller: WProtoCaller): { tag: "ok"; val: Uint8Array } | { tag: "err"; val: string };
    };
    shinkaHandler: {
      onHeartbeat(feedJson: string, engagementJson: string): { tag: "ok"; val: string } | { tag: "err"; val: string };
      onReaction(reactionJson: string): { tag: "ok" } | { tag: "err"; val: string };
      onNewFollower(followerNanoid: string): { tag: "ok" } | { tag: "err"; val: string };
      onFollowRequest(requesterNanoid: string, requesterDid: string, consentId: string): { tag: "ok"; val: string } | { tag: "err"; val: string };
    };
  };
}

async function resolveSecret(v: unknown): Promise<string> {
  if (!v) return "";
  if (typeof v === "string") return v;
  if (typeof (v as any)?.get === "function") return await (v as any).get();
  if (typeof (v as any)?.text === "function") return await (v as any).text();
  return String(v);
}

function asBodyInit(bytes: Uint8Array): ArrayBuffer {
  return Uint8Array.from(bytes).buffer;
}

function b64uDecode(s: string): Uint8Array {
  let t = s.replace(/-/g, "+").replace(/_/g, "/");
  while (t.length % 4) t += "=";
  return Uint8Array.from(atob(t), c => c.charCodeAt(0));
}

function base58btcEncode(bytes: Uint8Array): string {
  const alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
  let n = 0n;
  for (const b of bytes) n = (n << 8n) | BigInt(b);
  let out = "";
  while (n > 0n) {
    const rem = Number(n % 58n);
    out = alphabet[rem] + out;
    n /= 58n;
  }
  for (const b of bytes) {
    if (b === 0) out = "1" + out;
    else break;
  }
  return out || "1";
}

async function resolveSigningPublicMultikey(env: Record<string, unknown>): Promise<string> {
  const fromVar = (env["SIGNING_PUBLIC_KEY"] as string | undefined)?.toString?.() ?? "";
  if (fromVar) return fromVar;

  try {
    // Timeout secret resolution to 2 seconds (CF Secrets binding hangs on missing binding)
    const signingKey = await Promise.race([
      resolveSecret(env["SS_SIGNING_KEY"]),
      new Promise<string>((_, reject) => setTimeout(() => reject(new Error("secret resolution timeout")), 2000)),
    ]);
    if (!signingKey) return "";
    const b64Key = signingKey.replace(/-----[A-Z ]+-----/g, "").replace(/\s/g, "");
    const raw = b64Key.replace(/-/g, "+").replace(/_/g, "/");
    let padded = raw;
    while (padded.length % 4) padded += "=";
    const der = Uint8Array.from(atob(padded), c => c.charCodeAt(0));
    const priv = await crypto.subtle.importKey("pkcs8", der, { name: "ECDSA", namedCurve: "P-256" }, true, ["sign"]);
    const jwk = await crypto.subtle.exportKey("jwk", priv) as JsonWebKey;
    if (!jwk.x || !jwk.y) return "";
    const x = b64uDecode(jwk.x);
    const y = b64uDecode(jwk.y);
    if (x.length !== 32 || y.length !== 32) return "";
    const compressed = new Uint8Array(33);
    compressed[0] = (y[31] & 1) ? 0x03 : 0x02;
    compressed.set(x, 1);
    const multicodec = new Uint8Array(2 + compressed.length);
    multicodec[0] = 0x80; // varint(0x1200) first byte
    multicodec[1] = 0x24; // varint(0x1200) second byte
    multicodec.set(compressed, 2);
    return "z" + base58btcEncode(multicodec);
  } catch {
    return "";
  }
}

/** Create the host SDK singleton.
 *  selfRepo = canonical nanoid DID (AT Protocol compliant: repo = DID, never handle).
 *  Vanity domains (e.g. pachinko.etzhayyim.com) are handles, not DIDs — never used as repo. */
export function createHostSDK(config: HostSDKConfig): HostSDK {
  const nanoid = config.appDef.id || "";
  const selfRepo = (config.env["PERFORMER_DID"] as string)
    ?? (config.env["APP_DID"] as string)
    ?? (nanoid ? `did:web:${nanoid}.etzhayyim.com` : "");
  const appName = config.appDef.name || config.appDef.id || "";

  const pds = new XrpcClient({
    pdsRpc: config.pdsRpc as any ?? null,
    repo: selfRepo,
    appName,
    internalToken: config.internalToken,
    isServiceBinding: true,
  });
  pds.cdnR2 = (config.env["CDN_R2"] as R2Bucket | undefined) ?? null;

  const baseImports = createHostImports(config.env, pds, config.appDef.id);
  const hostImports: HostImports = config.hostOverrides
    ? { ...baseImports, ...config.hostOverrides }
    : baseImports;

  // Wire the Lexicon-typed host client to this SDK's host implementation.
  // App code can import typed com.etzhayyim.host.* helpers and they resolve in-process
  // through the dispatcher instead of going over HTTP.
  //
  // Optional host capabilities (e.g. m365) auto-construct from env vars when all
  // required bindings are present. Absent bindings → extras omitted → NSID invocation
  // throws a clear error only when actually called (lazy failure).
  //
  // Secret binding: SS_M365_CLIENT_SECRET (Cloudflare Secrets Store binding — object
  // with async .get()). Passed as a provider function so each token acquisition
  // awaits the current stored value. Tenant / client IDs are public identifiers
  // and live in kotodama.jsonld component.env as plain M365_TENANT_ID / M365_CLIENT_ID.
  const m365TenantId = (config.env["M365_TENANT_ID"] as string) ?? "";
  const m365ClientId = (config.env["M365_CLIENT_ID"] as string) ?? "";
  const m365SecretBinding = config.env["SS_M365_CLIENT_SECRET"] ?? config.env["M365_CLIENT_SECRET"];
  const extras: { m365?: ReturnType<typeof createM365Capability> } = {};
  if (m365TenantId && m365ClientId && m365SecretBinding) {
    extras.m365 = createM365Capability({
      tenantId: m365TenantId,
      clientId: m365ClientId,
      clientSecret: () => resolveSecret(m365SecretBinding),
    });
  }
  setHostDispatcher(createHostDispatcher(hostImports, extras));

  setKyselyHyperdrive((config.env["HYPERDRIVE"] as any) ?? null);
  setConversationHost(hostImports);
  setRemoteHost(hostImports);
  const pdsService = config.pdsRpc as { fetch(input: string | Request, init?: RequestInit): Promise<globalThis.Response> } | undefined;
  const sdkFetcher: any = pdsService?.fetch
    ? (input: string | Request, init?: RequestInit) => pdsService.fetch(input, init ?? {})
    : (input: string | Request, init?: RequestInit) => globalThis.fetch(input as any, init);
  setLLMFetch(sdkFetcher, config.internalToken ?? "");
  if (pdsService?.fetch) {
    setLLMPdsGateway((input: any, init: any) => pdsService.fetch(input, init ?? {}));
  }
  setReactPdsClient(pds);

  const app = new App(config.appDef, hostImports, pds);

  // Cache signing key to avoid per-request Secret binding access (hangs on missing binding)
  let cachedSigningKey: string | null = null;
  const getSigningPublicMultikey = async () => {
    if (cachedSigningKey !== null) return cachedSigningKey;
    const key = await resolveSigningPublicMultikey(config.env);
    cachedSigningKey = key;
    return key;
  };

  const wHandler = {
    handleComAtprotoSyncSubscribeReposCommit(commit: ComAtprotoSyncSubscribeReposCommit): { tag: "ok" } | { tag: "err"; val: string } {
      const errMsg = app.comAtprotoSyncSubscribeRepos(commit);
      if (errMsg) return { tag: "err", val: errMsg };
      return { tag: "ok" };
    },
  };

  const witExports = {
    wHandler,

    serveHandler: {
      handle(
        method: string, params: Uint8Array, caller: WProtoCaller,
      ): { tag: "ok"; val: Uint8Array } | { tag: "err"; val: string } {
        try {
          return { tag: "ok", val: app.dispatchRemoteCall(method, method, params, caller.did, caller.orgId) };
        } catch (err) {
          return { tag: "err", val: String(err) };
        }
      },
    },

    shinkaHandler: {
      onHeartbeat(_feedJson: string, _engagementJson: string): { tag: "ok"; val: string } | { tag: "err"; val: string } {
        return { tag: "ok", val: "[]" };
      },
      onReaction(_reactionJson: string): { tag: "ok" } | { tag: "err"; val: string } {
        return { tag: "ok" };
      },
      onNewFollower(_followerNanoid: string): { tag: "ok" } | { tag: "err"; val: string } {
        return { tag: "ok" };
      },
      onFollowRequest(_requesterNanoid: string, _requesterDid: string, _consentId: string): { tag: "ok"; val: string } | { tag: "err"; val: string } {
        return { tag: "ok", val: "pending" };
      },
    },
  };

  // ── Hono router (worker/web adapter) ──
  const router = createHostWebRouter({
    app,
    appDef: config.appDef,
    env: config.env,
    witExports: { wHandler },
    resolveSigningPublicMultikey: getSigningPublicMultikey,
    mcpFacade: config.mcpFacade,
    mcpRegistry: config.mcpRegistry,
  });

  const compatHttpHandler = {
    async handle(req: Request): Promise<globalThis.Response> {
      const method = req.method.toUpperCase();
      const request = req instanceof globalThis.Request
        ? req
        : new globalThis.Request(req.url, {
            method,
            headers: req.headers,
            ...(method === "GET" || method === "HEAD" ? {} : { body: asBodyInit(req.body) }),
          });
      return router.fetch(request);
    },
  };

  const exportedWitHandlers = {
    httpHandler: compatHttpHandler,
    ...witExports,
  };

  return {
    app,
    env: config.env,
    hostImports,
    pds,
    witExports: exportedWitHandlers,
    /** Hono app instance — exposed for testing and composition. */
    router,

    async handleRequest(request: Request) {
      // Hono requires a standard Request — wrap plain object if needed.
      const method = request.method.toUpperCase();
      const req = (request instanceof globalThis.Request)
        ? request
        : new globalThis.Request(request.url, {
            method,
            headers: request.headers,
            ...(method === "GET" || method === "HEAD" ? {} : { body: asBodyInit(request.body) }),
          });
      return router.fetch(req);
    },
  };
}

// Re-export everything
export type {
  AppDef, AppContext, RLSMeta, CommandHandler, ConversationHandler,
  RemoteCallHandler, ComAtprotoSyncSubscribeReposCommit, ConversationMessage,
  RACIAssignee, ApprovalRequirement, AssigneeRef, ActorCard, ActorAddress,
  ToolDescriptor, ActorCapability, CommandPolicy, GovernanceManifest,
  AgentToolDef, HostImports,
  CapabilityStatus, CapabilityDiscoveryEntry, ConversationSession,
  ProviderInfo, GraphOp, WhereClause, Request, Response,
  WProtoCaller, SmtpConnectionInfo,
} from "./types.js";

export { RACIRole, AssigneeKind, DecisionClass, PolicyVerdict, Role, ToolChoiceMode } from "./types.js";

export { App, makeRLSMeta, asAgentTool, withCapabilityTags, withWLexicon, withSignalEncrypt,
  withCapabilityPhase, responsible, accountable, consulted, informed,
  requireApproval, withBPMNTask, withOCELEvent } from "./app.js";
export type { CommandOption, CommandEntry, AutoCrudConfig, HeartbeatHook } from "./app.js";

// Kysely re-exports (ADR-2605111200: createKyselyDb throws inside Workers; types stay for server use).
export {
  assertPrivateGraphTable,
  createKyselyDb,
  getKyselyHyperdrive,
  getKyselyRpc,
  isPrivateGraphTable,
  setKyselyHyperdrive,
  setKyselyRpc,
  sql,
  WorkerDBProhibitedError,
  writePrivate,
} from "./kysely.js";
export type { KyselyDb, Hyperdrive, PrivateGraphTable, WritePrivateOptions, WritePrivateResult } from "./kysely.js";
export type { ExpressionBuilder, Expression, SqlBool } from "kysely";

/** @deprecated Drizzle archived 2026-04-13, use createKyselyDb instead. */
export type DrizzleDb = never;

export { startConversation, say, reply, getConversationHistory, endConversation } from "./conversation.js";

export { remoteCall, remoteCallJson, remoteCallAsync, remoteDiscover } from "./remote.js";

export { agentConverseAsync, llmAsk, llmCall, llmJson, setLLMFetch, setLLMPdsGateway, getPdsGatewayFetch } from "./llm.js";
export type { LLMMessage, LLMConverseOptions, LLMConverseResult, LLMToolCall } from "./llm.js";

export { agentReact, BUILTIN_TOOLS, REACT_DEFAULT_MODEL } from "./react.js";
export type { AgentTool, ToolResult, ReactOptions, ReactResult } from "./react.js";

export { MODEL_REGISTRY, USE_CASE_DEFAULTS, MURAKUMO_DEFAULT_MODEL, TRAINING_DEFAULT_BASE_MODEL, BAIEN_DEFAULT_TRUNK_MODEL, MODEL_ALIASES, resolveModelId, resolveModel, isKnownModel } from "./llm-model-registry.js";
export type { ModelDef, UseCaseName } from "./llm-model-types.js";

// ADR-0026 cohort utilities + LLM tool registry
export { parseSegmentHash, apqcL1DidFromSegment, deriveCohortEventType } from "./cohort.js";
export type { CohortSegment, CohortOcelEventType } from "./cohort.js";
export { cohortToolSpecs, cohortToolDispatch, cohortToolNsid, createCohortToolHandler } from "./llm-tools-cohort.js";
export type { OpenAIToolSpec, CohortToolDispatchEntry } from "./llm-tools-cohort.js";

export { XrpcClient, collectionToLabel, nsidToMethod } from "./xrpc-client.js";
export type { XrpcClientConfig } from "./xrpc-client.js";

export { archiveToOutbox, syncOutbox, generateWriteId } from "./write-outbox.js";
export type { OutboxEntry } from "./write-outbox.js";

export { toSnake, toKebab, humanizeIdentifier, normalizeTag, dedupeStrings, respondJson, stripHTML, truncateText, parseYataRows, decodeJson, encodeJson, str, nowISO, genID, rlsDefaults, num, firstRow } from "./helpers.js";

export { resolveHeartbeatCadence, createInboxBuffer, createCadenceState, determineMood } from "./heartbeat-cadence.js";

export { createConsentHelper } from "./consent-helpers.js";
export type { ConsentHelper, ConsentSubmitInput, ConsentRequestRecord, ConsentVerdict } from "./consent-helpers.js";

export { createAgentLifecycle } from "./agent-lifecycle.js";
export type { AgentLifecycle, AgentSpawnConfig, AgentRecord, AgentEvent, AgentStatus } from "./agent-lifecycle.js";

// Generic S3-compatible blob helpers (provider-agnostic; B2 = one endpoint).
export { s3Get, s3Put, s3Head, s3Delete } from "./s3.js";
export type { S3Env, S3GetResult, S3PutOptions, S3HeadResult } from "./s3.js";
// Backward-compat aliases — `b2*` re-exports the same s3 implementation.
export { b2Get, b2Put, b2Head, b2Delete } from "./b2.js";
export type { B2Env, B2GetResult, B2PutOptions, B2HeadResult } from "./b2.js";

export { createAuditHelper } from "./audit-query-builder.js";
export type { AuditHelper, AuditEmitInput, AuditEntry, AuditFilter, AuditCategory, AuditOutcome } from "./audit-query-builder.js";

export { createCreditsMeter } from "./credits-meter.js";
export type { CreditsMeterEnv } from "./credits-meter.js";

// ── Retail cloud billing v2 metering (ADR-2605080000 P2) ──
export { recordUsageEvent, createMeteringMiddleware } from "./metering.js";
export type {
  BillingMetric,
  BillingProduct,
  MeteringEnv,
  MeteringContext,
  RecordUsageEventParams,
} from "./metering.js";

export { ActorRegistry, flattenActorDefs } from "./actor-registry.js";
export type { ActorDef, ActorRegistryConfig, ActorRow, SeedResult, RegisterResult, IngestDelta, KyumeiResult, LLMFn, LLMJsonFn } from "./actor-registry.js";

// Per-taxonomy langserver actor wrappers (ADR-2605180900 Phase 6).
export {
  LangserverActor,
  UnispscActor,
  IsicActor,
  LangserverActorError,
  createUnispscActor,
  createIsicActor,
  createLangserverActor,
} from "./langserver-actor.js";
export type {
  Taxonomy,
  ModelHint,
  LangserverActorConfig,
  ClassifyInput,
  ClassifyOutput,
  CandidateOut,
  IsicClassifyOutput,
  IsicCandidateOut,
  IsicHierarchicalInput,
  IsicHierarchicalOutput,
  InvokeAgentInput,
  InvokeAgentOutput,
  ListAgentsInput,
  ListAgentsOutput,
  ListedAgent,
  HealthOutput,
} from "./langserver-actor.js";

// AppView XRPC handler (ADR-2605180900 Phase 7).
export { createLangserverXrpcHandler } from "./langserver-xrpc-handler.js";
export type { LangserverXrpcHandlerConfig } from "./langserver-xrpc-handler.js";

export { validateKamiScene, assertValidKamiScene } from "./kami-scene-validator.js";
export type { SceneValidationError } from "./kami-scene-validator.js";

export { buildVRMCharacterScene, vrmCdnUrl } from "./kami-character-vrm.js";
export type { VRMCharacterConfig, VRMMaterialOverride } from "./kami-character-vrm.js";

export { buildSplatCharacterScene, splatCdnUrl } from "./kami-character-splat.js";
export type { SplatCharacterConfig } from "./kami-character-splat.js";

export { buildHybridCharacterScene, defaultSofiaBody, defaultSofiaHair } from "./kami-character-hybrid.js";
export type { HybridCharacterConfig } from "./kami-character-hybrid.js";

export type { SdfBodyPartConfig } from "./kami-character-sdf.js";

export { buildSplatVTuberScene, ARKIT_TO_SPLAT_DEFAULTS } from "./kami-vtuber-splat.js";
export type { SplatRegion, SplatRegionTransform, SplatExpressionPreset, HeadPose, SplatTrackingConfig, SplatVTuberConfig } from "./kami-vtuber-splat.js";

export { buildVRMVTuberScene, ARKIT_BLEND_SHAPES, VRM_HUMANOID_BONES, VISEME_MAP, EMOTION_PRESETS } from "./kami-vtuber-vrm.js";
export type { VisemeMapping, EmotionPreset, VRMTrackingConfig, VRMVTuberMaterialOverride, VRMVTuberConfig, ARKitBlendShape } from "./kami-vtuber-vrm.js";

export { buildHybridVTuberScene } from "./kami-vtuber-hybrid.js";
export type { BoundaryBlendMode, HybridFaceConfig, HybridBodyConfig, HybridHairConfig, HybridTrackingConfig, HybridVTuberConfig } from "./kami-vtuber-hybrid.js";

export { buildAvatarPipelineDAG, buildSceneFromArtifacts, buildFaceAnalysisPrompt, buildMultiViewPrompt, submitAvatarGeneration, getAvatarStatus } from "./kami-avatar-pipeline.js";
export type { AvatarOutputMode, AvatarStyle, FaceAnalysis, MultiViewParams, ReconstructionParams, BodyGenParams, AvatarGenerationConfig, PipelineStage, AvatarJobStatus, AvatarArtifacts } from "./kami-avatar-pipeline.js";
export type { HeartbeatCadence, CadenceState, JouchoScores, InboxBuffer, InboundCommit, InboundReaction, FollowerReward, FollowerSnapshot, ContentSource, DataRepairTarget, Mood } from "./heartbeat-cadence.js";

export { DEFAULT_CHARACTER_DEF, buildCharacterExtractionPrompt, buildCharacterPreviewScene } from "./kami-character-maker.js";
export type { CharacterDef, FaceShapeParams, EyeParams as CharEyeParams, NoseParams, MouthParams as CharMouthParams, BrowParams, SkinParams, HairPreset, HairParams as CharHairParams, ClothingPreset, ClothingParams, BodyParams as CharBodyParams } from "./kami-character-maker.js";

// F-Plan 2026-04-13: Lexicon-typed host capability client (generated from com.etzhayyim.host.* lexicons).
// Apps can `import { secretsGet, invokeCall, configGet, ... } from "@etzhayyim/kotodama-host-sdk"`
// instead of using the legacy `sdk.hostImports.*` pattern. The dispatcher is auto-wired by
// createHostSDK() / createWorkerExport() — no manual setup needed.
export {
	HOST_NSID,
	llmConverse as hostLlmConverse,
	secretsGet as hostSecretsGet,
} from "./generated/host-client.js";
// Re-export the full generated client namespace for apps that want all capability functions.
export * as hostClient from "./generated/host-client.js";

// F-Plan F2 (2026-04-13): typed NSID helpers + per-NSID I/O type maps, generated from
// 00-contracts/lexicons/. Enforces that NSIDs exist at compile time and provides handler
// input/output shapes without manual schema duplication.
//
// Usage:
//   import { nsid, LEXICON_NSID, type LexiconInput, type LexiconOutput } from "@etzhayyim/kotodama-host-sdk";
//   sdk.app.command(nsid("com.etzhayyim.apps.foo.bar"), async (ctx, body) => {
//     const input = decodeJson<LexiconInput<"com.etzhayyim.apps.foo.bar">>(body, {} as any);
//     const output: LexiconOutput<"com.etzhayyim.apps.foo.bar"> = { ok: true };
//     return JSON.stringify(output);
//   });
export { LEXICON_NSID, nsid, LEXICON_INPUT_SCHEMA } from "./generated/lexicon-nsid-types.js";
export { parseLexiconInput, tryParseLexiconInput, LexiconValidationError, validateAgainstSchema } from "./lexicon-validator.js";
export {
  parseDid,
  tryParseDid,
  extractDidMethod,
  isDid,
  isDidErc725,
  isDidWeb,
  isDidPlc,
  isDidPkh,
  isDidetzhayyim,
  didetzhayyimDepth,
  didetzhayyimParent,
  didetzhayyimRoot,
  assertDidetzhayyimDepth,
  assertDidPrincipalOretzhayyimDepth,
  DidParseError,
} from "./did.js";
export type { DidMethod, ParsedDid } from "./did.js";
export type {
	KnownLexiconNSID,
	KnownLexiconQueryNSID,
	KnownLexiconProcedureNSID,
	KnownLexiconSubscriptionNSID,
	KnownLexiconRecordNSID,
	KnownLexiconPermissionSetNSID,
	StrictCommandNSID,
	StrictQueryNSID,
	LexiconNsid,
	LexiconInput,
	LexiconOutput,
	LexiconInputMap,
	LexiconOutputMap,
	LexiconRuntimeSchema,
	LexiconPrimitiveType,
} from "./generated/lexicon-nsid-types.js";

/** Default SDK factory — resolves AppDef from deploy-injected env vars (APP_NANOID, APP_DISPLAY_NAME, APP_DESCRIPTION).
 *  Single Source of Truth: kotodama.jsonld → etzhayyim deploy → env vars → SDK. No hardcoded appDef needed.
 *
 *  `options.mcpFacade` (ADR-0042) is threaded into HostSDKConfig when present.
 *  Apps that want per-actor MCP + OpenAPI exposure pass their generated manifest here
 *  (via createWorkerExport). Omit to disable the facade — no routes registered, no bundle cost.
 *
 *  `options.mcpRegistry` (ADR-2604261000) opts the actor into Kysely-backed MCP.
 *  When neither is supplied, env var `APP_MCP_REGISTRY=1` auto-enables registry mode
 *  (zero-config rollout — `etzhayyim deploy` injects this once an actor is migrated). */
export function createDefaultHostSDK(
  env: Record<string, unknown>,
  options?: { mcpFacade?: McpFacadeConfig; mcpRegistry?: McpRegistryConfig },
): HostSDK {
  const ev = (k: string): string => (env as any)[k] ?? "";
  const autoRegistry = !options?.mcpFacade && !options?.mcpRegistry && ev("APP_MCP_REGISTRY") === "1"
    ? {} as McpRegistryConfig
    : options?.mcpRegistry;
  return createHostSDK({
    appDef: {
      id: ev("APP_NANOID"),
      name: ev("APP_DISPLAY_NAME") || ev("APP_NANOID"),
      description: ev("APP_DESCRIPTION") || "",
    },
    env,
    pdsRpc: (env as any).PDS_SERVICE ?? null,
    pdsQueryRpc: (env as any).PDS_RPC ?? null,
    internalToken: "",
    mcpFacade: options?.mcpFacade,
    mcpRegistry: autoRegistry,
  });
}

/** Create a CF Worker default export from an SDK setup callback.
 *  Caches the SDK singleton per isolate. All routing delegates to handleRequest().
 *
 *  Usage patterns:
 *  - `export default createWorkerExport();` — auto-resolve from env (no hardcoded appDef)
 *  - `export default createWorkerExport((sdk) => { sdk.app.command(...); });` — setup callback (recommended)
 *  - `export default createWorkerExport(setup, { mcpFacade: { ... } });` — ADR-0042 MCP + OpenAPI facade (codegen)
 *  - `export default createWorkerExport(setup, { mcpRegistry: {} });`     — ADR-2604261000 Kysely-backed MCP
 *  For env-driven custom workers, use `createWorkerExportFromEnvFactory(...)`. */
export function createWorkerExport(
  setup?: (sdk: HostSDK) => void,
  options?: { mcpFacade?: McpFacadeConfig; mcpRegistry?: McpRegistryConfig },
): { fetch(request: Request, env: Record<string, unknown>, ctx?: { waitUntil(p: Promise<unknown>): void }): Promise<globalThis.Response> } {
  let _sdk: HostSDK | null = null;
  return {
    async fetch(request: Request, env: Record<string, unknown>, ctx?: { waitUntil(p: Promise<unknown>): void }): Promise<globalThis.Response> {
      if (!_sdk) {
        _sdk = createDefaultHostSDK(env, options);
        setup?.(_sdk);
        // Change 2: deferred serveAsync — don't block first request
        const servePromise = _sdk.app.serveAsync().catch(e =>
          console.warn(`[serve] registration deferred: ${e?.message ?? e}`));
        if (ctx?.waitUntil) {
          ctx.waitUntil(servePromise.catch(e =>
            console.warn(`[serve] registration waitUntil failed: ${e?.message ?? e}`)));
        } else {
          await servePromise;
        }
      }
      const resp = await _sdk.handleRequest(request as unknown as Request);
      // Drain fire-and-forget writes so they reach PDS.
      // ctx.waitUntil keeps them alive after response (non-blocking).
      // Without ctx, await before returning so CF Worker doesn't discard them.
      if (_sdk.pds?.pendingWrites?.length) {
        const drainPromise = _sdk.pds.drainPendingWrites();
        if (ctx?.waitUntil) {
          ctx.waitUntil(drainPromise.catch(e =>
            console.warn(`[pds] pending write drain failed: ${e?.message ?? e}`)));
        } else {
          await drainPromise;
        }
      }
      // ADR-2605111200: Worker-side outbox archive is prohibited. Failed writes are dropped
      // with a log; durable outbox replay is owned by server-side (LangGraph / LangServer).
      if (_sdk.pds?.failedWrites?.length) {
        const entries = _sdk.pds.failedWrites.splice(0);
        console.error(
          `[write-outbox] ADR-2605111200: Worker DB access prohibited; ${entries.length} failed writes dropped:`,
          entries.map((e) => e.writeId),
        );
      }
      return resp;
    },
  };
}

/** Explicit env-driven Worker factory.
 *  Use this for workers that need to build a custom SDK or wrap additional Hono routes
 *  before delegating back to host-sdk. Kept separate so `createWorkerExport()` can stay
 *  unambiguous and callback-only. */
export function createWorkerExportFromEnvFactory(
  factory: (env: Record<string, unknown>) => HostSDK,
): { fetch(request: Request, env: Record<string, unknown>, ctx?: { waitUntil(p: Promise<unknown>): void }): Promise<globalThis.Response> } {
  let _sdk: HostSDK | null = null;
  return {
    async fetch(request: Request, env: Record<string, unknown>, ctx?: { waitUntil(p: Promise<unknown>): void }): Promise<globalThis.Response> {
      if (!_sdk) {
        _sdk = factory(env);
        const servePromise = _sdk.app.serveAsync().catch(e =>
          console.warn(`[serve] registration deferred: ${e?.message ?? e}`));
        if (ctx?.waitUntil) {
          ctx.waitUntil(servePromise.catch(e =>
            console.warn(`[serve] registration waitUntil failed: ${e?.message ?? e}`)));
        } else {
          await servePromise;
        }
      }
      const resp = await _sdk.handleRequest(request as unknown as Request);
      if (_sdk.pds?.pendingWrites?.length) {
        const drainPromise = _sdk.pds.drainPendingWrites();
        if (ctx?.waitUntil) {
          ctx.waitUntil(drainPromise.catch(e =>
            console.warn(`[pds] pending write drain failed: ${e?.message ?? e}`)));
        } else {
          await drainPromise;
        }
      }
      // ADR-2605111200: same prohibition as createWorkerExport.
      if (_sdk.pds?.failedWrites?.length) {
        const entries = _sdk.pds.failedWrites.splice(0);
        console.error(
          `[write-outbox] ADR-2605111200: Worker DB access prohibited; ${entries.length} failed writes dropped:`,
          entries.map((e) => e.writeId),
        );
      }
      return resp;
    },
  };
}

// ── Capability Worker (MCP-only, no DID management) ──

/** Tool definition for createCapabilityWorker. */
export interface CapabilityToolDef {
  /** Tool description for MCP discovery. */
  description: string;
  /** JSON Schema for tool input parameters. */
  inputSchema?: Record<string, unknown>;
  /** Tags for discovery filtering. */
  tags?: string[];
  /** Tool handler — receives params and context, returns result. */
  handler: (params: Record<string, unknown>, ctx: CapabilityContext) => Promise<unknown>;
}

/** Context available to capability tool handlers. */
export interface CapabilityContext {
  /** Execute a graph SQL read via PDS_SERVICE. */
  query: (statement: string, params?: Record<string, unknown>) => Promise<Record<string, unknown>[]>;
  /** Write a record via PDS_SERVICE. */
  write: (collection: string, record: Record<string, unknown>) => Promise<{ rkey: string; uri: string }>;
  /** Upload a blob via PDS_SERVICE. */
  blob: (data: ArrayBuffer, contentType: string) => Promise<{ cid: string; url: string }>;
  /** LLM inference via PDS Gateway. */
  llm: (messages: Array<{ role: string; content: string }>, opts?: { model?: string }) => Promise<{ text: string }>;
  /** Raw env bindings (for advanced use). */
  env: Record<string, unknown>;
}

/**
 * Create a Capability Worker — pure MCP tool handler, no DID management.
 *
 * Unlike createWorkerExport(), this does NOT call serveAsync() and does NOT
 * register actor identity/capability/governance. The Worker only provides
 * stateless MCP tools. Actor DIDs are managed by PDS records and Hyperdrive-backed Kysely state.
 *
 * On first request, auto-registers tools in the Tool graph via
 * com.etzhayyim.tool.registerBatch XRPC.
 *
 * @example
 * ```typescript
 * // ADR-2605111200: DB I/O は server side (LangGraph / LangServer) で実行する。
 * export default createCapabilityWorker({
 *   tools: {
 *     "summarize": {
 *       description: "Summarize article by URL",
 *       inputSchema: { type: "object", properties: { url: { type: "string" } } },
 *       handler: async (params, ctx) => {
 *         const rows = await ctx.query(
 *           "SELECT url, text FROM vertex_article WHERE url = $1 LIMIT 1",
 *           { 1: String(params.url ?? "") },
 *         );
 *         return { summary: (rows[0] as any)?.text ?? "not found" };
 *       }
 *     }
 *   }
 * });
 * ```
 */
export function createCapabilityWorker(config: {
  tools: Record<string, CapabilityToolDef>;
}): { fetch(request: Request, env: Record<string, unknown>, ctx?: { waitUntil(p: Promise<unknown>): void }): Promise<globalThis.Response> } {
  let _registered = false;
  let _sdk: HostSDK | null = null;

  return {
    async fetch(request: Request, env: Record<string, unknown>, ctx?: { waitUntil(p: Promise<unknown>): void }): Promise<globalThis.Response> {
      // Initialize SDK (but skip serveAsync — no DID registration)
      if (!_sdk) {
        _sdk = createDefaultHostSDK(env);
      }

      // Auto-register tools in Tool graph (once)
      if (!_registered) {
        _registered = true;
        const nanoid = String(env.APP_NANOID || '');
        if (nanoid && _sdk.pds) {
          const toolDefs = Object.entries(config.tools).map(([name, def]) => ({
            name: `${nanoid}.${name}`,
            description: def.description,
            inputSchema: def.inputSchema ?? { type: "object" },
            tags: def.tags ?? [],
          }));
          const regPromise = _sdk.pds.xrpc("com.etzhayyim.tool.registerBatch", {
            capabilityWorker: nanoid,
            tools: toolDefs,
          }).catch((e: any) => console.warn(`[capability-worker] tool registration failed: ${e?.message ?? e}`));
          if (ctx?.waitUntil) {
            ctx.waitUntil(regPromise.catch((e: any) =>
              console.warn(`[capability-worker] tool registration waitUntil failed: ${e?.message ?? e}`)));
          } else {
            await regPromise;
          }
        }
      }

      const url = new URL(request.url);

      // Health check
      if (url.pathname === "/health" || url.pathname === "/_worker/health") {
        return new Response(JSON.stringify({ status: "ok", type: "capability-worker" }), {
          headers: { "Content-Type": "application/json" },
        });
      }

      // /_app/meta — expose tool metadata
      if (url.pathname === "/_app/meta") {
        const tools = Object.entries(config.tools).map(([name, def]) => ({
          name,
          description: def.description,
          inputSchema: def.inputSchema ?? { type: "object" },
          tags: def.tags ?? [],
        }));
        return new Response(JSON.stringify({ type: "capability-worker", tools }), {
          headers: { "Content-Type": "application/json" },
        });
      }

      // XRPC tool dispatch: /xrpc/com.etzhayyim.apps.{nanoid}.{method}
      if (url.pathname.startsWith("/xrpc/")) {
        const nsid = url.pathname.slice(6);
        // Extract method name from NSID (last segment)
        const parts = nsid.split(".");
        const method = parts[parts.length - 1];

        const toolDef = config.tools[method];
        if (!toolDef) {
          return new Response(JSON.stringify({ error: "unknown tool", method }), {
            status: 404,
            headers: { "Content-Type": "application/json" },
          });
        }

        let body: Record<string, unknown> = {};
        if (request.method === "POST") {
          try { body = await (request as any).json() as Record<string, unknown>; } catch { /* empty body */ }
        }

        // Build capability context
        const capCtx: CapabilityContext = {
          query: async (statement, params) => {
            if (!_sdk?.pds) return [];
            const result = await _sdk.pds.xrpc("com.etzhayyim.kagami.sql", { statement, params });
            return Array.isArray(result) ? result : ((result as any)?.rows ?? []);
          },
          write: async (collection, record) => {
            if (!_sdk?.pds) throw new Error("PDS not available");
            return _sdk.pds.createRecord(collection, record) as any;
          },
          blob: async (_data, _contentType) => {
            // Blob upload requires multipart — delegate to PDS XRPC
            throw new Error("blob upload not yet supported in capability worker");
          },
          llm: async (messages, opts) => {
            if (!_sdk?.pds) throw new Error("PDS not available");
            return _sdk.pds.xrpc("com.etzhayyim.llm.converse", { messages, ...opts }) as any;
          },
          env,
        };

        try {
          const result = await toolDef.handler(body, capCtx);
          return new Response(JSON.stringify(result ?? {}), {
            headers: { "Content-Type": "application/json" },
          });
        } catch (e: any) {
          console.error(`[capability-worker] tool ${method} failed:`, e);
          return new Response(JSON.stringify({ error: e?.message ?? String(e) }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          });
        }
      }

      // Fallback: delegate to host-sdk handleRequest for other routes
      return _sdk.handleRequest(request as unknown as Request);
    },
  };
}


/** Config for createKotodamaWorker — merged Worker entry factory.
 *  Used by deploy.go merged Worker path. Single-app entry typically uses createWorkerExport(). */
export interface KotodamaWorkerConfig {
  appId: string;
  projectName?: string;
  uiMode?: string;
  displayName?: string;
  accent?: string;
  icon?: string;
  performerType?: string;
  capabilities?: string[];
  ssrRoutesJSON?: string;
  version?: string;
  gameRuntime?: string;
  gameEntry?: string;
  sveltekitSSR?: unknown;
}

/** Create a Cloudflare Worker fetch handler backed by host-sdk.
 *  All routing (/_commit, /_heartbeat, /_app/meta, ?embed=1, /health, XRPC) is
 *  handled by sdk.handleRequest() (Hono trie router). Used by merged multi-nanoid Workers. */
export function createKotodamaWorker(config: KotodamaWorkerConfig): { default: { fetch: ExportedHandlerFetchHandler } } {
  let _sdk: HostSDK | null = null;

  async function getSDK(env: Record<string, unknown>): Promise<HostSDK> {
    if (_sdk) return _sdk;
    _sdk = createHostSDK({
      appDef: { id: config.appId, name: (env as any).APP_PROJECT_NAME || config.appId, description: "" },
      env,
      pdsRpc: (env as any).PDS_SERVICE ?? null,
      internalToken: "",
    });
    return _sdk;
  }

  const fetchHandler: ExportedHandlerFetchHandler = async (request, env, _ctx) => {
    const sdk = await getSDK(env as Record<string, unknown>);
    return sdk.handleRequest(request as unknown as Request);
  };

  return { default: { fetch: fetchHandler } };
}
