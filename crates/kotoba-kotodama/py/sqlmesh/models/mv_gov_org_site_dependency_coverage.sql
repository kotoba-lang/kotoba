-- Gov org site dependency coverage: dependency and site counts per owner.
MODEL (
  name dev.mv_gov_org_site_dependency_coverage,
  kind FULL,
  dialect postgres,
  description 'Per owner_did: dependency count, org count, site count, and latest indexed_at.',
  grain [owner_did],
  tags [gov, org, site, dependency, coverage]
);

SELECT
  owner_did,
  COUNT(*) AS dependency_count,
  COUNT(DISTINCT path) AS org_count,
  COUNT(DISTINCT site_did) AS site_count,
  MAX(indexed_at) AS latest_indexed_at
FROM edge_gov_org_site_dependency
GROUP BY owner_did
