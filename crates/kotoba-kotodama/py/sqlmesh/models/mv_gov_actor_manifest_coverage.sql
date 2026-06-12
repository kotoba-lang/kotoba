-- Gov actor manifest coverage: actor counts per owner and country.
MODEL (
  name dev.mv_gov_actor_manifest_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (owner_did, country): actor count and latest indexed_at from vertex_gov_actor_manifest.',
  grain [owner_did, country],
  tags [gov, actor, manifest, coverage]
);

SELECT
  owner_did,
  country,
  COUNT(*) AS actor_count,
  MAX(indexed_at) AS latest_indexed_at
FROM vertex_gov_actor_manifest
GROUP BY owner_did, country
