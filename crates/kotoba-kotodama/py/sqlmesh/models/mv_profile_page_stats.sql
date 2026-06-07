-- Profile page stats: social, page, governance, and tool counts per canonical actor DID.
MODEL (
  name dev.mv_profile_page_stats,
  kind FULL,
  dialect postgres,
  description 'Per canonical actor DID: follower/following/post/page/governance/tool counts.',
  grain [actor_did],
  tags [profile, social, page, governance, tools]
);

WITH social_counts AS (
  SELECT
    CASE
      WHEN actor_did LIKE 'did:web:%' THEN regexp_replace(actor_did, '^(did:web:[^:]+).*$', '$1')
      ELSE actor_did
    END AS canonical_actor_did,
    MAX(follower_count)::BIGINT AS follower_count,
    MAX(following_count)::BIGINT AS following_count,
    MAX(post_count)::BIGINT AS post_count
  FROM mv_actor_social_stats
  GROUP BY 1
),
page_counts AS (
  SELECT
    CASE
      WHEN owner_did LIKE 'did:web:%' THEN regexp_replace(owner_did, '^(did:web:[^:]+).*$', '$1')
      ELSE owner_did
    END AS canonical_actor_did,
    COUNT(*)::BIGINT AS page_count
  FROM vertex_page
  WHERE owner_did IS NOT NULL AND owner_did <> ''
  GROUP BY 1
),
governance_counts AS (
  SELECT
    CASE
      WHEN actor_did LIKE 'did:web:%' THEN regexp_replace(actor_did, '^(did:web:[^:]+).*$', '$1')
      ELSE actor_did
    END AS canonical_actor_did,
    COUNT(DISTINCT policy_vid)::BIGINT AS governance_count
  FROM mv_actor_governance_policy
  GROUP BY 1
),
tool_counts AS (
  SELECT
    CASE
      WHEN actor_did LIKE 'did:web:%' THEN regexp_replace(actor_did, '^(did:web:[^:]+).*$', '$1')
      ELSE actor_did
    END AS canonical_actor_did,
    COUNT(DISTINCT tool_name)::BIGINT AS tool_count
  FROM mv_actor_tool_grants
  GROUP BY 1
),
canonical_keys AS (
  SELECT canonical_actor_did FROM social_counts
  UNION SELECT canonical_actor_did FROM page_counts
  UNION SELECT canonical_actor_did FROM governance_counts
  UNION SELECT canonical_actor_did FROM tool_counts
)
SELECT
  k.canonical_actor_did AS actor_did,
  k.canonical_actor_did AS canonical_actor_did,
  COALESCE(sc.follower_count, 0) AS follower_count,
  COALESCE(sc.following_count, 0) AS following_count,
  COALESCE(sc.post_count, 0) AS post_count,
  COALESCE(pg.page_count, 0) AS page_count,
  COALESCE(g.governance_count, 0) AS governance_count,
  COALESCE(t.tool_count, 0) AS tool_count
FROM canonical_keys k
LEFT JOIN social_counts sc ON sc.canonical_actor_did = k.canonical_actor_did
LEFT JOIN page_counts pg ON pg.canonical_actor_did = k.canonical_actor_did
LEFT JOIN governance_counts g ON g.canonical_actor_did = k.canonical_actor_did
LEFT JOIN tool_counts t ON t.canonical_actor_did = k.canonical_actor_did
