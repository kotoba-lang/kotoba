// react.ts — ReAct (Reason + Act) autonomous agent loop.
//
// Think → tool_use → observe → repeat until text response or max iterations.
// Built-in tools: graph query, post, createRecord, invoke, web fetch.

import { agentConverseAsync, type LLMMessage, type LLMConverseOptions, type LLMConverseResult, type LLMToolCall } from "./llm.js";
import type { XrpcClient } from "./xrpc-client.js";

/** Tool definition passed to LLM (OpenAI function calling format). */
export interface AgentTool {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: Record<string, unknown>;
  };
}

/** Result from executing a single tool call. */
export interface ToolResult {
  toolCallId: string;
  name: string;
  content: string;
  error?: boolean;
}

import { USE_CASE_DEFAULTS } from "./llm-model-registry.js";

/** Default model for ReAct — resolved from llm-model-registry SSoT. */
export const REACT_DEFAULT_MODEL = USE_CASE_DEFAULTS.react;

/** ReAct loop configuration. */
export interface ReactOptions {
  /** System prompt for the agent. */
  systemPrompt: string;
  /** LLM model to use. Default: llama-3.3-70b (full tool-use support). */
  model?: string;
  /** Maximum ReAct iterations before forcing stop. Default: 8. */
  maxIterations?: number;
  /** Additional tools beyond built-ins. */
  extraTools?: AgentTool[];
  /** Custom tool executor — called for tools not in built-in set. */
  customToolExecutor?: (name: string, args: Record<string, unknown>) => Promise<string>;
  /** LLM options passthrough. */
  llmOptions?: LLMConverseOptions;
}

/** ReAct loop result. */
export interface ReactResult {
  /** Final text content from the agent. */
  content: string;
  /** Number of iterations executed. */
  iterations: number;
  /** All tool calls made during the loop. */
  toolCallLog: Array<{ name: string; args: string; result: string }>;
  /** LLM model used. */
  model: string;
}

// ── Built-in Tool Definitions ──────────────────────────────────────────

const TOOL_GRAPH_QUERY: AgentTool = {
  type: "function",
  function: {
    name: "graph_query",
    description: "Deprecated graph query tool. SQL execution was removed; use app-specific tools or records instead.",
    parameters: {
      type: "object",
      properties: {
        sql: { type: "string", description: "SQL query statement" },
        params: { type: "object", description: "Query parameters (key-value pairs)" },
      },
      required: ["sql"],
    },
  },
};

const TOOL_POST: AgentTool = {
  type: "function",
  function: {
    name: "post",
    description: "Create a social post as this agent. The post will appear in the agent's feed.",
    parameters: {
      type: "object",
      properties: {
        text: { type: "string", description: "Post text content (max 3000 chars)" },
      },
      required: ["text"],
    },
  },
};

const TOOL_CREATE_RECORD: AgentTool = {
  type: "function",
  function: {
    name: "create_record",
    description: "Create an AT Protocol record in a collection.",
    parameters: {
      type: "object",
      properties: {
        collection: { type: "string", description: "NSID collection (e.g. com.etzhayyim.apps.myapp.entry)" },
        record: { type: "object", description: "Record data object" },
      },
      required: ["collection", "record"],
    },
  },
};

const TOOL_INVOKE: AgentTool = {
  type: "function",
  function: {
    name: "invoke",
    description: "Call another agent by DID or nanoid. Returns the agent's response.",
    parameters: {
      type: "object",
      properties: {
        target: { type: "string", description: "Target agent nanoid or DID" },
        method: { type: "string", description: "Method to invoke" },
        params: { type: "object", description: "Method parameters" },
      },
      required: ["target", "method"],
    },
  },
};

const TOOL_WEB_FETCH: AgentTool = {
  type: "function",
  function: {
    name: "web_fetch",
    description: "Fetch a URL and return the response body as text. Use for retrieving web pages, APIs, or data sources.",
    parameters: {
      type: "object",
      properties: {
        url: { type: "string", description: "URL to fetch" },
        method: { type: "string", description: "HTTP method (default: GET)" },
      },
      required: ["url"],
    },
  },
};

/** All built-in tools available to agents. */
export const BUILTIN_TOOLS: AgentTool[] = [
  TOOL_GRAPH_QUERY,
  TOOL_POST,
  TOOL_CREATE_RECORD,
  TOOL_INVOKE,
  TOOL_WEB_FETCH,
];

// ── Built-in Tool Executor ─────────────────────────────────────────────

let _pdsClient: XrpcClient | null = null;

/** Set the PDS client for built-in tool dispatch. Called by index.ts during SDK init. */
export function setReactPdsClient(pds: XrpcClient): void {
  _pdsClient = pds;
}

async function executeBuiltinTool(name: string, args: Record<string, unknown>): Promise<string> {
  switch (name) {
    case "graph_query": {
      return JSON.stringify({
        error: "DeprecatedTool",
        message: "graph_query is no longer available. Use app-specific commands or Kysely-backed tools instead.",
      });
    }

    case "post": {
      if (!_pdsClient) return JSON.stringify({ error: "PDS client not initialized" });
      const text = String(args.text ?? "").slice(0, 3000);
      if (!text) return JSON.stringify({ error: "text is required" });
      const result = await _pdsClient.post(text);
      return JSON.stringify({ ok: true, uri: result?.uri ?? "" });
    }

    case "create_record": {
      if (!_pdsClient) return JSON.stringify({ error: "PDS client not initialized" });
      const collection = String(args.collection ?? "");
      const record = args.record ?? {};
      if (!collection) return JSON.stringify({ error: "collection is required" });
      const result = await _pdsClient.createRecord(collection, record);
      return JSON.stringify({ ok: true, uri: result?.uri ?? "" });
    }

    case "invoke": {
      if (!_pdsClient) return JSON.stringify({ error: "PDS client not initialized" });
      const target = String(args.target ?? "");
      const method = String(args.method ?? "");
      if (!target || !method) return JSON.stringify({ error: "target and method are required" });
      const result = await _pdsClient.invoke(target, method, (args.params as Record<string, unknown>) ?? {});
      return JSON.stringify(result ?? { ok: true });
    }

    case "web_fetch": {
      const url = String(args.url ?? "");
      if (!url) return JSON.stringify({ error: "url is required" });
      const method = String(args.method ?? "GET");
      const resp = await fetch(url, { method, headers: { "User-Agent": "KotodamaAgent/1.0" }, signal: AbortSignal.timeout(10_000) });
      const text = await resp.text();
      return text.slice(0, 8000);
    }

    default:
      return JSON.stringify({ error: `unknown tool: ${name}` });
  }
}

// ── ReAct Loop ─────────────────────────────────────────────────────────

/** Build a prompt-based tool calling system message for models without native tool_use. */
function buildToolPrompt(tools: AgentTool[]): string {
  const toolList = tools.map((t) =>
    `- ${t.function.name}: ${t.function.description}\n  Parameters: ${JSON.stringify(t.function.parameters)}`
  ).join("\n");
  return `\n\n## TOOLS\nYou MUST use tools to gather data before answering. Do NOT guess or make up data.\nTo call a tool, output EXACTLY this JSON (nothing else):\n\`\`\`json\n{"tool": "tool_name", "args": {"param": "value"}}\n\`\`\`\nAfter you see the tool result, write your final answer as normal text.\n\nAvailable tools:\n${toolList}\n\nIMPORTANT: Always call graph_query first to get real data. Then call post to share your findings.`;
}

/** Try to parse prompt-based tool call from LLM text content. */
function parsePromptToolCall(content: string): { name: string; args: Record<string, unknown> } | null {
  const jsonMatch = content.match(/```json\s*\n?([\s\S]*?)\n?```/) ?? content.match(/\{[\s\S]*"tool"[\s\S]*\}/);
  if (!jsonMatch) return null;
  try {
    const raw = jsonMatch[1] ?? jsonMatch[0];
    const parsed = JSON.parse(raw.trim());
    if (parsed.tool && typeof parsed.tool === "string") {
      return { name: parsed.tool, args: parsed.args ?? parsed.arguments ?? {} };
    }
  } catch { /* not valid JSON */ }
  return null;
}

/**
 * Execute a ReAct loop: think → tool_use → observe → repeat.
 *
 * Supports two modes:
 * 1. Native tool calling (models that return tool_calls in response)
 * 2. Prompt-based tool calling (fallback for models like qwen3 that ignore tools param)
 */
export async function agentReact(
  task: string,
  options: ReactOptions,
): Promise<ReactResult> {
  const maxIterations = options.maxIterations ?? 8;
  const tools = [...BUILTIN_TOOLS, ...(options.extraTools ?? [])];
  const builtinNames = new Set(BUILTIN_TOOLS.map((t) => t.function.name));
  const allToolNames = new Set(tools.map((t) => t.function.name));
  const toolCallLog: ReactResult["toolCallLog"] = [];

  // System prompt includes prompt-based tool instructions as fallback
  const systemPrompt = options.systemPrompt + buildToolPrompt(tools);

  const messages: LLMMessage[] = [
    { role: 0, content: systemPrompt },
    { role: 1, content: task },
  ];

  const llmOpts: LLMConverseOptions = {
    ...options.llmOptions,
    model: options.model ?? options.llmOptions?.model ?? REACT_DEFAULT_MODEL,
    tools,
    toolChoice: "auto",
  };

  let lastResult: LLMConverseResult | null = null;

  for (let i = 0; i < maxIterations; i++) {
    const result = await agentConverseAsync(messages, llmOpts);
    lastResult = result;

    // Check for native tool calls first
    let toolCalls = result.toolCalls;

    // Fallback: parse prompt-based tool call from text content
    if (toolCalls.length === 0 && result.content) {
      const parsed = parsePromptToolCall(result.content);
      if (parsed && allToolNames.has(parsed.name)) {
        toolCalls = [{
          id: `prompt_${Date.now()}`,
          name: parsed.name,
          arguments: JSON.stringify(parsed.args),
        }];
      }
    }

    // No tool calls — agent is done reasoning
    if (toolCalls.length === 0) {
      return {
        content: result.content,
        iterations: i + 1,
        toolCallLog,
        model: result.model,
      };
    }

    // Add assistant message to history
    messages.push({ role: 2, content: result.content || "" });

    // Execute each tool call and collect results
    for (const tc of toolCalls) {
      let args: Record<string, unknown>;
      try {
        args = JSON.parse(tc.arguments);
      } catch {
        args = {};
      }

      let output: string;
      try {
        if (builtinNames.has(tc.name)) {
          output = await executeBuiltinTool(tc.name, args);
        } else if (options.customToolExecutor) {
          output = await options.customToolExecutor(tc.name, args);
        } else {
          output = JSON.stringify({ error: `no executor for tool: ${tc.name}` });
        }
      } catch (e) {
        output = JSON.stringify({ error: String(e) });
      }

      toolCallLog.push({ name: tc.name, args: tc.arguments, result: output.slice(0, 2000) });

      // Add tool result as user message (prompt-based mode) or tool message (native mode)
      messages.push({
        role: tc.id.startsWith("prompt_") ? 1 : 3,
        content: `Tool result for ${tc.name}:\n${output}`,
        ...(tc.id.startsWith("prompt_") ? {} : { toolCallId: tc.id }),
      });
    }
  }

  // Hit max iterations — return whatever we have
  return {
    content: lastResult?.content || `[ReAct reached ${maxIterations} iterations without final answer]`,
    iterations: maxIterations,
    toolCallLog,
    model: lastResult?.model || "",
  };
}
