import { describe, expect, it } from "vitest";
import { assertPrivateGraphTable, isPrivateGraphTable, writePrivate } from "../src/private-write.js";

function createMockDb() {
  const calls: Array<{ op: string; table: string; payload?: unknown }> = [];
  const db = {
    insertInto: (table: string) => ({
      values: (values: unknown) => ({
        execute: async () => {
          calls.push({ op: "insert", table, payload: values });
        },
      }),
    }),
    deleteFrom: (table: string) => ({
      where: (column: string, op: string, values: unknown) => ({
        execute: async () => {
          calls.push({ op: "delete", table, payload: { column, op, values } });
        },
      }),
    }),
    transaction: () => ({
      execute: async (fn: (trx: unknown) => Promise<void>) => fn(db),
    }),
    calls,
  };
  return db as any;
}

describe("writePrivate", () => {
  it("accepts typed graph tables and rejects repo-public tables", () => {
    expect(isPrivateGraphTable("vertex_gov_record")).toBe(true);
    expect(isPrivateGraphTable("edge_follows")).toBe(true);
    expect(isPrivateGraphTable("vertex_repo_record")).toBe(false);
    expect(isPrivateGraphTable("vertex_repo_commit")).toBe(false);
    expect(isPrivateGraphTable("plain_table")).toBe(false);
    expect(() => assertPrivateGraphTable("vertex_repo_record")).toThrow(/writePrivate/);
  });

  it("inserts one or more rows into a private graph table", async () => {
    const db = createMockDb();
    const result = await writePrivate({
      db,
      table: "vertex_gov_record",
      values: { vertex_id: "gov:1", record_kind: "com.etzhayyim.gov.test", value_json: "{}" },
    });

    expect(result).toEqual({ table: "vertex_gov_record", inserted: 1 });
    expect(db.calls).toEqual([
      {
        op: "insert",
        table: "vertex_gov_record",
        payload: [{ vertex_id: "gov:1", record_kind: "com.etzhayyim.gov.test", value_json: "{}" }],
      },
    ]);
  });

  it("supports delete-before-insert replacement by key", async () => {
    const db = createMockDb();
    const result = await writePrivate({
      db,
      table: "vertex_gov_record",
      replaceBy: "vertex_id",
      values: [
        { vertex_id: "gov:1", value_json: "{\"n\":1}" },
        { vertex_id: "gov:2", value_json: "{\"n\":2}" },
      ],
    });

    expect(result.inserted).toBe(2);
    expect(db.calls).toEqual([
      {
        op: "delete",
        table: "vertex_gov_record",
        payload: { column: "vertex_id", op: "in", values: ["gov:1", "gov:2"] },
      },
      {
        op: "insert",
        table: "vertex_gov_record",
        payload: [
          { vertex_id: "gov:1", value_json: "{\"n\":1}" },
          { vertex_id: "gov:2", value_json: "{\"n\":2}" },
        ],
      },
    ]);
  });

  it("refuses to write vertex_repo_record", async () => {
    await expect(writePrivate({
      db: createMockDb(),
      table: "vertex_repo_record" as any,
      values: { uri: "at://did/app.bsky.feed.post/rkey" },
    })).rejects.toThrow(/not a private typed graph table/);
  });
});
