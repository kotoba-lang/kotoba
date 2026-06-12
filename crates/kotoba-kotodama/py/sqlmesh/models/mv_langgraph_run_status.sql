-- SQLMesh model: mv_langgraph_run_status
-- Run-status aggregates for LangGraph Server /runs API (ADR-2605080600 Phase 2).
--
-- Source of truth for the deployed RisingWave streaming MV.
-- Apply via: rw-health-gate.sh gate + psql DDL channel.
--
-- Lineage:
--   vertex_langgraph_run
--   → mv_langgraph_run_status

MODEL (
  name dev.mv_langgraph_run_status,
  kind FULL,
  dialect postgres,
  description 'Per-assistant run counts by status. Drives /readyz graph health and soak monitoring.',
  grain [assistant_id, status],
  tags [langgraph, l3_runtime, adr_2605080600, materialized_view]
);

SELECT
  assistant_id,
  status,
  COUNT(*)                                                      AS run_count,
  MIN(created_at)                                               AS oldest_created_at,
  MAX(created_at)                                               AS newest_created_at,
  SUM(CASE WHEN completed_at IS NOT NULL
           THEN completed_at - started_at ELSE NULL END)        AS total_latency_ms,
  COUNT(CASE WHEN completed_at IS NOT NULL
             AND started_at IS NOT NULL THEN 1 END)             AS completed_with_latency
FROM vertex_langgraph_run
GROUP BY assistant_id, status
