import assert from "node:assert/strict";
import test from "node:test";
import { createHandler } from "../src/index.ts";

const endpoint = "https://kotobase.net/xrpc/ai.gftd.apps.kotobase.query.execute";

test("requires authentication before dispatch", async () => {
  const handler = createHandler(async () => { throw new Error("must not dispatch"); });
  const response = await handler(new Request(endpoint, {
    method: "POST",
    body: JSON.stringify({ language: "cypher", query: "MATCH (n:users) RETURN n.name" }),
  }));
  assert.equal(response.status, 401);
  assert.equal((await response.json()).error.code, "unauthorized");
});

test("maps Cypher to its native protocol and wraps the result", async () => {
  let captured: { url: string; init?: RequestInit } | undefined;
  const handler = createHandler(async (input, init) => {
    captured = { url: String(input), init };
    return Response.json({ results: [{ columns: ["n.name"], data: [{ row: ["Ada"] }] }], errors: [] });
  });
  const response = await handler(new Request(endpoint, {
    method: "POST",
    headers: { authorization: "Bearer test", "content-type": "application/json", "x-request-id": "req-1" },
    body: JSON.stringify({ language: "cypher", query: "MATCH (n:users) RETURN n.name", parameters: { role: "admin" } }),
  }));
  const result = await response.json();
  assert.equal(response.status, 200);
  assert.equal(captured?.url, "https://cypher.kotobase.net/db/data/transaction/commit");
  assert.equal(new Headers(captured?.init?.headers).get("authorization"), "Bearer test");
  assert.deepEqual(JSON.parse(String(captured?.init?.body)), {
    statements: [{ statement: "MATCH (n:users) RETURN n.name", parameters: { role: "admin" } }],
  });
  assert.equal(result.meta.requestId, "req-1");
  assert.equal(result.meta.engine, "org-opencypher-cypher");
});

test("maps Datalog to the tenant-scoped apex query", async () => {
  let body: Record<string, unknown> | undefined;
  const handler = createHandler(async (_input, init) => {
    body = JSON.parse(String(init?.body));
    return Response.json({ graph: "bafygraph", rows_edn: [["\"Ada\""]], basis_t: "bafybasis" });
  });
  const response = await handler(new Request(endpoint, {
    method: "POST",
    headers: { authorization: "Bearer test", "content-type": "application/json" },
    body: JSON.stringify({
      language: "datalog",
      database: "people",
      query: "{:find [?n] :where [[?e :person/name ?n]]}",
      options: { limit: 10, emitCid: true },
    }),
  }));
  const result = await response.json();
  assert.equal(response.status, 200);
  assert.equal(body?.db_name, "people");
  assert.equal(body?.limit, 10);
  assert.equal(result.meta.basisT, "bafybasis");
});

test("returns an explicit unavailable error on DNS or transport failure", async () => {
  const handler = createHandler(async () => { throw new TypeError("DNS failure"); });
  const response = await handler(new Request(endpoint, {
    method: "POST",
    headers: { authorization: "Bearer test", "content-type": "application/json" },
    body: JSON.stringify({ language: "graphql", query: "{ users { name } }" }),
  }));
  const result = await response.json();
  assert.equal(response.status, 503);
  assert.equal(result.error.code, "engine_unavailable");
  assert.equal(result.error.retryable, true);
});

test("does not expose a query engine 5xx response body", async () => {
  const handler = createHandler(async () => Response.json(
    { error: { message: "internal credential and object-key details" } },
    { status: 500 },
  ));
  const response = await handler(new Request(endpoint, {
    method: "POST",
    headers: { authorization: "Bearer test", "content-type": "application/json" },
    body: JSON.stringify({ language: "sparql", query: "SELECT * WHERE { ?s ?p ?o }" }),
  }));
  const result = await response.json();
  assert.equal(response.status, 503);
  assert.equal(result.error.message, "sparql query engine is unavailable");
  assert.doesNotMatch(JSON.stringify(result), /credential|object-key/);
});

test("GraphDB language uses the SPARQL engine and records repository compatibility", async () => {
  let captured: { url: string; body: string } | undefined;
  const handler = createHandler(async (input, init) => {
    captured = { url: String(input), body: String(init?.body) };
    return Response.json({ head: { vars: ["s"] }, results: { bindings: [] } });
  });
  const response = await handler(new Request(endpoint, {
    method: "POST",
    headers: { authorization: "Bearer test", "content-type": "application/json" },
    body: JSON.stringify({
      language: "graphdb",
      database: "default",
      query: "SELECT ?s WHERE { ?s ?p ?o }",
    }),
  }));
  const result = await response.json();
  assert.equal(response.status, 200);
  assert.equal(captured?.url, "https://sparql.kotobase.net/sparql");
  assert.equal(captured?.body, "SELECT ?s WHERE { ?s ?p ?o }");
  assert.equal(result.language, "graphdb");
  assert.equal(result.meta.repository, "default");
  assert.equal(result.meta.protocol, "rdf4j-rest-query-subset");
});

test("GraphDB rejects repositories that are not mounted", async () => {
  const handler = createHandler(async () => { throw new Error("must not dispatch"); });
  const response = await handler(new Request(endpoint, {
    method: "POST",
    headers: { authorization: "Bearer test", "content-type": "application/json" },
    body: JSON.stringify({ language: "graphdb", database: "private", query: "ASK { ?s ?p ?o }" }),
  }));
  assert.equal(response.status, 501);
  assert.equal((await response.json()).error.code, "repository_unavailable");
});

test("native RDF4J repository endpoint accepts form-encoded GraphDB queries", async () => {
  let captured: { url: string; headers: Headers; body: string } | undefined;
  const handler = createHandler(async (input, init) => {
    captured = { url: String(input), headers: new Headers(init?.headers), body: String(init?.body) };
    return Response.json({ head: { vars: ["s"] }, results: { bindings: [] } }, {
      headers: { "content-type": "application/sparql-results+json" },
    });
  });
  const response = await handler(new Request("https://graphdb.kotobase.net/repositories/default", {
    method: "POST",
    headers: {
      authorization: "Bearer test",
      "content-type": "application/x-www-form-urlencoded",
      accept: "application/sparql-results+json",
    },
    body: new URLSearchParams({ query: "SELECT ?s WHERE { ?s ?p ?o }" }),
  }));
  assert.equal(response.status, 200);
  assert.equal(captured?.url, "https://sparql.kotobase.net/sparql");
  assert.equal(captured?.headers.get("authorization"), "Bearer test");
  assert.equal(captured?.body, "SELECT ?s WHERE { ?s ?p ?o }");
  assert.equal(response.headers.get("x-kotobase-repository"), "default");
  assert.equal(response.headers.get("x-kotobase-compatibility"), "graphdb-rdf4j-query-subset");
});

test("native RDF4J repository endpoint accepts GET query parameters", async () => {
  let body = "";
  const handler = createHandler(async (_input, init) => {
    body = String(init?.body);
    return Response.json({ boolean: false });
  });
  const query = encodeURIComponent("ASK { ?s ?p ?o }");
  const response = await handler(new Request(`https://graphdb.kotobase.net/repositories/default?query=${query}`, {
    headers: { authorization: "Bearer test" },
  }));
  assert.equal(response.status, 200);
  assert.equal(body, "ASK { ?s ?p ?o }");
  assert.equal(response.headers.get("access-control-allow-methods"), "GET, POST, OPTIONS");
});

test("native GraphDB compatibility surface is read-only", async () => {
  const handler = createHandler();
  const response = await handler(new Request("https://graphdb.kotobase.net/repositories/default/statements", {
    method: "POST",
    headers: { authorization: "Bearer test", "content-type": "application/sparql-update" },
    body: "INSERT DATA { <a> <b> <c> }",
  }));
  assert.equal(response.status, 404);
});

test("native GraphDB upstream authentication errors use the stable JSON envelope", async () => {
  const handler = createHandler(async () => new Response("upstream implementation details", { status: 401 }));
  const response = await handler(new Request("https://graphdb.kotobase.net/repositories/default", {
    method: "POST",
    headers: { authorization: "Bearer invalid", "content-type": "application/sparql-query" },
    body: "ASK { ?s ?p ?o }",
  }));
  const result = await response.json();
  assert.equal(response.status, 401);
  assert.equal(result.error.code, "unauthorized");
  assert.doesNotMatch(JSON.stringify(result), /implementation details/);
});

test("CORS preflight is handled on the exact route", async () => {
  const handler = createHandler();
  const response = await handler(new Request(endpoint, { method: "OPTIONS" }));
  assert.equal(response.status, 204);
  assert.equal(response.headers.get("access-control-allow-methods"), "GET, POST, OPTIONS");
});
