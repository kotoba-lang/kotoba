-- Mutual follows: actor pairs that follow each other in both directions.
MODEL (
  name dev.mv_mutual_follows,
  kind FULL,
  dialect postgres,
  description 'Per (actor_a, actor_b): pairs from edge_follows where both directions exist.',
  grain [actor_a, actor_b],
  tags [social, follow, mutual]
);

SELECT
  a.src_vid AS actor_a,
  a.dst_vid AS actor_b
FROM edge_follows a
JOIN edge_follows b ON a.src_vid = b.dst_vid AND a.dst_vid = b.src_vid
