-- Per root actor DID: descendant follower/following/subdid counts + repo record count.
MODEL (
  name dev.mv_actor_repo_stats,
  kind FULL,
  dialect postgres,
  description 'Per did:web root actor: descendant follow, subdid, and repo record counts via split_part normalization.',
  grain [actor_did],
  tags [actor, did, stats, social, repo]
);

WITH roots AS (
  SELECT DISTINCT
    split_part(val, ':', 1) || ':' || split_part(val, ':', 2) || ':' || split_part(val, ':', 3) AS actor_did
  FROM (
    SELECT did AS val FROM vertex_did WHERE did LIKE 'did:web:%'
    UNION
    SELECT repo AS val FROM vertex_did WHERE repo LIKE 'did:web:%'
    UNION
    SELECT repo AS val FROM vertex_repo_record WHERE repo LIKE 'did:web:%'
    UNION
    SELECT repo AS val FROM edge_follows WHERE repo LIKE 'did:web:%'
    UNION
    SELECT dst_vid AS val FROM edge_follows WHERE dst_vid LIKE 'did:web:%'
  ) s
),
follower_desc AS (
  SELECT
    split_part(dst_vid, ':', 1) || ':' || split_part(dst_vid, ':', 2) || ':' || split_part(dst_vid, ':', 3) AS actor_did,
    COUNT(*)::bigint AS descendant_follower_count
  FROM edge_follows
  WHERE dst_vid LIKE 'did:web:%:%'
  GROUP BY 1
),
following_desc AS (
  SELECT
    split_part(repo, ':', 1) || ':' || split_part(repo, ':', 2) || ':' || split_part(repo, ':', 3) AS actor_did,
    COUNT(*)::bigint AS descendant_following_count
  FROM edge_follows
  WHERE repo LIKE 'did:web:%:%'
  GROUP BY 1
),
subdid_desc AS (
  SELECT
    split_part(did, ':', 1) || ':' || split_part(did, ':', 2) || ':' || split_part(did, ':', 3) AS actor_did,
    COUNT(*)::bigint AS descendant_subdid_count
  FROM vertex_did
  WHERE did LIKE 'did:web:%:%'
  GROUP BY 1
),
repo_rec AS (
  SELECT
    split_part(repo, ':', 1) || ':' || split_part(repo, ':', 2) || ':' || split_part(repo, ':', 3) AS actor_did,
    COUNT(*)::bigint AS repo_record_count
  FROM vertex_repo_record
  WHERE repo LIKE 'did:web:%'
  GROUP BY 1
)
SELECT
  r.actor_did,
  COALESCE(fd.descendant_follower_count,  0) AS descendant_follower_count,
  COALESCE(fo.descendant_following_count, 0) AS descendant_following_count,
  COALESCE(sd.descendant_subdid_count,    0) AS descendant_subdid_count,
  COALESCE(rr.repo_record_count,          0) AS repo_record_count
FROM roots r
LEFT JOIN follower_desc  fd ON fd.actor_did = r.actor_did
LEFT JOIN following_desc fo ON fo.actor_did = r.actor_did
LEFT JOIN subdid_desc    sd ON sd.actor_did = r.actor_did
LEFT JOIN repo_rec       rr ON rr.actor_did = r.actor_did
