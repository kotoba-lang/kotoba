-- Kuruma supply chain depth: part and supplier counts per vehicle model.
MODEL (
  name dev.mv_kuruma_supply_chain_depth,
  kind FULL,
  dialect postgres,
  description 'Per vehicle model: part count, supplier count, and max tier depth.',
  grain [model_did],
  tags [kuruma, supply_chain, parts, suppliers]
);

SELECT
  m.vertex_id AS model_did,
  COUNT(DISTINCT cp.dst_vid) AS part_count,
  COUNT(DISTINCT ps.dst_vid) AS supplier_count,
  COALESCE(MAX(ps.tier), 0) AS max_tier
FROM vertex_kuruma_model m
LEFT JOIN edge_kuruma_contains_part cp ON cp.src_vid = m.vertex_id
LEFT JOIN edge_kuruma_part_supplier ps ON ps.src_vid = cp.dst_vid
GROUP BY m.vertex_id
