-- Per-actor like + repost engagement from social graph edges.
MODEL (
  name dev.mv_actor_subject_engagement,
  kind FULL,
  dialect postgres,
  description 'Per-actor total like_count and repost_count from edge_likes and edge_reposts.',
  grain [actor_did],
  tags [actor, social, engagement, likes, reposts]
);

WITH actor_keys AS (
  SELECT split_part(subject_uri, '/', 3) AS actor_did
  FROM edge_likes
  WHERE subject_uri LIKE 'at://did:%'
  UNION
  SELECT split_part(subject_uri, '/', 3) AS actor_did
  FROM edge_reposts
  WHERE subject_uri LIKE 'at://did:%'
),
like_counts AS (
  SELECT split_part(subject_uri, '/', 3) AS actor_did, COUNT(*)::bigint AS like_count
  FROM edge_likes
  WHERE subject_uri LIKE 'at://did:%'
  GROUP BY 1
),
repost_counts AS (
  SELECT split_part(subject_uri, '/', 3) AS actor_did, COUNT(*)::bigint AS repost_count
  FROM edge_reposts
  WHERE subject_uri LIKE 'at://did:%'
  GROUP BY 1
)
SELECT
  k.actor_did,
  COALESCE(l.like_count, 0) AS like_count,
  COALESCE(r.repost_count, 0) AS repost_count
FROM actor_keys k
LEFT JOIN like_counts l ON l.actor_did = k.actor_did
LEFT JOIN repost_counts r ON r.actor_did = k.actor_did
