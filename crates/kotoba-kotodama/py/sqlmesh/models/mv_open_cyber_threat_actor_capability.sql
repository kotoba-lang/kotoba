-- Open cyber threat actor capability: tracked threat actor counts per attribution and tier.
MODEL (
  name dev.mv_open_cyber_threat_actor_capability,
  kind FULL,
  dialect postgres,
  description 'Per (attribution, capability_tier, suspected_nexus): tracked actor count and latest observed.',
  grain [attribution, capability_tier, suspected_nexus],
  tags [open_cyber, threat_actor, capability]
);

SELECT
  attribution,
  capability_tier,
  suspected_nexus,
  COUNT(*) AS actor_count,
  MAX(first_observed) AS latest_observed
FROM vertex_open_cyber_threat_actor
WHERE status = 'tracked'
GROUP BY attribution, capability_tier, suspected_nexus
