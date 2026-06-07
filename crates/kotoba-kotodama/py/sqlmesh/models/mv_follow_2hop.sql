-- Follow 2-hop: mutual follow suggestions via 2-hop graph traversal.
MODEL (
  name dev.mv_follow_2hop,
  kind FULL,
  dialect postgres,
  description 'Per (actor, suggestion): mutual follow count via 2-hop path through edge_follows.',
  grain [actor, suggestion],
  tags [follow, graph, suggestion, social]
);

SELECT
  f1.src_vid AS actor,
  f2.dst_vid AS suggestion,
  COUNT(*) AS mutual_count
FROM edge_follows f1
JOIN edge_follows f2 ON f1.dst_vid = f2.src_vid
WHERE f1.src_vid != f2.dst_vid
GROUP BY f1.src_vid, f2.dst_vid
