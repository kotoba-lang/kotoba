/**
 * Kysely dialect for direct Hyperdrive-backed PostgreSQL access.
 *
 * Uses node-postgres over Cloudflare Hyperdrive to talk directly to RisingWave.
 */

// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import type { DatabaseConnection, Driver, Dialect, QueryResult, CompiledQuery, DialectAdapter } from "kysely";
import { PostgresAdapter, PostgresIntrospector, PostgresQueryCompiler } from "kysely";

export interface Hyperdrive {
  connectionString: string;
}

type PgQueryResult = { rows: Record<string, unknown>[]; rowCount: number | null };
type PgClientLike = {
  connect: () => Promise<unknown>;
  end: () => Promise<void>;
  query: (sql: string, params?: unknown[]) => Promise<PgQueryResult>;
};
type PgClientCtor = new (opts: { connectionString: string }) => PgClientLike;

/**
 * Inline LIMIT/OFFSET bind parameters as integer literals.
 * RisingWave requires LIMIT/OFFSET to be constant expressions, not bind params.
 */
function inlineLimitOffset(sql: string, parameters: readonly unknown[]): { sql: string; parameters: unknown[] } {
  if (!/\b(limit|offset)\s+\$\d+/i.test(sql)) return { sql, parameters: [...parameters] };
  const removedIndices = new Set<number>();
  const rewritten = sql.replace(/\b(limit|offset)\s+\$(\d+)/gi, (_m, kw: string, nStr: string) => {
    const idx = parseInt(nStr, 10) - 1;
    const val = parameters[idx];
    if (typeof val !== "number" || !Number.isFinite(val) || !Number.isInteger(val)) return `${kw} ${val}`;
    removedIndices.add(idx);
    return `${kw} ${val}`;
  });
  if (removedIndices.size === 0) return { sql: rewritten, parameters: [...parameters] };
  const keptParams: unknown[] = [];
  const oldToNew = new Map<number, number>();
  for (let i = 0; i < parameters.length; i++) {
    if (removedIndices.has(i)) continue;
    oldToNew.set(i + 1, keptParams.length + 1);
    keptParams.push(parameters[i]);
  }
  const renumbered = rewritten.replace(/\$(\d+)/g, (m, nStr: string) => {
    const newN = oldToNew.get(parseInt(nStr, 10));
    return newN ? `$${newN}` : m;
  });
  return { sql: renumbered, parameters: keptParams };
}

class HyperdriveConnection implements DatabaseConnection {
  constructor(private pgClient: PgClientLike) {}

  async beginTransaction(): Promise<void> {
    await this.pgClient.query("BEGIN");
  }

  async commitTransaction(): Promise<void> {
    await this.pgClient.query("COMMIT");
  }

  async rollbackTransaction(): Promise<void> {
    await this.pgClient.query("ROLLBACK");
  }

  async close(): Promise<void> {
    try {
      await this.pgClient.end();
    } catch (error) {
      console.warn("HyperdriveDialect: failed to close pg client", error);
    }
  }

  async executeQuery<R>(compiledQuery: CompiledQuery): Promise<QueryResult<R>> {
    const { sql: rawSql, parameters: rawParams } = compiledQuery;
    const { sql, parameters } = inlineLimitOffset(rawSql, rawParams);
    const result = await this.pgClient.query(sql, parameters as unknown[]);
    const rows = result.rows.map((row) => row as Record<string, unknown> as R);
    return {
      rows,
      numAffectedRows: typeof result.rowCount === "number" ? BigInt(result.rowCount) : undefined,
    };
  }

  async *streamQuery<R>(
    _compiledQuery: CompiledQuery,
    _chunkSize: number,
  ): AsyncIterableIterator<QueryResult<R>> {
    throw new Error("HyperdriveDialect does not support streaming");
  }
}

class HyperdriveDriver implements Driver {
  // CF Workers I/O objects cannot cross request boundaries, so pg Client is
  // created fresh per acquireConnection() and closed in releaseConnection().
  // Hyperdrive pools upstream — the per-request handshake is cheap.
  private pgCtor: PgClientCtor | null = null;

  constructor(private hyperdrive: Hyperdrive) {}

  async init(): Promise<void> {
    if (!this.hyperdrive?.connectionString) {
      throw new Error("HyperdriveDialect: missing Hyperdrive connectionString");
    }
    if (!this.pgCtor) {
      const mod = (await import("pg")) as unknown as { Client: PgClientCtor };
      this.pgCtor = mod.Client;
    }
  }

  async acquireConnection(): Promise<DatabaseConnection> {
    if (!this.pgCtor) await this.init();
    const Client = this.pgCtor!;
    const pgClient = new Client({ connectionString: this.hyperdrive.connectionString });
    await pgClient.connect();
    return new HyperdriveConnection(pgClient);
  }

  async beginTransaction(conn: DatabaseConnection): Promise<void> {
    await (conn as HyperdriveConnection).beginTransaction();
  }

  async commitTransaction(conn: DatabaseConnection): Promise<void> {
    await (conn as HyperdriveConnection).commitTransaction();
  }

  async rollbackTransaction(conn: DatabaseConnection): Promise<void> {
    await (conn as HyperdriveConnection).rollbackTransaction();
  }

  async releaseConnection(conn: DatabaseConnection): Promise<void> {
    await (conn as HyperdriveConnection).close();
  }

  async destroy(): Promise<void> {
    this.pgCtor = null;
  }
}

export class HyperdriveDialect implements Dialect {
  constructor(private hyperdrive: Hyperdrive) {}

  createAdapter(): DialectAdapter {
    return new PostgresAdapter();
  }

  createDriver(): Driver {
    return new HyperdriveDriver(this.hyperdrive);
  }

  createIntrospector(db: any) {
    return new PostgresIntrospector(db);
  }

  createQueryCompiler() {
    return new PostgresQueryCompiler();
  }
}
