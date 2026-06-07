import { describe, it, expect, vi } from "vitest";
import {
  ednStr,
  ednVal,
  toTxEdn,
  tableAttrNamespace,
  rowToEntity,
  identityAttr,
  schemaInstallEdn,
  KotobaDatomicClient,
  KotobaTransactError,
  DEFAULT_KOTOBA_URL,
  DEFAULT_KOTOBA_GRAPH,
} from "./kotoba-datomic.js";

describe("EDN serialization", () => {
  it("scalars", () => {
    expect(ednVal(null)).toBe("nil");
    expect(ednVal(undefined)).toBe("nil");
    expect(ednVal(true)).toBe("true");
    expect(ednVal(false)).toBe("false");
    expect(ednVal(42)).toBe("42");
    expect(ednVal(3.5)).toBe("3.5");
  });
  it("string vs keyword passthrough", () => {
    expect(ednVal("hello world")).toBe('"hello world"');
    expect(ednVal(":vertex.employee/name")).toBe(":vertex.employee/name");
    expect(ednVal(":not a kw")).toBe('":not a kw"');
  });
  it("escaping", () => {
    expect(ednVal('say "hi"')).toBe('"say \\"hi\\""');
    expect(ednStr("a\nb")).toBe('"a\\nb"');
  });
  it("collections", () => {
    expect(ednVal([1, 2, 3])).toBe("[1 2 3]");
    expect(ednVal({ ":a": 1 })).toBe("{:a 1}");
  });
  it("tx-data framing", () => {
    expect(toTxEdn([])).toBe("[]");
    const out = toTxEdn([{ ":vertex.x/vertex-id": "at://1" }]);
    expect(out.startsWith("[{")).toBe(true);
    expect(out).toContain(":vertex.x/vertex-id");
    expect(out).toContain('"at://1"');
  });
});

describe("table → attribute namespace", () => {
  it("maps vertex/edge/plain", () => {
    expect(tableAttrNamespace("vertex_employee")).toBe("vertex.employee");
    expect(tableAttrNamespace("edge_actor_has_role")).toBe("edge.actor-has-role");
    expect(tableAttrNamespace("plain_table")).toBe("ent.plain-table");
  });
  it("identity attr", () => {
    expect(identityAttr("vertex_employee")).toBe(":vertex.employee/vertex-id");
    expect(identityAttr("edge_x", "edge_id")).toBe(":edge.x/edge-id");
  });
});

describe("row → entity", () => {
  it("maps columns and drops null/undefined", () => {
    const ent = rowToEntity("vertex_employee", {
      vertex_id: "at://did/x",
      name: "Ada",
      hired_at: "2026-01-01",
      manager: null,
      note: undefined,
    });
    expect(ent).toEqual({
      ":vertex.employee/vertex-id": "at://did/x",
      ":vertex.employee/name": "Ada",
      ":vertex.employee/hired-at": "2026-01-01",
    });
  });
  it("schema install declares unique identity", () => {
    const edn = schemaInstallEdn("vertex_employee");
    expect(edn).toContain(":vertex.employee/vertex-id");
    expect(edn).toContain(":db.unique/identity");
    expect(edn).toContain(":db.cardinality/one");
  });
});

describe("client", () => {
  it("defaults", () => {
    const c = new KotobaDatomicClient();
    expect(c.url).toBe(DEFAULT_KOTOBA_URL);
    expect(c.graph).toBe(DEFAULT_KOTOBA_GRAPH);
  });

  it("selectRows builds a pull query and projects back to snake_case rows", async () => {
    const fetchImpl = vi.fn(async (_url: any, init: any) => {
      const body = JSON.parse(init.body);
      // assert the datalog query shape
      expect(body.query).toContain(
        "(pull ?e [:vertex.employee/vertex-id :vertex.employee/name])",
      );
      expect(body.query).toContain("[?e :vertex.employee/vertex-id _]");
      return new Response(
        JSON.stringify({
          result: [[{ ":vertex.employee/vertex-id": "at://1", ":vertex.employee/name": "Ada" }]],
        }),
        { status: 200 },
      );
    });
    const c = new KotobaDatomicClient({ fetchImpl: fetchImpl as unknown as typeof fetch });
    const rows = await c.selectRows("vertex_employee", ["vertex_id", "name"]);
    expect(rows).toEqual([{ vertex_id: "at://1", name: "Ada" }]);
  });

  it("transact without credential throws (no platform-held key)", async () => {
    const c = new KotobaDatomicClient();
    await expect(c.transact("[]")).rejects.toBeInstanceOf(KotobaTransactError);
  });

  it("insertRow upserts an entity with a credential", async () => {
    const fetchImpl = vi.fn(async (_url: any, init: any) => {
      const body = JSON.parse(init.body);
      expect(body.tx_edn).toContain(":vertex.employee/vertex-id");
      return new Response(JSON.stringify({ tx_cid: "cid1", datom_count: 2 }), { status: 200 });
    });
    const c = new KotobaDatomicClient({ token: "op-token", fetchImpl: fetchImpl as unknown as typeof fetch });
    const res = await c.insertRow("vertex_employee", { vertex_id: "at://1", name: "Ada" });
    expect(res.datom_count).toBe(2);
  });
});
