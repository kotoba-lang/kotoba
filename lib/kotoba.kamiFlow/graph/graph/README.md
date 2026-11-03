# Kami Flow Graph Ingest

This directory contains graph ingestion assets for `graph.etzhayyim.com` (RisingWave-backed Graph Worker).

## Files
- `neo4j_bulk_ingest.cypher`: original Cypher batch draft
- `neo4j_domain_coverage.cypher`: original domain Cypher draft
- `data/runs.json`: run-level sample payload
- `data/entries_semiconductor.json`: coverage/supply-chain/actor payload (11 tools)
- `run_ingest_graph_worker.mjs`: active ingest script for `graph.etzhayyim.com`

## Active path (`graph.etzhayyim.com`)

```bash
node 40-engine/kami-engine/kami-flow/graph/run_ingest_graph_worker.mjs
```

Optional env overrides:

```bash
GRAPH_BASE='https://graph.etzhayyim.com' \
GRAPH_REPO_DID='did:web:kami.etzhayyim.com' \
GRAPH_COLLECTION='app.etzhayyim.apps.kami.flow.graph' \
RUNS_JSON='40-engine/kami-engine/kami-flow/graph/data/runs.json' \
ENTRIES_JSON='40-engine/kami-engine/kami-flow/graph/data/entries_semiconductor.json' \
node 40-engine/kami-engine/kami-flow/graph/run_ingest_graph_worker.mjs
```

The script:
- checks `/_worker/health`
- writes vertices/edges to `graphar.vertex_kami_flow_node` and `graphar.edge_kami_flow_relation`
- verifies inserted counts by node/relation label

## Direct query example (`statement` SQL)

```bash
curl -sS -X POST https://graph.etzhayyim.com/xrpc/app.etzhayyim.kagami.graph.query \
  -H 'content-type: application/json' \
  --data '{"statement":"SELECT node_label AS label, COUNT(*) AS cnt FROM graphar.vertex_kami_flow_node GROUP BY node_label ORDER BY cnt DESC LIMIT 20"}'
```

## Cypher read example

```bash
curl -sS -X POST https://graph.etzhayyim.com/xrpc/app.etzhayyim.kagami.graph.query \
  -H 'content-type: application/json' \
  --data '{"cypher":"MATCH (n:Coverage) RETURN count(n) AS cnt LIMIT 1"}'
```
