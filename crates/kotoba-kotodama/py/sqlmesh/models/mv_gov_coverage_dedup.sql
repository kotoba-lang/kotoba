-- Gov coverage dedup: entity counts per kind from deduplicated gov records.
MODEL (
  name dev.mv_gov_coverage_dedup,
  kind FULL,
  dialect postgres,
  description 'Per entity_kind: distinct entity count from mv_gov_record_dedup.',
  grain [entity_kind],
  tags [gov, coverage, dedup]
);

SELECT
  entity_kind,
  COUNT(*) AS entity_count,
  SUM(record_count) AS total_records
FROM dev.mv_gov_record_dedup
GROUP BY entity_kind
