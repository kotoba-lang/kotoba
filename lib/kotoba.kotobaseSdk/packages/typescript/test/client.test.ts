import assert from "node:assert/strict";
import test from "node:test";
import { KotobaseClient, KotobaseError, type TransportRequest } from "../src/index.js";

test("cypher sends the common envelope and authentication", async () => {
  let captured: TransportRequest | undefined;
  const client = new KotobaseClient({
    endpoint: "https://example.test/",
    token: "secret",
    transport: async (request) => {
      captured = request;
      return Response.json({
        ok: true,
        language: "cypher",
        data: { columns: ["n.name"], rows: [["Ada"]] },
        meta: { requestId: "req-1", elapsedMs: 2 },
      });
    },
  });

  const result = await client.cypher("MATCH (n:users) RETURN n.name", {
    parameters: { role: "admin" },
    requestId: "client-1",
  });

  assert.equal(captured?.url, "https://example.test/xrpc/ai.gftd.apps.kotobase.query.execute");
  assert.equal(captured?.headers.authorization, "Bearer secret");
  assert.equal(captured?.headers["x-request-id"], "client-1");
  assert.deepEqual(JSON.parse(captured?.body ?? ""), {
    language: "cypher",
    query: "MATCH (n:users) RETURN n.name",
    parameters: { role: "admin" },
  });
  assert.equal(result.meta.requestId, "req-1");
});

test("gremlin accepts bytecode and rejects an empty traversal", async () => {
  const client = new KotobaseClient({
    transport: async () => Response.json({
      ok: true,
      language: "gremlin",
      data: ["Ada"],
      meta: { requestId: "req-2", elapsedMs: 1 },
    }),
  });
  const result = await client.gremlin([["V"], ["hasLabel", "users"], ["values", "name"]]);
  assert.deepEqual(result.data, ["Ada"]);
  await assert.rejects(() => client.gremlin([]), TypeError);
});

test("structured errors become KotobaseError", async () => {
  const client = new KotobaseClient({
    transport: async () => Response.json(
      { error: { code: "engine_unavailable", message: "Cypher is disabled", retryable: true, requestId: "req-3" } },
      { status: 503 },
    ),
  });
  await assert.rejects(
    () => client.cypher("MATCH (n:users) RETURN n.name"),
    (error: unknown) => error instanceof KotobaseError &&
      error.code === "engine_unavailable" && error.status === 503 && error.retryable,
  );
});

test("graphdb sends SPARQL with a repository name", async () => {
  let captured: TransportRequest | undefined;
  const client = new KotobaseClient({
    transport: async (request) => {
      captured = request;
      return Response.json({
        ok: true,
        language: "graphdb",
        data: { head: { vars: ["s"] }, results: { bindings: [] } },
        meta: { requestId: "req-graphdb", elapsedMs: 1 },
      });
    },
  });
  await client.graphdb("SELECT ?s WHERE { ?s ?p ?o }", { database: "default" });
  assert.deepEqual(JSON.parse(captured?.body ?? ""), {
    language: "graphdb",
    query: "SELECT ?s WHERE { ?s ?p ?o }",
    database: "default",
  });
});
