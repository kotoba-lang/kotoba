-- Open seiyaku released batches: pharmaceutical batches in released or amended state.
MODEL (
  name dev.mv_open_seiyaku_released_batches,
  kind FULL,
  dialect postgres,
  description 'Per batch (released or amended): manufacturer, plant, product, release/approval timestamps.',
  grain [vertex_id],
  tags [open_seiyaku, batch, released, pharmaceutical]
);

SELECT
  manufacturer_org_id,
  plant_org_id,
  product_code,
  batch_number,
  vertex_id,
  status,
  released_at,
  approved_at
FROM vertex_open_seiyaku_batch
WHERE status IN ('released', 'amended')
