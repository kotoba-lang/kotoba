-- Open ORCID by country: active researcher count per country and verification level.
MODEL (
  name dev.mv_open_orcid_by_country,
  kind FULL,
  dialect postgres,
  description 'Per (country, verification): active researcher count and latest registered timestamp.',
  grain [country, verification],
  tags [open_orcid, researcher, country, verification]
);

SELECT
  country,
  verification,
  COUNT(*) AS researcher_count,
  MAX(registered_at) AS latest_registered_at
FROM vertex_open_orcid_researcher
WHERE status = 'active'
GROUP BY country, verification
