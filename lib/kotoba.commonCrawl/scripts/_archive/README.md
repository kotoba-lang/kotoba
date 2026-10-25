# _archive

One-shot operational scripts retained for provenance.

- `phase3k_s3_connector_swap.sql` — executed 2026-04-16 during the CC bulk
  ingest that populated `vertex_page` (985M), `edge_links_to` (4.6B), and
  `edge_links_to_domain` (2.3B). SWAP is complete; the script is not part
  of any runbook. Kept so the exact SQL that landed live tables is
  auditable. See `30-graph/graph-schema/AGENTS.md` §"Cluster state" for
  current live row counts.
