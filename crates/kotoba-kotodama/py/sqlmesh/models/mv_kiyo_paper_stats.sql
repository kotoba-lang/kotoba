-- Kiyo paper stats: per-paper citation, review, endorsement, and revision counts.
MODEL (
  name dev.mv_kiyo_paper_stats,
  kind FULL,
  dialect postgres,
  description 'Per (paper_id, vertex_id): inbound citations, reviews, endorsements, and max revision.',
  grain [paper_id],
  tags [kiyo, paper, stats]
);

SELECT
  p.paper_id,
  p.vertex_id,
  COUNT(DISTINCT c.edge_id) AS citation_in_count,
  COUNT(DISTINCT r.vertex_id) AS review_count,
  COUNT(DISTINCT e.edge_id) AS endorsement_count,
  MAX(v.version) AS revision_count
FROM vertex_kiyo_paper p
LEFT JOIN edge_kiyo_cites c ON c.dst_vid = p.vertex_id
LEFT JOIN vertex_kiyo_review r ON r.paper_id = p.paper_id
LEFT JOIN edge_kiyo_endorses e ON e.dst_vid = p.vertex_id
LEFT JOIN vertex_kiyo_revision v ON v.paper_id = p.paper_id
GROUP BY p.paper_id, p.vertex_id
