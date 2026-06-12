-- Hospitality tier coverage: actor counts per tier and kind.
MODEL (
  name dev.mv_hospitality_tier_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (tier, kind): actor count for hospitality actors, tier derived from actor kind.',
  grain [tier, kind],
  tags [hospitality, tier, coverage]
);

SELECT
  CASE split_part(split_part(did, ':actor:', 2), ':', 1)
    WHEN 'hotel' THEN 'accommodation'
    WHEN 'ryokan' THEN 'accommodation'
    WHEN 'restaurant' THEN 'dining'
    WHEN 'cafe' THEN 'dining'
    WHEN 'resort' THEN 'accommodation'
    ELSE 'other'
  END AS tier,
  split_part(split_part(did, ':actor:', 2), ':', 1) AS kind,
  COUNT(*) AS actor_count
FROM vertex_profile
WHERE did LIKE 'did:web:hospitality.etzhayyim.com:actor:%'
GROUP BY tier, kind
