export type QueryLanguage =
  | "datalog"
  | "cypher"
  | "gremlin"
  | "graphdb"
  | "graphql"
  | "sparql";

export type JsonPrimitive = string | number | boolean | null;
export type JsonValue =
  | JsonPrimitive
  | JsonValue[]
  | { [key: string]: JsonValue };
export type GremlinBytecode = [string, ...JsonValue[]][];

export interface QueryOptions {
  limit?: number;
  timeoutMs?: number;
  asOf?: string;
  explain?: boolean;
  emitCid?: boolean;
}

export interface QueryRequest {
  language: QueryLanguage;
  query: string | GremlinBytecode;
  parameters?: Record<string, JsonValue>;
  database?: string;
  collections?: string[];
  options?: QueryOptions;
}

export interface QueryMeta {
  requestId: string;
  elapsedMs: number;
  basisT?: string;
  querySpecCid?: string;
  queryJobCid?: string;
  resultCid?: string;
  truncated?: boolean;
  engine?: string;
  [key: string]: JsonValue | undefined;
}

export interface QueryResult<T = JsonValue> {
  ok: true;
  language: QueryLanguage;
  data: T;
  meta: QueryMeta;
  warnings?: string[];
}

export interface RequestOptions {
  parameters?: Record<string, JsonValue>;
  database?: string;
  collections?: string[];
  options?: QueryOptions;
  signal?: AbortSignal;
  requestId?: string;
}

export interface TransportRequest {
  url: string;
  headers: Record<string, string>;
  body: string;
  signal?: AbortSignal;
}

export type Transport = (request: TransportRequest) => Promise<Response>;

export interface KotobaseClientOptions {
  endpoint?: string;
  token?: string;
  transport?: Transport;
  headers?: Record<string, string>;
}

interface ErrorBody {
  error?: {
    code?: string;
    message?: string;
    retryable?: boolean;
    requestId?: string;
    details?: JsonValue;
  };
}

export class KotobaseError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryable: boolean;
  readonly requestId: string | undefined;
  readonly details: JsonValue | undefined;

  constructor(args: {
    message: string;
    code?: string;
    status?: number;
    retryable?: boolean;
    requestId?: string;
    details?: JsonValue;
  }) {
    super(args.message);
    this.name = "KotobaseError";
    this.code = args.code ?? "query_failed";
    this.status = args.status ?? 0;
    this.retryable = args.retryable ?? false;
    this.requestId = args.requestId;
    this.details = args.details;
  }
}

const QUERY_PATH = "/xrpc/ai.gftd.apps.kotobase.query.execute";

export class KotobaseClient {
  readonly endpoint: string;
  private readonly token: string | undefined;
  private readonly transport: Transport;
  private readonly headers: Record<string, string>;

  constructor(config: KotobaseClientOptions = {}) {
    this.endpoint = (config.endpoint ?? "https://kotobase.net").replace(/\/$/, "");
    this.token = config.token;
    this.transport = config.transport ?? defaultTransport;
    this.headers = config.headers ?? {};
  }

  async query<T = JsonValue>(
    request: QueryRequest,
    requestOptions: Pick<RequestOptions, "signal" | "requestId"> = {},
  ): Promise<QueryResult<T>> {
    validateRequest(request);
    const headers: Record<string, string> = {
      accept: "application/json",
      "content-type": "application/json",
      ...this.headers,
    };
    if (this.token) headers.authorization = `Bearer ${this.token}`;
    if (requestOptions.requestId) headers["x-request-id"] = requestOptions.requestId;

    let response: Response;
    try {
      response = await this.transport({
        url: `${this.endpoint}${QUERY_PATH}`,
        headers,
        body: JSON.stringify(request),
        ...(requestOptions.signal ? { signal: requestOptions.signal } : {}),
      });
    } catch (cause) {
      throw new KotobaseError({
        code: "transport_error",
        message: cause instanceof Error ? cause.message : "Kotobase request failed",
        retryable: true,
      });
    }

    const body = await parseJson(response);
    if (!response.ok) throw errorFromResponse(response.status, body);
    if (!isQueryResult(body)) {
      throw new KotobaseError({
        code: "invalid_response",
        message: "Kotobase returned an invalid query result",
        status: response.status,
      });
    }
    return body as QueryResult<T>;
  }

  datalog<T = JsonValue>(query: string, options: RequestOptions = {}) {
    return this.query<T>(buildRequest("datalog", query, options), options);
  }

  cypher<T = JsonValue>(query: string, options: RequestOptions = {}) {
    return this.query<T>(buildRequest("cypher", query, options), options);
  }

  graphql<T = JsonValue>(query: string, options: RequestOptions = {}) {
    return this.query<T>(buildRequest("graphql", query, options), options);
  }

  graphdb<T = JsonValue>(query: string, options: RequestOptions = {}) {
    return this.query<T>(buildRequest("graphdb", query, options), options);
  }

  sparql<T = JsonValue>(query: string, options: RequestOptions = {}) {
    return this.query<T>(buildRequest("sparql", query, options), options);
  }

  gremlin<T = JsonValue>(query: GremlinBytecode, options: RequestOptions = {}) {
    return this.query<T>(buildRequest("gremlin", query, options), options);
  }
}

function buildRequest(
  language: QueryLanguage,
  query: string | GremlinBytecode,
  input: RequestOptions,
): QueryRequest {
  return {
    language,
    query,
    ...(input.parameters ? { parameters: input.parameters } : {}),
    ...(input.database ? { database: input.database } : {}),
    ...(input.collections ? { collections: input.collections } : {}),
    ...(input.options ? { options: input.options } : {}),
  };
}

function validateRequest(request: QueryRequest): void {
  if (request.language === "gremlin") {
    if (!Array.isArray(request.query) || request.query.length === 0) {
      throw new TypeError("Gremlin query must be non-empty bytecode");
    }
  } else if (typeof request.query !== "string" || request.query.trim() === "") {
    throw new TypeError(`${request.language} query must be a non-empty string`);
  }
}

async function parseJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    throw new KotobaseError({
      code: "invalid_response",
      message: "Kotobase returned a non-JSON response",
      status: response.status,
      retryable: response.status >= 500,
    });
  }
}

function errorFromResponse(status: number, value: unknown): KotobaseError {
  const body = value as ErrorBody;
  return new KotobaseError({
    status,
    message: body?.error?.message ?? `Kotobase query failed with HTTP ${status}`,
    retryable: body?.error?.retryable ?? status >= 500,
    ...(body?.error?.code ? { code: body.error.code } : {}),
    ...(body?.error?.requestId ? { requestId: body.error.requestId } : {}),
    ...(body?.error?.details !== undefined ? { details: body.error.details } : {}),
  });
}

function isQueryResult(value: unknown): value is QueryResult {
  if (!value || typeof value !== "object") return false;
  const result = value as Partial<QueryResult>;
  return result.ok === true && typeof result.language === "string" &&
    !!result.meta && typeof result.meta.requestId === "string" &&
    typeof result.meta.elapsedMs === "number" && "data" in result;
}

const defaultTransport: Transport = ({ url, headers, body, signal }) =>
  fetch(url, {
    method: "POST",
    headers,
    body,
    ...(signal ? { signal } : {}),
  });
