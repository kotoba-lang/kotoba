-- Vertex smishing sender blocklist count: per-actor smishing sender blocklist count.
MODEL (
  name dev.mv_vertex_smishing_sender_blocklist_count,
  kind FULL,
  dialect postgres,
  description 'Per actor_id: blocklist sender count from vertex_smishing_sender_blocklist.',
  grain [actor_id],
  tags [smishing, blocklist, count]
);

SELECT
  actor_id,
  COUNT(*)::BIGINT AS cnt
FROM vertex_smishing_sender_blocklist
GROUP BY actor_id
