// kotoba Datomic substrate client (TypeScript) — the RW-free replacement for
// createKyselyDb / Hyperdrive / Kysely across the inherited 60-apps.
//
// ADR-2605262130 + ADR-2605312345: the kotoba Datom log is first-class canonical
// state; the read path is `kotoba-kqe` over the log (no projection layer). This is
// the TS mirror of `kotodama.kotoba_datomic` — identical NSIDs, identical
// `vertex_*`/`edge_*` → attribute-namespace mapping, identical select/insert shims —
// so a Python worker and a TS app project the same Datoms the same way.
//
// Dependency-free (global `fetch`, works in CF Workers + Node 18+). No kysely,
// no Hyperdrive, no psycopg.

export const NSID_TRANSACT = "com.etzhayyim.apps.kotoba.datomic.transact";
export const NSID_Q = "com.etzhayyim.apps.kotoba.datomic.q";
export const NSID_PULL = "com.etzhayyim.apps.kotoba.datomic.pull";
export const NSID_SESSION_VERIFY = "com.etzhayyim.pds.session.verify";

export const DEFAULT_KOTOBA_URL = "http://127.0.0.1:8077";
export const DEFAULT_KOTOBA_GRAPH = "etzhayyim/kotodama/graph";

export type EdnScalar = string | number | boolean | null;
export type Row = Record<string, unknown>;

// ───────────────────────────── EDN serialization ─────────────────────────────

export function ednStr(s: string): string {
  const out = s
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/\n/g, "\\n")
    .replace(/\t/g, "\\t");
  return `"${out}"`;
}

/** Serialize a JS value to EDN. A string that already looks like `:ns/name` is
 *  emitted verbatim (keyword passthrough); any other string is quoted. */
export function ednVal(x: unknown): string {
  if (x === null || x === undefined) return "nil";
  if (typeof x === "boolean") return x ? "true" : "false";
  if (typeof x === "number") return String(x);
  if (typeof x === "string") {
    if (x.startsWith(":") && !x.includes(" ") && !x.includes('"')) return x;
    return ednStr(x);
  }
  if (Array.isArray(x)) return "[" + x.map(ednVal).join(" ") + "]";
  if (typeof x === "object") {
    const inner = Object.entries(x as Row)
      .map(([k, v]) => `${ednVal(k)} ${ednVal(v)}`)
      .join(" ");
    return "{" + inner + "}";
  }
  return ednStr(String(x));
}

/** Frame entity maps as a Datomic map-form tx-data vector. */
export function toTxEdn(entities: Row[], headerLines: string[] = []): string {
  const head = headerLines.map((l) => `;; ${l}\n`).join("");
  const body = entities.map((e) => ednVal(e)).join("\n ");
  return body ? `${head}[${body}]` : `${head}[]`;
}

// ───────────────────────────── row → entity mapping ─────────────────────────────

const kebab = (s: string) => s.replace(/_/g, "-");

/** `vertex_employee` → `vertex.employee` ; `edge_actor_has_role` → `edge.actor-has-role`. */
export function tableAttrNamespace(table: string): string {
  const t = table.split(".").pop() ?? table;
  if (t.startsWith("vertex_")) return "vertex." + kebab(t.slice("vertex_".length));
  if (t.startsWith("edge_")) return "edge." + kebab(t.slice("edge_".length));
  return "ent." + kebab(t);
}

/** Convert a `vertex_*`/`edge_*` SQL-shaped row into a kotoba entity map.
 *  `null`/`undefined` columns are dropped (no NULL datom). */
export function rowToEntity(table: string, row: Row): Row {
  const ns = tableAttrNamespace(table);
  const ent: Row = {};
  for (const [col, val] of Object.entries(row)) {
    if (val === null || val === undefined) continue;
    ent[`:${ns}/${kebab(col)}`] = val;
  }
  return ent;
}

export function identityAttr(table: string, idColumn = "vertex_id"): string {
  return `:${tableAttrNamespace(table)}/${kebab(idColumn)}`;
}

/** Schema-install tx declaring a table's `:db.unique/identity` attribute (upsert). */
export function schemaInstallEdn(table: string, idColumn = "vertex_id"): string {
  const ns = tableAttrNamespace(table);
  return toTxEdn(
    [
      {
        ":db/ident": `:${ns}/${kebab(idColumn)}`,
        ":db/unique": ":db.unique/identity",
        ":db/cardinality": ":db.cardinality/one",
      },
    ],
    [`${table} identity attr install`],
  );
}

// ───────────────────────────── client ─────────────────────────────

export class KotobaTransactError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "KotobaTransactError";
  }
}

export interface KotobaClientOptions {
  url?: string;
  graph?: string;
  /** Bearer token (operator credential) — ADR-2605231525: no platform-held key. */
  token?: string;
  /** Session PoP, verified via `com.etzhayyim.pds.session.verify` before writes. */
  sessionPop?: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
}

export class KotobaDatomicClient {
  readonly url: string;
  readonly graph: string;
  private token?: string;
  private sessionPop?: string;
  private fetchImpl: typeof fetch;
  private timeoutMs: number;
  private sessionVerified = false;

  constructor(opts: KotobaClientOptions = {}) {
    this.url = (opts.url ?? DEFAULT_KOTOBA_URL).replace(/\/+$/, "");
    this.graph = opts.graph ?? DEFAULT_KOTOBA_GRAPH;
    this.token = opts.token;
    this.sessionPop = opts.sessionPop;
    this.fetchImpl = opts.fetchImpl ?? fetch;
    this.timeoutMs = opts.timeoutMs ?? 30_000;
  }

  private async post(nsid: string, body: Row): Promise<{ status: number; json: any }> {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), this.timeoutMs);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      const tok = this.token ?? this.sessionPop;
      if (tok) headers["Authorization"] = `Bearer ${tok}`;
      const resp = await this.fetchImpl(`${this.url}/xrpc/${nsid}`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
      const text = await resp.text();
      let json: any = {};
      try {
        json = text ? JSON.parse(text) : {};
      } catch {
        json = { error: "non-json", raw: text };
      }
      return { status: resp.status, json };
    } finally {
      clearTimeout(timer);
    }
  }

  private async verifySession(): Promise<void> {
    if (this.sessionVerified || !this.sessionPop) return;
    const { status, json } = await this.post(NSID_SESSION_VERIFY, { token: this.sessionPop });
    if (status !== 200 || !json?.valid) {
      throw new KotobaTransactError(`session PoP rejected: ${JSON.stringify(json)}`);
    }
    this.sessionVerified = true;
  }

  private requireWriteCredential(): void {
    if (!this.token && !this.sessionPop) {
      throw new KotobaTransactError(
        "no write credential — pass token or sessionPop (ADR-2605231525: no platform-held key).",
      );
    }
  }

  // -- public Datomic surface --
  async transact(txEdn: string, graph?: string): Promise<any> {
    this.requireWriteCredential();
    await this.verifySession();
    const { status, json } = await this.post(NSID_TRANSACT, { graph: graph ?? this.graph, tx_edn: txEdn });
    if (status !== 200) throw new KotobaTransactError(`transact failed: ${status} ${JSON.stringify(json)}`);
    return json;
  }

  async q(queryEdn: string, args: EdnScalar[] = [], graph?: string): Promise<any[]> {
    const { status, json } = await this.post(NSID_Q, { graph: graph ?? this.graph, query: queryEdn, args });
    if (status !== 200) throw new KotobaTransactError(`query failed: ${status} ${JSON.stringify(json)}`);
    return json?.result ?? json?.rows ?? [];
  }

  async pull(selector: string, eid: EdnScalar, graph?: string): Promise<any> {
    const { status, json } = await this.post(NSID_PULL, {
      graph: graph ?? this.graph,
      selector,
      eid: ednVal(eid),
    });
    if (status !== 200) throw new KotobaTransactError(`pull failed: ${status} ${JSON.stringify(json)}`);
    return json?.entity ?? json;
  }

  // -- Kysely-shim helpers (low-friction migration off createKyselyDb) --
  async ensureSchema(table: string, idColumn = "vertex_id"): Promise<any> {
    return this.transact(schemaInstallEdn(table, idColumn));
  }

  /** Replacement for `db.insertInto(table).values(row).execute()` — upsert one entity. */
  async insertRow(table: string, row: Row): Promise<any> {
    const ent = rowToEntity(table, row);
    if (Object.keys(ent).length === 0) return { datom_count: 0 };
    return this.transact(toTxEdn([ent], [`${table} row`]));
  }

  async insertRows(table: string, rows: Row[]): Promise<any> {
    const ents = rows.map((r) => rowToEntity(table, r)).filter((e) => Object.keys(e).length > 0);
    if (ents.length === 0) return { datom_count: 0 };
    return this.transact(toTxEdn(ents, [`${table} rows (${ents.length})`]));
  }

  /** Replacement for `db.selectFrom(table).select(cols).limit(n).execute()`. */
  async selectRows(table: string, columns: string[] = [], limit = 100): Promise<Row[]> {
    const idAttr = identityAttr(table);
    return this.selectByClause(table, `[?e ${idAttr} _]`, columns, limit);
  }

  /** Replacement for `db.selectFrom(table).where(col,"=",val).select(cols).execute()`. */
  async selectWhere(
    table: string,
    column: string,
    value: EdnScalar,
    columns: string[] = [],
    limit = 100,
  ): Promise<Row[]> {
    const ns = tableAttrNamespace(table);
    const clause = `[?e :${ns}/${kebab(column)} ${ednVal(value)}]`;
    return this.selectByClause(table, clause, columns, limit);
  }

  /** Replacement for `…where(col,"=",val).limit(1).executeTakeFirst()`. */
  async selectFirstWhere(table: string, column: string, value: EdnScalar, columns: string[] = []): Promise<Row | null> {
    const rows = await this.selectWhere(table, column, value, columns, 1);
    return rows[0] ?? null;
  }

  /** Replacement for `…select(eb.fn.sum(col)).where(w,"=",v).executeTakeFirst()`.
   *  Returns the scalar aggregate (0 when no rows). `fn` ∈ count|sum|max|min|avg. */
  async aggregateWhere(
    table: string,
    fn: "count" | "sum" | "max" | "min" | "avg",
    column: string,
    whereColumn?: string,
    whereValue?: EdnScalar,
  ): Promise<number> {
    const ns = tableAttrNamespace(table);
    const clauses: string[] = [];
    const aggExpr = fn === "count" && column === "*" ? "(count ?e)" : `(${fn} ?v)`;
    if (column !== "*") clauses.push(`[?e :${ns}/${kebab(column)} ?v]`);
    if (whereColumn !== undefined) {
      clauses.push(`[?e :${ns}/${kebab(whereColumn)} ${ednVal(whereValue ?? null)}]`);
    }
    if (clauses.length === 0) clauses.push(`[?e ${identityAttr(table)} _]`);
    const query = `[:find ${aggExpr} :where ${clauses.join(" ")}]`;
    const raw = await this.q(query);
    const first = Array.isArray(raw) && raw.length ? raw[0] : null;
    const scalar = Array.isArray(first) ? first[0] : first;
    return typeof scalar === "number" ? scalar : Number(scalar ?? 0);
  }

  private async selectByClause(table: string, whereClause: string, columns: string[], limit: number): Promise<Row[]> {
    const ns = tableAttrNamespace(table);
    const selAttrs = columns.length ? columns.map((c) => `:${ns}/${kebab(c)}`) : ["*"];
    const selector = "[" + selAttrs.join(" ") + "]";
    const query = `[:find (pull ?e ${selector}) :where ${whereClause}]`;
    const raw = await this.q(query);
    const capped = raw.slice(0, Math.max(1, Math.min(limit | 0 || 100, 1000)));
    const prefix = `:${ns}/`;
    const rows: Row[] = [];
    for (const item of capped) {
      const ent = Array.isArray(item) && item.length ? item[0] : item;
      if (!ent || typeof ent !== "object") continue;
      const row: Row = {};
      for (const [k, v] of Object.entries(ent as Row)) {
        const key = String(k);
        const col = key.startsWith(prefix) ? key.slice(prefix.length) : key.replace(/^:/, "");
        row[col.replace(/-/g, "_")] = v;
      }
      rows.push(row);
    }
    return rows;
  }
}

let _defaultClient: KotobaDatomicClient | null = null;
let _config: KotobaClientOptions = {};

/** Configure the process-wide kotoba client from a Worker/pod env (mirrors
 *  `setKyselyHyperdrive`). Call once at worker init; then `createKotobaDb()` is
 *  argument-less in app code. Reads `KOTOBA_URL` / `KOTOBA_TOKEN` /
 *  `KOTOBA_SESSION_POP` / `KOTODAMA_KOTOBA_GRAPH` from the env bag. */
export function setKotobaConfig(env: Record<string, unknown> | undefined): void {
  if (!env) return;
  const s = (k: string) => (typeof env[k] === "string" ? (env[k] as string) : undefined);
  _config = {
    url: s("KOTOBA_URL"),
    graph: s("KOTODAMA_KOTOBA_GRAPH"),
    token: s("KOTOBA_TOKEN"),
    sessionPop: s("KOTOBA_SESSION_POP"),
  };
  _defaultClient = null; // rebuild on next createKotobaDb()
}

/** Process-wide default client. Mirrors `createKyselyDb` ergonomics: call once,
 *  reuse. Options passed here override anything from `setKotobaConfig`. */
export function createKotobaDb(opts: KotobaClientOptions = {}): KotobaDatomicClient {
  if (_defaultClient === null) _defaultClient = new KotobaDatomicClient({ ..._config, ...opts });
  return _defaultClient;
}
