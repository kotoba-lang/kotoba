-- Open ISIC entities by class: confirmed ISIC classifications per class and country.
MODEL (
  name dev.mv_open_isic_entities_by_class,
  kind FULL,
  dialect postgres,
  description 'Per (isic_class_code, country): entity count, avg confidence, latest classified.',
  grain [isic_class_code, country],
  tags [open_isic, entity, class]
);

SELECT
  isic_class_code,
  country,
  COUNT(*) AS entity_count,
  AVG(confidence) AS avg_confidence,
  MAX(classified_at) AS latest_classified_at
FROM vertex_open_isic_classification
WHERE status = 'confirmed'
GROUP BY isic_class_code, country
