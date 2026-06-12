-- SQLMesh model: mv_lora_adapter_actor_status
-- Supersedes inline Kysely definition in 20260507512000_lora_adapter_vertex_edge.ts
-- (ADR-2605080500 Phase 0: parallel coexistence until Kysely MV is dropped).
--
-- Apply DDL changes via: rw-health-gate.sh gate + psql DDL channel.
--
-- Lineage:
--   vertex_lora_adapter
--   → mv_lora_adapter_actor_status

MODEL (
  name dev.mv_lora_adapter_actor_status,
  kind FULL,
  dialect postgres,
  description 'Per-actor LoRA adapter count and latest registration timestamp, grouped by status. Drives Ameno adapter selection and training coverage.',
  grain [owner_did, status],
  tags [lora, ameno, ml_serving, materialized_view]
);

SELECT
  owner_did,
  base_model,
  status,
  COUNT(*)                    AS adapter_count,
  MAX(created_at)             AS latest_created_at,
  SUM(weight_byte_size)       AS total_weight_bytes,
  MAX(display_name_yomi)      AS sample_yomi
FROM vertex_lora_adapter
GROUP BY owner_did, base_model, status
