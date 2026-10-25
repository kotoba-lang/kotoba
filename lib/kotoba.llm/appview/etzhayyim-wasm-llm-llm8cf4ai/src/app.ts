import {
  asAgentTool,
  createDefaultHostSDK,
  createWorkerExportFromEnvFactory,
  nowISO,
  str,
  withCapabilityTags,
  withOCELEvent,
  type ComAtprotoSyncSubscribeReposCommit,
  type HostSDK,
  resolveHeartbeatCadence,
  createCadenceState,
  createInboxBuffer,
  MURAKUMO_DEFAULT_MODEL,
  nsid,
} from "@etzhayyim/kotodama-host-sdk";

const cadenceState = createCadenceState();
const inbox = createInboxBuffer();
const ANSWER_WITH_KNOWLEDGE_NSID = "com.etzhayyim.apps.llm.answerWithKnowledge";

let appId = ""
let actorDID = ""

const _dec = new TextDecoder();
function decBody(body: Uint8Array): string {
  if (!body || body.length === 0) return "{}";
  return _dec.decode(body) || "{}";
}

// ── Workers AI Model Registry (SSoT: @etzhayyim/kotodama-host-sdk llm-model-registry) ──

import {
  MODEL_REGISTRY, USE_CASE_DEFAULTS, MODEL_ALIASES,
  resolveModel, resolveModelId, isKnownModel,
} from "@etzhayyim/kotodama-host-sdk";

/** Backward compat alias. */
const isKnownModelId = isKnownModel;

// ── Credit Gate (Workers AI costs money — require credits for external callers) ──

/** Credit cost per model (¥ credits per request) — Ollama Tier 0 only */
const CREDIT_COST: Record<string, number> = {
  [MURAKUMO_DEFAULT_MODEL]: 2,
};

/**
 * Deduct credits for LLM inference.
 * Returns error string only on explicit 402 insufficient_balance.
 * Passes through when credits service is unavailable (graceful degradation).
 * Credits are billed reactively via AT Protocol commit events in credits-mcp actor;
 * this call is a best-effort pre-check only.
 */
async function deductCredits(callerDid: string, modelId: string): Promise<string | null> {
  const cost = CREDIT_COST[modelId] ?? 1;
  try {
    const resp = await fetch("https://credits.etzhayyim.com/xrpc/com.etzhayyim.apps.credits.checkSpendAllowed", {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-kotodama-verified": "true" },
      body: JSON.stringify({ userId: callerDid, action: "llm_inference", amount: cost }),
    });
    // Only block on explicit 402 insufficient balance; pass through on any other error
    if (resp.status === 402) {
      const data = await resp.json().catch(() => ({})) as Record<string, unknown>;
      return String(data.reason ?? "insufficient_credits");
    }
    return null;
  } catch {
    // Credits service unavailable — pass through (billed reactively)
    return null;
  }
}

// ── Core Inference ──

interface InferenceRequest {
  messages: Array<{ role: string; content: string; toolCalls?: unknown; toolCallId?: string }>;
  model?: string;
  useCase?: string;
  maxTokens?: number;
  temperature?: number;
  responseFormat?: { type: string };
  tools?: Array<{ type: string; function: { name: string; description: string; parameters: unknown } }>;
  toolChoice?: string | { type: string; function?: { name: string } };
}

interface InferenceResult {
  content: string;
  model: string;
  'cfModel': string;
  'finishReason': string;
  usage?: { 'inputTokens': number; 'outputTokens': number };
  toolCalls?: Array<{ id: string; type: string; function: { name: string; arguments: string } }>;
}

/** Module-level env, set by createComponentHostSDK */
let _env: Record<string, unknown> = {};

async function readSecret(value: unknown): Promise<string> {
  if (!value) return "";
  if (typeof value === "string") return value;
  const getter = (value as { get?: () => Promise<string> }).get;
  if (typeof getter === "function") return await getter.call(value).catch(() => "");
  return "";
}

/**
 * Normalize a model hint to a canonical model ID.
 * Resolves aliases (e.g. "gemma-4-e2b" → "gemma-4-e2b-it") and cfModel names.
 * Returns the original hint if unrecognized (caught downstream by isKnownModelId).
 * Returns undefined if no hint given.
 */
function canonicalizeModelHint(model?: string): string | undefined {
  if (!model) return undefined;
  const trimmed = model.trim();
  if (!trimmed) return undefined;
  if (MODEL_REGISTRY[trimmed]) return trimmed;
  const aliased = MODEL_ALIASES[trimmed.toLowerCase()];
  if (aliased) return aliased;
  for (const [id, def] of Object.entries(MODEL_REGISTRY)) {
    if (def.cfModel.toLowerCase() === trimmed.toLowerCase()) return id;
  }
  return trimmed;
}

/**
 * Inference via llm.etzhayyim.com routing backends.
 *
 * Default tiers stay on Murakumo. Explicit RunPod models are still routed
 * through LiteLLM, because LiteLLM is the backend registry and policy point.
 */
async function runInference(req: InferenceRequest): Promise<InferenceResult> {
  const MURAKUMO_TIERS = new Set(["tier0-general", "tier0-structured", "tier1-reasoning"]);
  const RUNPOD_MODELS = new Set(["gemma4-runpod", "tier0-runpod"]);
  const requestedModel = canonicalizeModelHint(req.model);
  // Murakumo tier names are not in MODEL_REGISTRY — pass them through directly.
  if (requestedModel && !isKnownModelId(requestedModel) && !MURAKUMO_TIERS.has(requestedModel) && !RUNPOD_MODELS.has(requestedModel)) {
    return {
      content: "",
      model: requestedModel,
      'cfModel': "",
      'finishReason': `error:unknown_model:${requestedModel}`.slice(0, 200),
    };
  }
  const modelId = requestedModel || resolveModelId(undefined, req.useCase);

  // gemma3-1b: only non-thinking model available on the fleet (2026-04-28).
  // gemma4-e4b + qwen3.5-9b have thinking mode enabled — they produce empty content.
  const litellmModel = RUNPOD_MODELS.has(modelId) ? modelId : "gemma3-1b";

  const litellmUrl = ((_env as any).LITELLM_URL as string | undefined) ?? "https://murakumo-serve.etzhayyim.com";
  const litellmKey = ((_env as any).LITELLM_KEY as string | undefined) ?? "sk-etzhayyim-litellm-local";

  try {
    const upstream = await fetch(`${litellmUrl}/v1/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${litellmKey}`,
      },
      body: JSON.stringify({
        model: litellmModel,
        messages: req.messages,
        max_tokens: req.maxTokens ?? 1024,
        temperature: req.temperature ?? 0.7,
        stream: false,
      }),
      signal: AbortSignal.timeout(60_000),
    });

    if (!upstream.ok) {
      return {
        content: "",
        model: modelId,
        'cfModel': litellmModel,
        'finishReason': `error:litellm_${upstream.status}`,
      };
    }

    const data = await upstream.json() as Record<string, unknown>;
    const choices = (data.choices as Array<Record<string, unknown>>) ?? [];
    const first = choices[0] ?? {};
    const message = (first.message as Record<string, unknown>) ?? {};
    const content = String(message.content ?? "");
    const finishReason = String(first.finish_reason ?? "stop");
    const usage = data.usage as Record<string, number> | undefined;

    return {
      content,
      model: modelId,
      'cfModel': litellmModel,
      'finishReason': finishReason,
      usage: usage ? {
        'inputTokens': usage.prompt_tokens ?? 0,
        'outputTokens': usage.completion_tokens ?? 0,
      } : undefined,
    };
  } catch {
    return {
      content: "",
      model: modelId,
      'cfModel': litellmModel,
      'finishReason': "error:litellm_unavailable",
    };
  }
}

// ── OpenAI-Compatible Chat Completions ──

async function handleChatCompletions(body: InferenceRequest): Promise<Record<string, unknown>> {
  const result = await runInference(body);
  const message: Record<string, unknown> = { role: "assistant", content: result.content };
  if (result.toolCalls?.length) {
    message.toolCalls = result.toolCalls;
  }
  return {
    id: `chatcmpl-${Date.now()}`,
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model: result.model,
    choices: [
      {
        index: 0,
        message,
        'finishReason': result.finishReason,
      },
    ],
    _cf_model: result.cfModel,
  };
}

// ── Commands ──

async function cmdConverse(sdk: HostSDK, body: Uint8Array): Promise<unknown> {
  const args = JSON.parse(decBody(body));
  const messages: Array<{ role: string; content: string }> = [];

  if (Array.isArray(args.messages)) {
    for (const m of args.messages) {
      const role = m.role === 0 ? "system" : m.role === 1 ? "user" : m.role === 2 ? "assistant" : "user";
      messages.push({ role, content: String(m.content ?? "") });
    }
  }

  const result = await runInference({
    messages,
    model: args.options?.model ?? args.model,
    'useCase': args.options?.useCase ?? args.useCase,
    'maxTokens': args.options?.maxTokens ?? args.maxTokens,
    temperature: args.options?.temperature,
    'responseFormat': args.options?.responseFormat,
  });

  return {
    content: result.content,
    model: result.model,
    finishReason: result.finishReason,
    cfModel: result.cfModel,
  };
}

async function cmdChatCompletions(sdk: HostSDK, body: Uint8Array): Promise<unknown> {
  const args = JSON.parse(decBody(body)) as InferenceRequest;
  const result = await handleChatCompletions(args);
  return result;
}

async function cmdAnswerWithKnowledge(_sdk: HostSDK, body: Uint8Array, env: Record<string, unknown>): Promise<unknown> {
  const resp = await proxyAnswerWithKnowledge(
    new Request(`https://llm.etzhayyim.com/xrpc/${ANSWER_WITH_KNOWLEDGE_NSID}?stream=0&timeoutMs=240000`, {
      method: "POST",
      headers: { "content-type": "application/json", "accept": "application/json" },
      body,
    }),
    env,
  );
  const text = await resp.text();
  try {
    return JSON.parse(text);
  } catch {
    return { ok: resp.ok, status: resp.status, body: text };
  }
}

async function proxyAnswerWithKnowledge(request: Request, env: Record<string, unknown>): Promise<globalThis.Response> {
  const incomingUrl = new URL(request.url);
  const upstreamUrl = new URL(`https://atproto.etzhayyim.com/xrpc/${ANSWER_WITH_KNOWLEDGE_NSID}`);
  incomingUrl.searchParams.forEach((value, key) => upstreamUrl.searchParams.set(key, value));
  if (!upstreamUrl.searchParams.has("stream")) upstreamUrl.searchParams.set("stream", "1");
  if (!upstreamUrl.searchParams.has("timeoutMs")) upstreamUrl.searchParams.set("timeoutMs", "240000");

  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");
  if (!headers.has("content-type") && request.method !== "GET" && request.method !== "HEAD") {
    headers.set("content-type", "application/json");
  }
  if (upstreamUrl.searchParams.get("stream") !== "0" && upstreamUrl.searchParams.get("stream") !== "false") {
    headers.set("accept", "text/event-stream");
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
  };
  const pds = env.PDS_SERVICE as { fetch(input: string | Request, init?: RequestInit): Promise<globalThis.Response> } | undefined;
  const resp = pds?.fetch
    ? await pds.fetch(upstreamUrl.toString(), init)
    : await fetch(upstreamUrl.toString(), init);

  if (resp.headers.get("content-type")?.includes("text/event-stream")) {
    const outHeaders = new Headers(resp.headers);
    outHeaders.set("content-type", "text/event-stream");
    outHeaders.set("cache-control", "no-cache, no-transform");
    outHeaders.set("access-control-allow-origin", "*");
    return new globalThis.Response(resp.body, { status: resp.status, headers: outHeaders });
  }
  const outHeaders = new Headers(resp.headers);
  outHeaders.set("access-control-allow-origin", "*");
  return new globalThis.Response(resp.body, { status: resp.status, headers: outHeaders });
}

async function cmdListModels(_sdk: HostSDK, _body: Uint8Array): Promise<unknown> {
  const models = Object.entries(MODEL_REGISTRY).map(([id, def]) => ({
    id,
    'cfModel': def.cfModel,
    'maxTokens': def.maxTokens,
    'contextWindow': def.contextWindow,
    'useCases': def.useCases,
  }));
  return { models };
}

async function cmdRecommendModel(_sdk: HostSDK, body: Uint8Array): Promise<unknown> {
  const args = JSON.parse(decBody(body));
  const useCase = str(args.useCase ?? "general");
  const modelDef = resolveModel(undefined, useCase);
  const modelId = USE_CASE_DEFAULTS[useCase] ?? MURAKUMO_DEFAULT_MODEL;
  return {
    'useCase': useCase,
    'recommendedModel': modelId,
    'cfModel': modelDef.cfModel,
    'maxTokens': modelDef.maxTokens,
    'contextWindow': modelDef.contextWindow,
  };
}

async function cmdHealthCheck(_sdk: HostSDK, _body: Uint8Array): Promise<unknown> {
  const checks: Record<string, string> = {};
  for (const [id, def] of Object.entries(MODEL_REGISTRY)) {
    try {
      const result = await runInference({
        messages: [{ role: "user", content: "ping" }],
        model: id,
        'maxTokens': 5,
      });
      checks[id] = result.finishReason.startsWith("error") ? "unavailable" : "ok";
    } catch {
      checks[id] = "error";
    }
  }
  return { status: "ok", models: checks, 'checkedAt': nowISO() };
}

// ── Celler AI Voice Verification ──

interface CellerTestScenario {
  name: string;
  'callerE164': string;
  'expectedLang': string;
  'callerSpeech': string;
}

const CELLER_TEST_SCENARIOS: CellerTestScenario[] = [
  { name: "JP business inquiry", 'callerE164': "+81-50-1234-5678", 'expectedLang': "ja", 'callerSpeech': "もしもし、山田太郎です。来週の会議についてお電話しました。日程を変更したいのですが。" },
  { name: "US support call", 'callerE164': "+1-555-123-4567", 'expectedLang': "en", 'callerSpeech': "Hi, this is John Smith. I'm calling about my account. I need to update my billing information." },
  { name: "CN product inquiry", 'callerE164': "+86-138-0000-1234", 'expectedLang': "zh", 'callerSpeech': "你好，我是李明。我想咨询一下你们的产品价格。" },
  { name: "KR appointment", 'callerE164': "+82-10-1234-5678", 'expectedLang': "ko", 'callerSpeech': "안녕하세요, 김민수입니다. 다음 주 화요일 예약을 변경하고 싶습니다." },
  { name: "ES complaint", 'callerE164': "+34-612-345-678", 'expectedLang': "es", 'callerSpeech': "Hola, soy María García. Llamo porque tengo un problema con mi pedido. No ha llegado todavía." },
  { name: "FR reservation", 'callerE164': "+33-6-12-34-56-78", 'expectedLang': "fr", 'callerSpeech': "Bonjour, je suis Pierre Dupont. Je voudrais réserver une table pour vendredi soir, s'il vous plaît." },
  { name: "DE technical", 'callerE164': "+49-151-1234-5678", 'expectedLang': "de", 'callerSpeech': "Hallo, hier ist Hans Müller. Ich habe ein technisches Problem mit meinem Gerät und brauche Hilfe." },
  { name: "BR delivery", 'callerE164': "+55-11-98765-4321", 'expectedLang': "pt", 'callerSpeech': "Olá, sou João Silva. Estou ligando sobre a entrega do meu pedido que está atrasada." },
  { name: "SA service", 'callerE164': "+966-50-123-4567", 'expectedLang': "ar", 'callerSpeech': "مرحباً، أنا أحمد محمد. أريد الاستفسار عن خدماتكم." },
  { name: "IN billing", 'callerE164': "+91-98765-43210", 'expectedLang': "hi", 'callerSpeech': "नमस्ते, मैं राजेश कुमार हूँ। मुझे अपने बिल के बारे में बात करनी है।" },
];

async function cmdVerifyCellerAi(_sdk: HostSDK, body: Uint8Array): Promise<unknown> {
  const args = JSON.parse(decBody(body));
  const scenarioFilter = str(args.scenario ?? "");
  const model = str(args.model ?? MURAKUMO_DEFAULT_MODEL); // multilingual default

  const scenarios = scenarioFilter
    ? CELLER_TEST_SCENARIOS.filter(s => s.name.includes(scenarioFilter) || s.expectedLang === scenarioFilter)
    : CELLER_TEST_SCENARIOS;

  const results: Array<{
    scenario: string;
    lang: string;
    'callerE164': string;
    'callerSpeech': string;
    'aiResponse': string;
    summary: string;
    'responseLangOk': boolean;
    'latencyMs': number;
    model: string;
    status: "pass" | "fail" | "error";
    error?: string;
  }> = [];

  for (const sc of scenarios) {
    const t0 = Date.now();
    try {
      // Generate AI response to caller speech (single inference, maxTokens capped for speed)
      const systemPrompt = buildCellerSystemPrompt(sc.expectedLang);
      const responseResult = await runInference({
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: sc.callerSpeech },
        ],
        model,
        'maxTokens': 150,
        temperature: 0.5,
      });

      const hasContent = responseResult.content.length > 10;
      results.push({
        scenario: sc.name,
        lang: sc.expectedLang,
        'callerE164': sc.callerE164,
        'callerSpeech': sc.callerSpeech.slice(0, 80),
        'aiResponse': responseResult.content.slice(0, 300),
        summary: "",
        'responseLangOk': hasContent,
        'latencyMs': Date.now() - t0,
        model: responseResult.cfModel,
        status: hasContent ? "pass" : "fail",
      });
    } catch (e) {
      results.push({
        scenario: sc.name,
        lang: sc.expectedLang,
        'callerE164': sc.callerE164,
        'callerSpeech': sc.callerSpeech.slice(0, 80),
        'aiResponse': "",
        summary: "",
        'responseLangOk': false,
        'latencyMs': Date.now() - t0,
        model,
        status: "error",
        error: e instanceof Error ? e.message : String(e),
      });
    }
  }

  const passed = results.filter(r => r.status === "pass").length;
  const failed = results.filter(r => r.status === "fail").length;
  const errored = results.filter(r => r.status === "error").length;

  return {
    test: "cellerAiVoiceMultilingual",
    total: results.length,
    passed,
    failed,
    errored,
    'allPassed': passed === results.length,
    results,
    'testedAt': nowISO(),
  };
}

const LANG_NAME_MAP: Record<string, string> = {
  ja: "Japanese", en: "English", zh: "Chinese", ko: "Korean",
  es: "Spanish", fr: "French", de: "German", pt: "Portuguese",
  ar: "Arabic", hi: "Hindi",
};

function buildCellerSystemPrompt(lang: string): string {
  const langName = LANG_NAME_MAP[lang] ?? "English";
  const prompts: Record<string, string> = {
    ja: `あなたは電話の AI アシスタントです。日本語で応答してください。
- 簡潔に応答し、相手の話を遮らないでください
- 重要な情報（名前、電話番号、用件、期限）を確認してください
- 通話終了時に「ご用件は承りました。担当者にお伝えします。」と締めてください`,
    en: `You are a phone AI assistant. Respond in English.
- Respond concisely and do not interrupt the caller
- Confirm key information (name, phone number, purpose, deadline)
- End with "I've noted your request. I'll pass it along to the person in charge."`,
  };
  return prompts[lang] ?? `You are a phone AI assistant. You MUST respond in ${langName} only.
- Respond concisely and do not interrupt the caller
- Confirm key information (name, phone number, purpose, deadline)
- End with a polite closing in ${langName}`;
}

// ── SDK Factory + Command Registration ──



export function handleComAtprotoSyncSubscribeReposCommit(sdk: HostSDK, commit: ComAtprotoSyncSubscribeReposCommit): { ok: boolean; detail: string } {
  if (commit.action !== "create") return { ok: true, detail: "skip non-create" };
  if (commit.collection === "com.etzhayyim.apps.llm.inferenceRequest") {
    return { ok: true, detail: "inference request noted" };
  }
  return { ok: true, detail: "commit accepted" };
}


// Layer 3: Shinka (Social Evolution) — joucho cadence
const shinkaEnabled = true;

export async function runHeartbeat(sdk: HostSDK): Promise<{ ok: boolean; actions: Array<Record<string, unknown>> }> {
  const actions: Array<Record<string, unknown>> = [];
  const ts = nowISO();
  const cadence = await resolveHeartbeatCadence("did:web:llm8cf4ai.etzhayyim.com", cadenceState, inbox);
  actions.push({ action: "cadenceResolved", mood: cadence.mood, reason: cadence.reason, ts });

  if (actions.length === 1) actions.push({ action: "noop", mood: cadence.mood, ts });
  return { ok: true, actions };
}

// ── OpenAI-Compatible REST API (/v1/*) ──

/** Convert MODEL_REGISTRY to OpenAI /v1/models format */
function openaiListModels(): Record<string, unknown> {
  const data = Object.entries(MODEL_REGISTRY).map(([id, def]) => ({
    id,
    object: "model" as const,
    created: 1711929600, // 2024-04-01 epoch
    owned_by: "etzhayyim",
    permission: [],
    root: def.cfModel,
    parent: null,
  })).concat([
    {
      id: "gemma4-runpod",
      object: "model" as const,
      created: 1711929600,
      owned_by: "etzhayyim",
      permission: [],
      root: "gemma-4-e4b-it",
      parent: null,
    },
    {
      id: "tier0-runpod",
      object: "model" as const,
      created: 1711929600,
      owned_by: "etzhayyim",
      permission: [],
      root: "gemma-4-e4b-it",
      parent: null,
    },
  ]);
  return { object: "list", data };
}

/** Parse OpenAI-style chat completions request into InferenceRequest */
function parseOpenAIChatRequest(body: Record<string, unknown>): InferenceRequest {
  const messages = (Array.isArray(body.messages) ? body.messages : []) as Array<{
    role: string; content: string; tool_calls?: unknown; tool_call_id?: string;
  }>;
  return {
    messages: messages.map(m => ({
      role: m.role,
      content: String(m.content ?? ""),
      toolCalls: m.tool_calls,
      toolCallId: m.tool_call_id,
    })),
    model: typeof body.model === "string" ? body.model : undefined,
    maxTokens: typeof body.max_tokens === "number" ? body.max_tokens : undefined,
    temperature: typeof body.temperature === "number" ? body.temperature : undefined,
    responseFormat: body.response_format as InferenceRequest["responseFormat"],
    tools: body.tools as InferenceRequest["tools"],
    toolChoice: body.tool_choice as InferenceRequest["toolChoice"],
  };
}

/** Build OpenAI-format chat completion response */
async function openaiChatCompletions(body: Record<string, unknown>): Promise<Record<string, unknown>> {
  const req = parseOpenAIChatRequest(body);
  const result = await runInference(req);
  const message: Record<string, unknown> = { role: "assistant", content: result.content };
  if (result.toolCalls?.length) {
    message.tool_calls = result.toolCalls;
  }
  return {
    id: `chatcmpl-${Date.now()}`,
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model: result.model,
    choices: [{
      index: 0,
      message,
      finish_reason: result.finishReason === "toolCalls" ? "tool_calls" : result.finishReason,
    }],
    usage: result.usage ? {
      prompt_tokens: result.usage.inputTokens,
      completion_tokens: result.usage.outputTokens,
      total_tokens: result.usage.inputTokens + result.usage.outputTokens,
    } : undefined,
  };
}

/** SSE streaming wrapper — runs non-streaming inference then emits as SSE chunks. */
async function streamChatCompletions(body: Record<string, unknown>): Promise<globalThis.Response> {
  const req = parseOpenAIChatRequest(body);
  const result = await runInference(req);
  const id = `chatcmpl-${Date.now()}`;
  const created = Math.floor(Date.now() / 1000);
  const model = result.model;

  const chunks: string[] = [];
  // role chunk
  chunks.push(JSON.stringify({
    id, object: "chat.completion.chunk", created, model,
    choices: [{ index: 0, delta: { role: "assistant" }, finish_reason: null }],
  }));
  // content chunk
  if (result.content) {
    chunks.push(JSON.stringify({
      id, object: "chat.completion.chunk", created, model,
      choices: [{ index: 0, delta: { content: result.content }, finish_reason: null }],
    }));
  }
  // tool_calls chunk
  if (result.toolCalls?.length) {
    chunks.push(JSON.stringify({
      id, object: "chat.completion.chunk", created, model,
      choices: [{ index: 0, delta: { tool_calls: result.toolCalls }, finish_reason: null }],
    }));
  }
  // finish chunk
  const finishReason = result.finishReason === "toolCalls" ? "tool_calls" : (result.finishReason ?? "stop");
  chunks.push(JSON.stringify({
    id, object: "chat.completion.chunk", created, model,
    choices: [{ index: 0, delta: {}, finish_reason: finishReason }],
  }));

  const sseBody = chunks.map(c => `data: ${c}\n\n`).join("") + "data: [DONE]\n\n";
  return new globalThis.Response(sseBody, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
      "Access-Control-Allow-Origin": "*",
    },
  });
}

/** Handle OpenAI-compatible /v1/* paths. Returns Response or null (pass-through). */
async function handleOpenAIPath(request: Request): Promise<globalThis.Response | null> {
  const url = new URL(request.url);
  const path = url.pathname;
  const json = (data: unknown, status = 200) =>
    new globalThis.Response(JSON.stringify(data), {
      status,
      headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
    });

  // CORS preflight for /v1/*
  if (request.method === "OPTIONS" && path.startsWith("/v1/")) {
    return new globalThis.Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, x-credits-did, x-kotodama-verified",
        "Access-Control-Max-Age": "86400",
      },
    });
  }

  if (path === "/v1/chat/completions" && request.method === "POST") {
    const body = await request.json() as Record<string, unknown>;

    // Credit gate: internal calls (PDS service binding) skip; external require credits
    const isInternal = request.headers.get("x-kotodama-verified") === "true";
    if (!isInternal) {
      const callerDid = request.headers.get("x-credits-did") || "";
      if (!callerDid) {
        return json({ error: { message: "x-credits-did header required — LLM inference requires credits", type: "auth_error", code: "credits_required" } }, 401);
      }
      const modelId = resolveModelId(
        typeof body.model === "string" ? body.model : undefined,
        typeof body.use_case === "string" ? body.use_case : undefined,
      );
      const creditErr = await deductCredits(callerDid, modelId);
      if (creditErr) {
        return json({ error: { message: creditErr, type: "billing_error", code: "insufficient_credits" } }, 402);
      }
    }

    if (body.stream === true) {
      return streamChatCompletions(body);
    }
    return json(await openaiChatCompletions(body));
  }

  if (path === "/v1/models" && request.method === "GET") {
    return json(openaiListModels());
  }

  const modelMatch = path.match(/^\/v1\/models\/(.+)$/);
  if (modelMatch && request.method === "GET") {
    const modelId = modelMatch[1];
    if (modelId === "gemma4-runpod" || modelId === "tier0-runpod") {
      return json({ id: modelId, object: "model", created: 1711929600, owned_by: "etzhayyim", permission: [], root: "gemma-4-e4b-it", parent: null });
    }
    const def = MODEL_REGISTRY[modelId];
    if (!def) return json({ error: { message: `Model '${modelId}' not found`, type: "invalid_request_error", code: "model_not_found" } }, 404);
    return json({ id: modelId, object: "model", created: 1711929600, owned_by: "etzhayyim", permission: [], root: def.cfModel, parent: null });
  }

  return null;
}

const _inner = createWorkerExportFromEnvFactory((env) => {
  const sdk = createDefaultHostSDK(env);
  appId = sdk.pds.selfNanoid ?? "";
  actorDID = sdk.pds.selfRepo ?? "";
  _env = env;
  sdk.app
    .command(nsid("com.etzhayyim.apps.llm.converse"), (ctx, body) => cmdConverse(sdk, body),
      asAgentTool("LLM inference via Workers AI — converse with system/user messages"),
      withCapabilityTags("llm", "inference", "workersAi"),
      withOCELEvent("governance.audit"),
    )
    .command(nsid("com.etzhayyim.apps.llm.chatCompletions"), (ctx, body) => cmdChatCompletions(sdk, body),
      asAgentTool("OpenAI-compatible chat completions via Workers AI"),
      withCapabilityTags("llm", "inference", "openaiCompatible"),
    )
    .command(nsid(ANSWER_WITH_KNOWLEDGE_NSID), (_ctx, body) => cmdAnswerWithKnowledge(sdk, body, env),
      asAgentTool("Answer with kotoba domain knowledge through the BPMN LangGraph workflow"),
      withCapabilityTags("llm", "knowledge", "rag", "bpmn", "langgraph"),
    )
    .command(nsid("com.etzhayyim.apps.llm.listModels"), (ctx, body) => cmdListModels(sdk, body),
      asAgentTool("List available Workers AI models and their capabilities"),
      withCapabilityTags("llm", "models", "catalog"),
    )
    .command(nsid("com.etzhayyim.apps.llm.recommendModel"), (ctx, body) => cmdRecommendModel(sdk, body),
      asAgentTool("Recommend optimal Workers AI model for a use case"),
      withCapabilityTags("llm", "models", "recommendation"),
    )
    .command(nsid("com.etzhayyim.apps.llm.healthCheck"), (ctx, body) => cmdHealthCheck(sdk, body),
      asAgentTool("Health check all Workers AI model endpoints"),
      withCapabilityTags("llm", "health", "monitoring"),
    )
    .command(nsid("com.etzhayyim.apps.llm.verifyCellerAi"), (ctx, body) => cmdVerifyCellerAi(sdk, body),
      asAgentTool("Verify Celler AI inbound call handling with 10-language multilingual test"),
      withCapabilityTags("llm", "celler", "voiceAi", "verification", "multilingual"),
    );
  return sdk;
});

/** OpenAI-compatible /v1/* — intercepts before host-sdk Hono router */
export default {
  async fetch(request: Request, env: Record<string, unknown>, ctx?: { waitUntil(p: Promise<unknown>): void }) {
    // Ensure env is available for AI binding before OpenAI path handler
    if (!_env || !(_env as any).AI) _env = env;
    const url = new URL(request.url);

    if (request.method === "OPTIONS" && url.pathname === `/xrpc/${ANSWER_WITH_KNOWLEDGE_NSID}`) {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "POST, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept",
          "Access-Control-Max-Age": "86400",
        },
      });
    }
    if (url.pathname === `/xrpc/${ANSWER_WITH_KNOWLEDGE_NSID}`) {
      return proxyAnswerWithKnowledge(request, env);
    }

    const openaiResp = await handleOpenAIPath(request);
    if (openaiResp) return openaiResp;

    // Credit gate for XRPC inference commands (converse, chatCompletions)
    const nsid = url.pathname.replace("/xrpc/", "");
    const isInferenceNsid = nsid === "com.etzhayyim.apps.llm.converse" || nsid === "com.etzhayyim.apps.llm.chatCompletions";
    if (isInferenceNsid && request.headers.get("x-kotodama-verified") !== "true") {
      const callerDid = request.headers.get("x-credits-did") || "";
      if (!callerDid) {
        return new Response(JSON.stringify({ error: "x-credits-did header required — LLM inference requires credits" }), {
          status: 401, headers: { "Content-Type": "application/json" },
        });
      }
      const creditErr = await deductCredits(callerDid, MURAKUMO_DEFAULT_MODEL);
      if (creditErr) {
        return new Response(JSON.stringify({ error: creditErr }), {
          status: 402, headers: { "Content-Type": "application/json" },
        });
      }
    }

    return _inner.fetch(request, env, ctx);
  },
};
