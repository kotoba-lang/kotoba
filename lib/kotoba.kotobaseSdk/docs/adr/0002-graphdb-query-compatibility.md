# ADR-0002: GraphDB/RDF4J read-query compatibility

- Status: Accepted
- Date: 2026-08-01

## Context

Ontotext GraphDB exposes an RDF4J REST query endpoint per repository at
`/repositories/{repositoryID}`. Queries are SPARQL; clients can submit them as
a URL query parameter, as `application/x-www-form-urlencoded`, or as
`application/sparql-query`, and select the result representation with
`Accept`.

Kotobase already runs a SPARQL protocol surface. Duplicating SPARQL parsing or
claiming compatibility with GraphDB management, inference, update, and plugin
APIs would be unnecessary and inaccurate.

Primary reference:
[Ontotext GraphDB 11.1 — RDF4J REST API](https://graphdb.ontotext.com/documentation/11.1/rdf4j-rest-api.html).

## Decision

Add two read-only entry points backed by Kotobase's existing SPARQL engine:

1. Unified SDK query language `graphdb`, exposed through
   `query.execute`. Its query document is SPARQL and `database` is the GraphDB
   repository identifier.
2. Native compatibility endpoint
   `https://graphdb.kotobase.net/repositories/default` supporting:
   - `GET ?query=<SPARQL>`
   - `POST application/x-www-form-urlencoded` with `query=<SPARQL>`
   - `POST application/sparql-query` with the query as the body
   - SPARQL Results JSON through `Accept: application/sparql-results+json`

Only the repository `default` is mounted initially. Other repository names
fail explicitly. Both entry points require an existing Kotobase credential.

## Compatibility boundary

This is a GraphDB/RDF4J **query endpoint subset**, not an Ontotext GraphDB
server implementation. It does not implement:

- repository creation, deletion, configuration, backup, or restore;
- `/statements` writes or SPARQL Update;
- GraphDB inference rulesets, sameAs controls, plugins, connectors, cluster, or
  workbench APIs;
- GraphDB-specific query optimizer behavior or extensions not understood by
  Kotobase's SPARQL engine.
- `CONSTRUCT`, `DESCRIBE`, alternate result serializations, and other query
  forms outside the current Kotobase SPARQL `SELECT`/`ASK` subset.

Responses identify the boundary with
`x-kotobase-compatibility: graphdb-rdf4j-query-subset`. The unified envelope
uses engine name `graphdb-rdf4j-query-compatible` and records repository
`default` in result metadata.

## Security

- Reads inherit the caller's Authorization/CACAO identity.
- Updates are not routed to the SPARQL engine.
- Query bodies are capped at 128 KiB and upstream calls at 30 seconds.
- Upstream 5xx bodies are not exposed.
- Repository identifiers are decoded and matched exactly; they are never used
  to construct arbitrary upstream URLs.

## Deployment record

Deployed on 2026-08-01 in Cloudflare Worker
`net-kotobase-query-gateway`, version
`803b2fff-8788-42db-8eed-3da669131e1d`; current verified version after GET/CORS
coverage and stable native error envelopes:
`5e1e9635-315c-4b0f-9494-076e8b664ea6`. The custom domain health endpoint and
both native/unified authentication boundaries were verified in production.
