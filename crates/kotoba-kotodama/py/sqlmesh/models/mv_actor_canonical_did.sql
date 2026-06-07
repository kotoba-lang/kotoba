-- Actor canonical DID lookup via normalize_actor_did() SQL UDF.
-- Unions social_stats, governance_policy, and tool_grants sources.
MODEL (
  name dev.mv_actor_canonical_did,
  kind FULL,
  dialect postgres,
  description 'Distinct raw_did → canonical_did mapping using normalize_actor_did() UDF.',
  grain [raw_did],
  tags [actor, identity, canonical_did]
);

SELECT DISTINCT
  raw_did,
  normalize_actor_did(raw_did) AS canonical_did
FROM (
  SELECT actor_did AS raw_did FROM mv_actor_social_stats
  UNION ALL
  SELECT actor_did AS raw_did FROM mv_actor_governance_policy
  UNION ALL
  SELECT actor_did AS raw_did FROM mv_actor_tool_grants
) s
