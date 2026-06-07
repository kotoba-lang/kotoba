// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import type { Insertable, Kysely } from "kysely";
import type { StrictDatabase } from "@etzhayyim/graph-schema";
import { createKyselyDb, type Hyperdrive, type KyselyDb } from "./kysely.js";

export type PrivateGraphTable = Extract<keyof StrictDatabase, `vertex_${string}` | `edge_${string}`>;

export interface WritePrivateOptions<T extends PrivateGraphTable = PrivateGraphTable> {
  db?: KyselyDb;
  hyperdrive?: Hyperdrive;
  table: T;
  values: Insertable<StrictDatabase[T]> | Array<Insertable<StrictDatabase[T]>>;
  /**
   * Delete rows with matching key values before insert. This is the preferred
   * idempotent write mode for RisingWave tables where ON CONFLICT behavior is
   * not PostgreSQL-compatible.
   */
  replaceBy?: keyof Insertable<StrictDatabase[T]> & string;
}

export interface WritePrivateResult<T extends PrivateGraphTable = PrivateGraphTable> {
  table: T;
  inserted: number;
}

const REPO_PUBLIC_TABLES = new Set<string>([
  "vertex_repo_record",
  "vertex_repo_commit",
  "vertex_repo_block",
]);

export function isPrivateGraphTable(table: string): table is PrivateGraphTable {
  return (table.startsWith("vertex_") || table.startsWith("edge_")) && !REPO_PUBLIC_TABLES.has(table);
}

export function assertPrivateGraphTable(table: string): asserts table is PrivateGraphTable {
  if (!isPrivateGraphTable(table)) {
    throw new Error(`writePrivate: ${table} is not a private typed graph table`);
  }
}

function getPrivateWriteDb(db: KyselyDb | undefined, hyperdrive: Hyperdrive | undefined): KyselyDb {
  return db ?? createKyselyDb(hyperdrive);
}

/**
 * Write app/domain state directly to typed graph tables, bypassing AT Repo
 * federation. Use this for non-social-post state that must not enter
 * `vertex_repo_record`.
 */
export async function writePrivate<T extends PrivateGraphTable>(
  options: WritePrivateOptions<T>,
): Promise<WritePrivateResult<T>> {
  const { table, values, replaceBy } = options;
  assertPrivateGraphTable(table);

  const rows = Array.isArray(values) ? values : [values];
  if (rows.length === 0) return { table, inserted: 0 };

  const db = getPrivateWriteDb(options.db, options.hyperdrive);
  if (!replaceBy) {
    await db.insertInto(table as any).values(rows as any).execute();
    return { table, inserted: rows.length };
  }

  const keyValues = rows
    .map((row) => (row as Record<string, unknown>)[replaceBy])
    .filter((value): value is string | number | bigint | boolean => value !== undefined && value !== null);

  await (db as Kysely<StrictDatabase>).transaction().execute(async (trx) => {
    if (keyValues.length > 0) {
      await trx
        .deleteFrom(table as any)
        .where(replaceBy as any, "in", keyValues as any)
        .execute();
    }
    await trx.insertInto(table as any).values(rows as any).execute();
  });

  return { table, inserted: rows.length };
}
