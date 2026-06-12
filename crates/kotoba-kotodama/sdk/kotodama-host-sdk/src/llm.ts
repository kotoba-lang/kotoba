// llm.ts — Async LLM helpers via llm.etzhayyim.com (Ollama GPU pod, zero cost).
// App Workers → llm.etzhayyim.com/v1/chat/completions (x-kotodama-verified bypass credits gate)
//           → LLM Worker → Ollama (172-236-133-64.ip.linodeusercontent.com, routing-gateway 非経由)
// PDS gateway path: App Workers (with PDS_SERVICE) → atproto.etzhayyim.com/xrpc/com.etzhayyim.apps.llm.chatCompletions
//                   → MURAKUMO_SERVICE binding → LLM Worker (zero extra hop, preferred when available)

import { str } from "./helpers.js";

export interface LLMMessage {
  role: 0 | 1 | 2 | 3;
  content: string;
  toolCalls?: unknown;
  toolCallId?: unknown;
}

export interface LLMConverseOptions {
  model?: string;
  useCase?: string;
  contextId?: string;
  scrubPii?: boolean;
  [key: string]: unknown;
}

/** Tool call returned by LLM when finish_reason is "tool_use". */
export interface LLMToolCall {
  id: string;
  name: string;
  arguments: string;
}

export interface LLMConverseResult {
  content: string;
  model: string;
  finishReason: string;
  /** Tool calls requested by the LLM (present when finishReason === "tool_use"). */
  toolCalls: LLMToolCall[];
}

/**
 * LLM gateway — OpenAI-compatible endpoint (zero CF cost, Ollama Tier 0 only).
 * Uses x-kotodama-verified: true to bypass credits gate (internal call).
 * ollama.etzhayyim.com is NOT used directly: CF Worker subrequests to *.etzhayyim.com are
 * intercepted by routing-gateway; WORKER_OLLAMA binding does not exist → 404.
 * llm.etzhayyim.com routes internally to Ollama via Linode NB hostname (172-236-133-64.*).
 */
const MURAKUMO_CHAT_URL = "https://llm.etzhayyim.com/v1/chat/completions";
/** PDS XRPC endpoint that proxies to LLM Worker via MURAKUMO_SERVICE binding (preferred when PDS gateway available). */
const PDS_MURAKUMO_XRPC_URL = "https://atproto.etzhayyim.com/xrpc/com.etzhayyim.apps.llm.chatCompletions";
import { MURAKUMO_DEFAULT_MODEL } from "./llm-model-registry.js";

// ── Internal fetch (set via setLLMFetch) ──

let _fetch: (input: string | Request, init?: RequestInit) => Promise<Response> = globalThis.fetch;
let _pdsGatewayFetch: ((input: string | Request, init?: RequestInit) => Promise<Response>) | null = null;
let _internalToken: string = "";

export function setLLMFetch(
  fetcher: (input: string | Request, init?: RequestInit) => Promise<Response>,
  token: string,
): void {
  _fetch = fetcher;
  _internalToken = token;
}

/** Set PDS gateway fetch for LLM (App Workers use PDS_SERVICE to reach LLM) */
export function setLLMPdsGateway(
  pdsFetch: (input: string | Request, init?: RequestInit) => Promise<Response>,
): void {
  _pdsGatewayFetch = pdsFetch;
}

/** Get PDS gateway fetch for direct PDS XRPC calls (e.g., AI image generation). */
export function getPdsGatewayFetch(): ((input: string | Request, init?: RequestInit) => Promise<Response>) | null {
  return _pdsGatewayFetch;
}

// ── Hayate model detection ──

const HAYATE_MODELS = ["hayate-v4", "hayate-v5", "etzhayyim/hayate-v4", "etzhayyim/hayate-v5"];

function isHayateModel(model?: string): boolean {
  return !!model && HAYATE_MODELS.includes(model);
}

function toChatRole(role: LLMMessage["role"]): "system" | "user" | "assistant" | "tool" {
  if (role === 0) return "system";
  if (role === 1) return "user";
  if (role === 2) return "assistant";
  return "tool";
}

// ── Core async converse ──

export async function agentConverseAsync(
  messages: LLMMessage[],
  options: LLMConverseOptions = {},
): Promise<LLMConverseResult> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
    "x-kotodama-verified": "true",
  };
  if (_internalToken) {
    headers["authorization"] = `Bearer ${_internalToken}`;
  }

  const useHayate = isHayateModel(options.model);
  const murakumoModel = options.model || MURAKUMO_DEFAULT_MODEL;
  const body = useHayate
    ? JSON.stringify({ messages, options })
    : JSON.stringify({
      model: murakumoModel,
      messages: messages.map((m) => ({ ...m, role: toChatRole(m.role) })),
      "max_tokens": options.maxTokens ?? 8192,
      temperature: options.temperature ?? 0.7,
      ...(options.tools ? { tools: options.tools, "tool_choice": options.toolChoice ?? "auto" } : {}),
    });

  try {
    let resp: Response;
    if (useHayate) {
      // Hayate models → Murakumo (on-prem MLX fleet) via PDS service binding
      resp = await _fetch("https://atproto.etzhayyim.com/xrpc/com.etzhayyim.agent.converse", {
        method: "POST", headers, body,
      });
    } else {
      // Non-Hayate: prefer PDS gateway (Worker service binding) when set — avoids CF WAF 1033
      // on same-account subrequests to llm.etzhayyim.com. Fall back to globalThis.fetch otherwise.
      if (_pdsGatewayFetch) {
        resp = await _pdsGatewayFetch(PDS_MURAKUMO_XRPC_URL, { method: "POST", headers, body });
      } else {
        resp = await globalThis.fetch(MURAKUMO_CHAT_URL, { method: "POST", headers, body });
      }
    }

    if (!resp.ok) {
      const text = await resp.text().catch((error) => {
        console.warn("[llm] failed reading error response body", error);
        return "";
      });
      if (resp.status === 401) throw new Error(`LLM auth failed: ${text.slice(0, 200)}`);
      if (resp.status === 429) throw new Error(`LLM rate limited: ${text.slice(0, 200)}`);
      throw new Error(`LLM error ${resp.status}: ${text.slice(0, 200)}`);
    }

    const result = await resp.json() as {
      content?: string;
      model?: string;
      finishReason?: string;
      finish_reason?: string;
      cfModel?: string;
      toolCalls?: Array<{ id?: string; function?: { name?: string; arguments?: string } }>;
      tool_calls?: Array<{ id?: string; function?: { name?: string; arguments?: string } }>;
      choices?: Array<{ finish_reason?: string; message?: { content?: string; tool_calls?: Array<{ id?: string; function?: { name?: string; arguments?: string } }> } }>;
    };
    const firstChoice = Array.isArray(result.choices) ? result.choices[0] : undefined;
    const content = str(result.content ?? firstChoice?.message?.content ?? "");
    const finishReason = str(result.finishReason ?? result.finish_reason ?? firstChoice?.finish_reason ?? "stop");
    const rawToolCalls = result.toolCalls ?? result.tool_calls ?? firstChoice?.message?.tool_calls ?? (firstChoice?.message as any)?.toolCalls ?? [];
    const toolCalls: LLMToolCall[] = rawToolCalls.map((tc: any) => ({
      id: str(tc.id ?? `call_${Date.now()}`),
      name: str(tc.function?.name ?? ""),
      arguments: str(tc.function?.arguments ?? "{}"),
    })).filter((tc: LLMToolCall) => tc.name);
    return {
      content,
      model: str(result.model ?? result.cfModel ?? ""),
      finishReason: toolCalls.length > 0 ? "tool_use" : finishReason,
      toolCalls,
    };
  } catch (err) {
    throw err instanceof Error ? err : new Error(`LLM error: ${err}`);
  }
}

// ── Convenience helpers ──

export async function llmAsk(prompt: string): Promise<string> {
  const result = await agentConverseAsync([{ role: 1, content: prompt }], {});
  return result.content;
}

export async function llmCall(systemPrompt: string, userPrompt: string, model?: string): Promise<string> {
  const result = await agentConverseAsync(
    [{ role: 0, content: systemPrompt }, { role: 1, content: userPrompt }],
    model ? { model } : {},
  );
  return result.content.trim();
}

export async function llmJson(systemPrompt: string, userPrompt: string, model?: string): Promise<Record<string, unknown>> {
  const content = await llmCall(systemPrompt, userPrompt, model);
  if (!content) return {};
  const raw = content.trim();
  const cleaned = raw.startsWith("```") ? raw.slice(raw.indexOf("\n") + 1).replace(/```\s*$/, "").trim() : raw;
  try {
    return JSON.parse(cleaned) as Record<string, unknown>;
  } catch {
    return { raw: cleaned };
  }
}
