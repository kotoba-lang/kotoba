// write-outbox.ts — Persistent outbox for failed fire-and-forget writes.
//
// Replaces volatile in-memory pendingWrites drain with durable RisingWave table.
// Failed or timed-out writes are INSERTed into vertex_write_outbox.
// PDS cron replays them via SELECT → XRPC dispatch → DELETE.
//
// Flow:
//   dispatch() → promise fails/times out → push to failedWrites[]
//   createWorkerExport drain → archiveToOutbox(failedWrites, db)
//   PDS cron (*/5 * * * *) → syncOutbox(db, replayFn)

// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import type { Kysely } from "kysely";
import type { Database } from "@etzhayyim/graph-schema";

/** A single write that failed or timed out during dispatch. */
export interface OutboxEntry {
  /** Deterministic ID for idempotency: `{timestampMs}-{type}` */
  writeId: string;
  /** Write buffer entry type (maps to XRPC NSID via dispatch table). */
  type: string;
  /** Original payload. */
  payload: unknown;
  /** App nanoid that originated the write. */
  appNanoid: string;
  /** ISO timestamp of failure. */
  failedAt: string;
  /** Error message from the failed attempt. */
  error: string;
  /** Number of replay attempts so far. */
  retryCount: number;
}

const MAX_RETRY = 5;
const MAX_SCAN = 50;

/**
 * Archive failed writes to RisingWave vertex_write_outbox.
 * Called from createWorkerExport drain handler.
 */
export async function archiveToOutbox(
  entries: OutboxEntry[],
  db: Kysely<Database>,
): Promise<void> {
  if (entries.length === 0) return;
  try {
    const rows = entries.map((e) => ({
      vertex_id: e.writeId,
      write_id: e.writeId,
      write_type: e.type,
      payload_json: JSON.stringify(e.payload),
      app_nanoid: e.appNanoid,
      failed_at: e.failedAt,
      error_message: e.error,
      retry_count: e.retryCount,
      created_date: new Date().toISOString().slice(0, 10),
      owner_did: `did:web:${e.appNanoid}.etzhayyim.com`,
    }));
    await db.insertInto("vertex_write_outbox").values(rows).execute();
    console.info(`[write-outbox] archived ${entries.length} failed writes`);
  } catch (e) {
    console.error(
      `[write-outbox] archive failed, writes lost:`,
      JSON.stringify(entries.map((e) => ({ writeId: e.writeId, type: e.type }))),
      e,
    );
  }
}

/**
 * Replay outbox entries from RisingWave. Called from PDS cron handler.
 *
 * @param db - Kysely DB instance (Hyperdrive → RisingWave).
 * @param replayFn - Function that replays a single write (XRPC dispatch).
 *                   Should throw on failure so the entry is retried next cycle.
 * @returns Stats: replayed (success), retried (updated retry_count), expired (deleted).
 */
export async function syncOutbox(
  db: Kysely<Database>,
  replayFn: (type: string, payload: unknown) => Promise<void>,
): Promise<{ replayed: number; retried: number; expired: number }> {
  const stats = { replayed: 0, retried: 0, expired: 0 };

  const rows = await db
    .selectFrom("vertex_write_outbox")
    .select([
      "vertex_id",
      "write_id",
      "write_type",
      "payload_json",
      "app_nanoid",
      "retry_count",
    ])
    .orderBy("_seq", "asc")
    .limit(MAX_SCAN)
    .execute();

  if (rows.length === 0) return stats;

  for (const row of rows) {
    const retryCount = Number(row.retry_count ?? 0);

    if (retryCount >= MAX_RETRY) {
      console.warn(
        `[write-outbox] expired writeId=${row.write_id} type=${row.write_type} after ${retryCount} retries`,
      );
      await db
        .deleteFrom("vertex_write_outbox")
        .where("vertex_id", "=", row.vertex_id!)
        .execute();
      stats.expired++;
      continue;
    }

    let payload: unknown;
    try {
      payload = row.payload_json ? JSON.parse(row.payload_json) : {};
    } catch {
      payload = {};
    }

    try {
      await replayFn(row.write_type!, payload);
      await db
        .deleteFrom("vertex_write_outbox")
        .where("vertex_id", "=", row.vertex_id!)
        .execute();
      stats.replayed++;
    } catch (e) {
      await db
        .updateTable("vertex_write_outbox")
        .set({
          retry_count: retryCount + 1,
          error_message: e instanceof Error ? e.message : String(e),
          failed_at: new Date().toISOString(),
        })
        .where("vertex_id", "=", row.vertex_id!)
        .execute();
      stats.retried++;
    }
  }

  if (stats.replayed > 0 || stats.retried > 0 || stats.expired > 0) {
    console.info(
      `[write-outbox] sync: replayed=${stats.replayed} retried=${stats.retried} expired=${stats.expired}`,
    );
  }

  return stats;
}

/** Generate a deterministic write ID for idempotency. */
export function generateWriteId(type: string): string {
  return `${Date.now()}-${type}`;
}
