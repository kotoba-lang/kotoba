// write-outbox.test.ts — Tests for the write outbox archive/sync (RisingWave).

import { describe, it, expect, vi } from "vitest";
import {
  archiveToOutbox,
  syncOutbox,
  generateWriteId,
  type OutboxEntry,
} from "../src/write-outbox.js";
// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import type { Kysely } from "kysely";
import type { Database } from "@etzhayyim/graph-schema";

function makeEntry(overrides: Partial<OutboxEntry> = {}): OutboxEntry {
  return {
    writeId: generateWriteId("test-type"),
    type: "test-type",
    payload: { foo: "bar" },
    appNanoid: "test123",
    failedAt: new Date().toISOString(),
    error: "timeout",
    retryCount: 0,
    ...overrides,
  };
}

/** In-memory mock for Kysely DB operations on vertex_write_outbox. */
function createMockDb() {
  const rows: Array<Record<string, unknown>> = [];

  const db = {
    insertInto: (_table: string) => ({
      values: (vals: Record<string, unknown> | Record<string, unknown>[]) => ({
        execute: async () => {
          const arr = Array.isArray(vals) ? vals : [vals];
          rows.push(...arr);
        },
      }),
    }),
    selectFrom: (_table: string) => {
      const chain = {
        select: (_cols: string[]) => chain,
        orderBy: (_col: string, _dir?: string) => chain,
        limit: (n: number) => ({
          execute: async () => rows.slice(0, n).map((r) => ({ ...r })),
        }),
      };
      return chain;
    },
    deleteFrom: (_table: string) => ({
      where: (_col: string, _op: string, val: string) => ({
        execute: async () => {
          const idx = rows.findIndex((r) => r.vertex_id === val);
          if (idx >= 0) rows.splice(idx, 1);
        },
      }),
    }),
    updateTable: (_table: string) => ({
      set: (updates: Record<string, unknown>) => ({
        where: (_col: string, _op: string, val: string) => ({
          execute: async () => {
            const row = rows.find((r) => r.vertex_id === val);
            if (row) Object.assign(row, updates);
          },
        }),
      }),
    }),
    _rows: rows,
  } as unknown as Kysely<Database> & { _rows: typeof rows };

  return db;
}

describe("generateWriteId", () => {
  it("includes type in the ID", () => {
    const id = generateWriteId("log-append");
    expect(id).toContain("log-append");
  });

  it("generates unique IDs", () => {
    const a = generateWriteId("test");
    const b = generateWriteId("test");
    expect(typeof a).toBe("string");
    expect(typeof b).toBe("string");
  });
});

describe("archiveToOutbox", () => {
  it("does nothing for empty entries", async () => {
    const db = createMockDb();
    await archiveToOutbox([], db);
    expect(db._rows).toHaveLength(0);
  });

  it("inserts entries into vertex_write_outbox", async () => {
    const db = createMockDb();
    const entries = [makeEntry(), makeEntry({ type: "other-type" })];
    await archiveToOutbox(entries, db);

    expect(db._rows).toHaveLength(2);
    expect(db._rows[0].write_type).toBe("test-type");
    expect(db._rows[1].write_type).toBe("other-type");
    expect(db._rows[0].app_nanoid).toBe("test123");
    expect(JSON.parse(db._rows[0].payload_json as string)).toEqual({ foo: "bar" });
  });

  it("logs error but does not throw on DB failure", async () => {
    const db = {
      insertInto: () => ({
        values: () => ({
          execute: async () => { throw new Error("RisingWave down"); },
        }),
      }),
    } as unknown as Kysely<Database>;

    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    await archiveToOutbox([makeEntry()], db);
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});

describe("syncOutbox", () => {
  it("returns zeros when outbox is empty", async () => {
    const db = createMockDb();
    const replayFn = vi.fn();
    const result = await syncOutbox(db, replayFn);
    expect(result).toEqual({ replayed: 0, retried: 0, expired: 0 });
    expect(replayFn).not.toHaveBeenCalled();
  });

  it("replays entries successfully and deletes the row", async () => {
    const db = createMockDb();
    const entry = makeEntry();
    db._rows.push({
      vertex_id: entry.writeId,
      write_id: entry.writeId,
      write_type: entry.type,
      payload_json: JSON.stringify(entry.payload),
      app_nanoid: entry.appNanoid,
      retry_count: 0,
    });

    const replayFn = vi.fn().mockResolvedValue(undefined);
    const result = await syncOutbox(db, replayFn);

    expect(result.replayed).toBe(1);
    expect(result.retried).toBe(0);
    expect(result.expired).toBe(0);
    expect(replayFn).toHaveBeenCalledWith("test-type", { foo: "bar" });
    expect(db._rows).toHaveLength(0);
  });

  it("increments retry_count on failed replay", async () => {
    const db = createMockDb();
    const entry = makeEntry({ retryCount: 2 });
    db._rows.push({
      vertex_id: entry.writeId,
      write_id: entry.writeId,
      write_type: entry.type,
      payload_json: JSON.stringify(entry.payload),
      app_nanoid: entry.appNanoid,
      retry_count: 2,
    });

    const replayFn = vi.fn().mockRejectedValue(new Error("still failing"));
    const result = await syncOutbox(db, replayFn);

    expect(result.replayed).toBe(0);
    expect(result.retried).toBe(1);
    expect(db._rows).toHaveLength(1);
    expect(db._rows[0].retry_count).toBe(3);
    expect(db._rows[0].error_message).toBe("still failing");
  });

  it("expires and deletes entries that exceed MAX_RETRY", async () => {
    const db = createMockDb();
    const entry = makeEntry({ retryCount: 5 });
    db._rows.push({
      vertex_id: entry.writeId,
      write_id: entry.writeId,
      write_type: entry.type,
      payload_json: JSON.stringify(entry.payload),
      app_nanoid: entry.appNanoid,
      retry_count: 5,
    });

    const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const replayFn = vi.fn();
    const result = await syncOutbox(db, replayFn);

    expect(result.expired).toBe(1);
    expect(result.replayed).toBe(0);
    expect(replayFn).not.toHaveBeenCalled();
    expect(db._rows).toHaveLength(0);
    consoleSpy.mockRestore();
  });

  it("handles mixed outcomes (replay + retry + expire)", async () => {
    const db = createMockDb();
    db._rows.push(
      {
        vertex_id: "a", write_id: "a", write_type: "type-a",
        payload_json: "{}", app_nanoid: "test123", retry_count: 0,
      },
      {
        vertex_id: "b", write_id: "b", write_type: "type-b",
        payload_json: "{}", app_nanoid: "test123", retry_count: 0,
      },
      {
        vertex_id: "c", write_id: "c", write_type: "type-c",
        payload_json: "{}", app_nanoid: "test123", retry_count: 5,
      },
    );

    const replayFn = vi.fn()
      .mockResolvedValueOnce(undefined)        // type-a succeeds
      .mockRejectedValueOnce(new Error("fail")); // type-b fails

    const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const result = await syncOutbox(db, replayFn);

    expect(result.replayed).toBe(1);  // type-a
    expect(result.retried).toBe(1);   // type-b
    expect(result.expired).toBe(1);   // type-c
    // a and c deleted, b remains with retry_count=1
    expect(db._rows).toHaveLength(1);
    expect(db._rows[0].vertex_id).toBe("b");
    expect(db._rows[0].retry_count).toBe(1);
    consoleSpy.mockRestore();
  });
});
