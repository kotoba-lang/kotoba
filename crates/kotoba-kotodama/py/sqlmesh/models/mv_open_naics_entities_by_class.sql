-- Open NAICS entities by class: confirmed classification count per NAICS code and country.
MODEL (
  name dev.mv_open_naics_entities_by_class,
  kind FULL,
  dialect postgres,
  description 'Per (naics_code, country): entity count, avg confidence, latest classified timestamp.',
  grain [naics_code, country],
  tags [open_naics, entity, classification, industry]
);

SELECT
  naics_code,
  country,
  COUNT(*) AS entity_count,
  AVG(confidence) AS avg_confidence,
  MAX(classified_at) AS latest_classified_at
FROM vertex_open_naics_classification
WHERE status = 'confirmed'
GROUP BY naics_code, country
