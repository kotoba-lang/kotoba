type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
type QueryLanguage = "datalog" | "cypher" | "gremlin" | "graphdb" | "graphql" | "sparql";
type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

interface QueryRequest {
  language: QueryLanguage;
  query: string | Json[][];
  parameters?: Record<string, Json>;
  database?: string;
  collections?: string[];
  options?: {
    limit?: number;
    timeoutMs?: number;
    asOf?: string;
    explain?: boolean;
    emitCid?: boolean;
  };
}

interface UpstreamResult {
  data: Json;
  meta?: Record<string, Json>;
  warnings?: string[];
}

const PATH = "/xrpc/ai.gftd.apps.kotobase.query.execute";
const MAX_BODY_BYTES = 131_072;
const LANGUAGES = new Set<QueryLanguage>(["datalog", "cypher", "gremlin", "graphdb", "graphql", "sparql"]);
const CORS: Record<string, string> = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, POST, OPTIONS",
  "access-control-allow-headers": "authorization, content-type, x-kotoba-did, x-request-id",
  "access-control-max-age": "86400",
};

export function createHandler(fetcher: Fetcher = fetch) {
  return async (request: Request): Promise<Response> => {
    const started = Date.now();
    const requestId = safeRequestId(request.headers.get("x-request-id")) ?? `kotobase-query-${crypto.randomUUID()}`;
    const url = new URL(request.url);
    if (url.hostname === "graphdb.kotobase.net") {
      return handleGraphDbProtocol(fetcher, request, url, requestId);
    }
    if (url.pathname !== PATH) return errorResponse(404, "not_found", "Not found", false, requestId);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: responseHeaders(requestId) });
    if (request.method !== "POST") return errorResponse(405, "method_not_allowed", "POST required", false, requestId);
    if (!hasCredential(request)) return errorResponse(401, "unauthorized", "Authentication required", false, requestId);
    const declaredLength = Number(request.headers.get("content-length") ?? "0");
    if (Number.isFinite(declaredLength) && declaredLength > MAX_BODY_BYTES) {
      return errorResponse(413, "request_too_large", "Query request exceeds 128 KiB", false, requestId);
    }

    let bodyText: string;
    try {
      bodyText = await request.text();
    } catch {
      return errorResponse(400, "invalid_request", "Unable to read request body", false, requestId);
    }
    if (new TextEncoder().encode(bodyText).byteLength > MAX_BODY_BYTES) {
      return errorResponse(413, "request_too_large", "Query request exceeds 128 KiB", false, requestId);
    }

    let input: QueryRequest;
    try {
      input = validateRequest(JSON.parse(bodyText));
    } catch (error) {
      return errorResponse(400, "invalid_request", messageOf(error), false, requestId);
    }

    try {
      const result = await dispatch(fetcher, request, input, requestId);
      return jsonResponse(200, {
        ok: true,
        language: input.language,
        data: result.data,
        meta: {
          requestId,
          elapsedMs: Date.now() - started,
          engine: engineName(input.language),
          ...(result.meta ?? {}),
        },
        ...(result.warnings?.length ? { warnings: result.warnings } : {}),
      }, requestId);
    } catch (error) {
      if (error instanceof GatewayError) {
        return errorResponse(error.status, error.code, error.message, error.retryable, requestId, error.details);
      }
      return errorResponse(502, "upstream_error", "Query engine request failed", true, requestId);
    }
  };
}

export default { fetch: createHandler() };

async function handleGraphDbProtocol(
  fetcher: Fetcher,
  request: Request,
  url: URL,
  requestId: string,
): Promise<Response> {
  if (url.pathname === "/health" && request.method === "GET") {
    return jsonResponse(200, {
      ok: true,
      service: "graphdb-rdf4j-query-compatible",
      repositories: ["default"],
      readOnly: true,
    }, requestId);
  }
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: responseHeaders(requestId) });
  }
  const match = /^\/repositories\/([^/]+)$/.exec(url.pathname);
  if (!match) return errorResponse(404, "not_found", "Repository query endpoint not found", false, requestId);
  let repository: string;
  try {
    repository = decodeURIComponent(match[1] ?? "");
  } catch {
    return errorResponse(400, "invalid_repository", "Invalid repository identifier", false, requestId);
  }
  if (repository !== "default") {
    return errorResponse(404, "repository_unavailable", "Only the default repository is currently available", false, requestId);
  }
  if (!hasCredential(request)) return errorResponse(401, "unauthorized", "Authentication required", false, requestId);

  let query: string | null = null;
  if (request.method === "GET") {
    query = url.searchParams.get("query");
  } else if (request.method === "POST") {
    const contentType = request.headers.get("content-type")?.split(";", 1)[0]?.trim().toLowerCase();
    if (contentType === "application/sparql-query") {
      query = await request.text();
    } else if (contentType === "application/x-www-form-urlencoded") {
      query = new URLSearchParams(await request.text()).get("query");
    } else {
      return errorResponse(415, "unsupported_media_type", "Use application/sparql-query or application/x-www-form-urlencoded", false, requestId);
    }
  } else {
    return errorResponse(405, "method_not_allowed", "GET or POST required", false, requestId);
  }
  if (!query?.trim()) return errorResponse(400, "invalid_request", "SPARQL query is required", false, requestId);
  if (new TextEncoder().encode(query).byteLength > MAX_BODY_BYTES) {
    return errorResponse(413, "request_too_large", "SPARQL query exceeds 128 KiB", false, requestId);
  }

  const headers = forwardedHeaders(request, requestId);
  headers.set("content-type", "application/sparql-query; charset=utf-8");
  headers.set("accept", request.headers.get("accept") || "application/sparql-results+json");
  let upstream: Response;
  try {
    upstream = await fetcher("https://sparql.kotobase.net/sparql", {
      method: "POST",
      headers,
      body: query,
      signal: AbortSignal.timeout(30_000),
    });
  } catch {
    return errorResponse(503, "engine_unavailable", "GraphDB-compatible query engine is unavailable", true, requestId);
  }
  if (upstream.status >= 500) {
    return errorResponse(503, "engine_unavailable", "GraphDB-compatible query engine is unavailable", true, requestId);
  }
  if (!upstream.ok) {
    const code = upstream.status === 401 ? "unauthorized"
      : upstream.status === 403 ? "forbidden"
      : upstream.status === 429 ? "rate_limited"
      : "query_execution_failed";
    const message = upstream.status === 401 ? "GraphDB query authentication failed"
      : upstream.status === 403 ? "GraphDB query is forbidden"
      : upstream.status === 429 ? "GraphDB query rate limit exceeded"
      : "GraphDB-compatible SPARQL query was rejected";
    return errorResponse(upstream.status, code, message, upstream.status === 429, requestId);
  }
  const response = new Response(upstream.body, { status: upstream.status });
  const contentType = upstream.headers.get("content-type");
  if (contentType) response.headers.set("content-type", contentType);
  for (const [name, value] of responseHeaders(requestId)) {
    response.headers.set(name, value);
  }
  if (contentType) response.headers.set("content-type", contentType);
  response.headers.set("x-kotobase-repository", repository);
  response.headers.set("x-kotobase-compatibility", "graphdb-rdf4j-query-subset");
  return response;
}

async function dispatch(
  fetcher: Fetcher,
  incoming: Request,
  input: QueryRequest,
  requestId: string,
): Promise<UpstreamResult> {
  if (input.language === "gremlin") return dispatchGremlin(fetcher, incoming, input, requestId);
  const target = upstreamRequest(incoming, input, requestId);
  let response: Response;
  try {
    response = await fetcher(target.url, target.init);
  } catch {
    throw new GatewayError(503, "engine_unavailable", `${input.language} query engine is unavailable`, true);
  }
  const value = await responseJson(response);
  if (!response.ok) throw upstreamFailure(response.status, input.language, value);
  return normalize(input.language, value);
}

function upstreamRequest(incoming: Request, input: QueryRequest, requestId: string): { url: string; init: RequestInit } {
  const headers = forwardedHeaders(incoming, requestId);
  const timeout = clamp(input.options?.timeoutMs ?? 30_000, 1, 60_000);
  if (input.language === "datalog") {
    if (!input.database) throw new GatewayError(400, "database_required", "Datalog requires database", false);
    const parameterInputs = input.parameters?.inputs;
    const inputs = Array.isArray(parameterInputs) ? parameterInputs : undefined;
    return jsonUpstream("https://kotobase.net/xrpc/ai.gftd.apps.kotobase.datomic.q", headers, {
      db_name: input.database,
      query_edn: input.query,
      ...(inputs ? { inputs_edn: inputs.map(ednLiteral) } : {}),
      ...(input.options?.limit ? { limit: input.options.limit } : {}),
      ...(input.options?.asOf ? { as_of: input.options.asOf } : {}),
      ...(input.options?.emitCid !== undefined ? { emit_cid: input.options.emitCid } : {}),
    }, timeout);
  }
  if (input.language === "cypher") {
    return jsonUpstream("https://cypher.kotobase.net/db/data/transaction/commit", headers, {
      statements: [{ statement: input.query, parameters: input.parameters ?? {} }],
    }, timeout);
  }
  if (input.language === "graphql") {
    return jsonUpstream("https://graphql.kotobase.net/graphql", headers, {
      query: input.query,
      variables: input.parameters ?? {},
    }, timeout);
  }
  if (input.language === "graphdb" && input.database && input.database !== "default") {
    throw new GatewayError(501, "repository_unavailable", "Only the default GraphDB repository is currently available", false);
  }
  headers.set("content-type", "application/sparql-query; charset=utf-8");
  headers.set("accept", "application/sparql-results+json");
  return {
    url: "https://sparql.kotobase.net/sparql",
    init: { method: "POST", headers, body: input.query as string, signal: AbortSignal.timeout(timeout) },
  };
}

function jsonUpstream(url: string, headers: Headers, body: Record<string, unknown>, timeout: number) {
  headers.set("content-type", "application/json");
  headers.set("accept", "application/json");
  return {
    url,
    init: { method: "POST", headers, body: JSON.stringify(body), signal: AbortSignal.timeout(timeout) },
  };
}

async function dispatchGremlin(
  fetcher: Fetcher,
  incoming: Request,
  input: QueryRequest,
  requestId: string,
): Promise<UpstreamResult> {
  const headers = forwardedHeaders(incoming, requestId);
  headers.set("upgrade", "websocket");
  let response: Response;
  try {
    response = await fetcher("https://gremlin.kotobase.net/gremlin", { headers });
  } catch {
    throw new GatewayError(503, "engine_unavailable", "gremlin query engine is unavailable", true);
  }
  const socket = response.webSocket;
  if (response.status !== 101 || !socket) {
    const value = await responseJson(response);
    throw upstreamFailure(response.status, "gremlin", value);
  }
  socket.accept();
  const timeoutMs = clamp(input.options?.timeoutMs ?? 30_000, 1, 60_000);
  return await new Promise<UpstreamResult>((resolve, reject) => {
    const timer = setTimeout(() => {
      socket.close(1000, "timeout");
      reject(new GatewayError(408, "query_timeout", "Gremlin query timed out", true));
    }, timeoutMs);
    socket.addEventListener("message", (event) => {
      clearTimeout(timer);
      try {
        const envelope = JSON.parse(String(event.data)) as Record<string, unknown>;
        const status = envelope.status as Record<string, unknown> | undefined;
        const result = envelope.result as Record<string, unknown> | undefined;
        const code = Number(status?.code ?? 598);
        if (code !== 200) {
          reject(new GatewayError(400, "query_execution_failed", String(status?.message ?? "Gremlin query failed"), false));
        } else {
          resolve({ data: (result?.data ?? null) as Json });
        }
      } catch {
        reject(new GatewayError(502, "invalid_upstream_response", "Gremlin returned invalid JSON", true));
      } finally {
        socket.close(1000, "complete");
      }
    });
    socket.addEventListener("error", () => {
      clearTimeout(timer);
      reject(new GatewayError(502, "upstream_error", "Gremlin WebSocket failed", true));
    });
    socket.send(JSON.stringify({
      requestId,
      op: "bytecode",
      processor: "traversal",
      args: { gremlin: input.query },
    }));
  });
}

function normalize(language: QueryLanguage, value: unknown): UpstreamResult {
  const object = isObject(value) ? value : {};
  if (language === "cypher" && Array.isArray(object.errors) && object.errors.length > 0) {
    const first = isObject(object.errors[0]) ? object.errors[0] : {};
    throw new GatewayError(400, "query_execution_failed", String(first.message ?? "Cypher query failed"), false, object.errors as Json);
  }
  if (language === "datalog") {
    return {
      data: value as Json,
      meta: compactMeta(object, {
        basisT: "basis_t",
        querySpecCid: "query_spec_cid",
        queryJobCid: "query_job_cid",
        resultCid: "result_cid",
      }),
    };
  }
  if (language === "graphql" && Array.isArray(object.errors) && object.data === undefined) {
    throw new GatewayError(400, "query_execution_failed", "GraphQL query failed", false, object.errors as Json);
  }
  return {
    data: value as Json,
    ...(language === "graphdb" ? { meta: { repository: "default", protocol: "rdf4j-rest-query-subset" } } : {}),
  };
}

function validateRequest(value: unknown): QueryRequest {
  if (!isObject(value)) throw new TypeError("request must be a JSON object");
  if (typeof value.language !== "string" || !LANGUAGES.has(value.language as QueryLanguage)) {
    throw new TypeError("unsupported query language");
  }
  const language = value.language as QueryLanguage;
  if (language === "gremlin") {
    if (!Array.isArray(value.query) || value.query.length === 0 || !value.query.every((step) => Array.isArray(step) && typeof step[0] === "string")) {
      throw new TypeError("Gremlin query must be non-empty bytecode");
    }
  } else if (typeof value.query !== "string" || value.query.trim() === "") {
    throw new TypeError(`${language} query must be a non-empty string`);
  }
  return value as unknown as QueryRequest;
}

function forwardedHeaders(request: Request, requestId: string): Headers {
  const headers = new Headers({ "x-request-id": requestId });
  for (const name of ["authorization", "cookie", "x-kotoba-did"] as const) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  return headers;
}

function hasCredential(request: Request): boolean {
  return Boolean(request.headers.get("authorization") || request.headers.get("cookie"));
}

async function responseJson(response: Response): Promise<unknown> {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    if (!response.ok) return { error: { message: text.slice(0, 512) } };
    throw new GatewayError(502, "invalid_upstream_response", "Query engine returned non-JSON data", true);
  }
}

function upstreamFailure(status: number, language: QueryLanguage, value: unknown): GatewayError {
  const object = isObject(value) ? value : {};
  const nested = isObject(object.error) ? object.error : {};
  const message = status >= 500 ? `${language} query engine is unavailable`
    : typeof nested.message === "string" ? nested.message
    : typeof nested.reason === "string" ? nested.reason
    : `${language} query engine returned HTTP ${status}`;
  const mappedStatus = status === 401 || status === 403 || status === 408 || status === 429 ? status : status >= 500 ? 503 : 400;
  const code = status === 401 ? "unauthorized" : status === 403 ? "forbidden" : status === 429 ? "rate_limited"
    : status >= 500 ? "engine_unavailable" : "query_execution_failed";
  return new GatewayError(mappedStatus, code, message, status === 408 || status === 429 || status >= 500);
}

function compactMeta(source: Record<string, unknown>, keys: Record<string, string>): Record<string, Json> {
  const result: Record<string, Json> = {};
  for (const [output, input] of Object.entries(keys)) {
    const value = source[input];
    if (typeof value === "string") result[output] = value;
  }
  return result;
}

function ednLiteral(value: Json): string {
  if (value === null) return "nil";
  if (typeof value === "string") return JSON.stringify(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function safeRequestId(value: string | null): string | null {
  return value && /^[\x21-\x7e]{1,128}$/.test(value) ? value : null;
}

function engineName(language: QueryLanguage): string {
  return ({
    datalog: "kotobase-datomic",
    cypher: "org-opencypher-cypher",
    gremlin: "org-apache-tinkerpop-gremlin",
    graphdb: "graphdb-rdf4j-query-compatible",
    graphql: "org-graphql-http",
    sparql: "org-w3-sparql-protocol",
  })[language];
}

function jsonResponse(status: number, value: unknown, requestId: string): Response {
  return new Response(JSON.stringify(value), { status, headers: responseHeaders(requestId) });
}

function errorResponse(status: number, code: string, message: string, retryable: boolean, requestId: string, details?: Json): Response {
  return jsonResponse(status, { error: { code, message, retryable, requestId, ...(details !== undefined ? { details } : {}) } }, requestId);
}

function responseHeaders(requestId: string): Headers {
  return new Headers({
    ...CORS,
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "x-kotobase-request-id": requestId,
  });
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, Math.trunc(value)));
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "Invalid request";
}

class GatewayError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly retryable: boolean,
    readonly details?: Json,
  ) {
    super(message);
  }
}
