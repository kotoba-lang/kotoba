-- Kuruma recall per maker: recall count and total affected units per maker.
MODEL (
  name dev.mv_kuruma_recall_per_maker,
  kind FULL,
  dialect postgres,
  description 'Per maker_did: recall count and total estimated affected units.',
  grain [maker_did],
  tags [kuruma, recall, maker, safety]
);

SELECT
  m.maker_did,
  COUNT(DISTINCT r.vertex_id) AS recall_count,
  SUM(r.affected_units_est)::BIGINT AS total_affected_units
FROM vertex_kuruma_recall r
JOIN edge_kuruma_recall_affects ra ON ra.src_vid = r.vertex_id
JOIN vertex_kuruma_model m ON m.vertex_id = ra.dst_vid
GROUP BY m.maker_did
