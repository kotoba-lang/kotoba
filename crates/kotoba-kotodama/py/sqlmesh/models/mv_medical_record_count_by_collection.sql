-- Medical record count by collection: record counts per collection and category.
MODEL (
  name dev.mv_medical_record_count_by_collection,
  kind FULL,
  dialect postgres,
  description 'Per (collection, category): record count and latest ingested_at from vertex_medical.',
  grain [collection, category],
  tags [medical, record, collection]
);

SELECT
  collection,
  category,
  COUNT(*)::BIGINT AS record_count,
  MAX(ingested_at) AS latest_ingested_at
FROM vertex_medical
WHERE collection IS NOT NULL AND collection <> ''
GROUP BY collection, category
