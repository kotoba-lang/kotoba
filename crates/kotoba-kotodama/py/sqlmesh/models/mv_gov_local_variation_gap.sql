-- Gov local variation gap: municipality gap counts per jurisdiction and gap type.
MODEL (
  name dev.mv_gov_local_variation_gap,
  kind FULL,
  dialect postgres,
  description 'Per (country_iso3, admin1_name, gap_kind, gap_status): municipality count from gap table.',
  grain [country_iso3, admin1_name, gap_kind, gap_status],
  tags [gov, local, variation, gap]
);

SELECT
  country_iso3,
  admin1_name,
  gap_kind,
  gap_status,
  COUNT(*) AS municipality_count
FROM vertex_gov_local_variation_gap
GROUP BY country_iso3, admin1_name, gap_kind, gap_status
