#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

if ! command -v cypher-shell >/dev/null 2>&1; then
  echo "cypher-shell not found. Install Neo4j client and retry." >&2
  exit 1
fi

: "${NEO4J_URI:=bolt://localhost:7687}"
: "${NEO4J_USER:=neo4j}"
: "${NEO4J_PASSWORD:?Set NEO4J_PASSWORD}"

echo "[1/2] Ingesting run-level signoff graph ..."
cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  --param-file "$ROOT_DIR/data/runs.json" \
  -f "$ROOT_DIR/neo4j_bulk_ingest.cypher"

echo "[2/2] Ingesting domain coverage graph ..."
cypher-shell -a "$NEO4J_URI" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  --param-file "$ROOT_DIR/data/entries_semiconductor.json" \
  -f "$ROOT_DIR/neo4j_domain_coverage.cypher"

echo "Done"
