-- Vertex natural person count: per-(label, vital, country, era, source) person count.
MODEL (
  name dev.mv_vertex_natural_person_count,
  kind FULL,
  dialect postgres,
  description 'Per (label, vital_status, country, era, source_app): natural person count.',
  grain [label, vital_status, country, era, source_app],
  tags [natural_person, count, rollup]
);

SELECT
  COALESCE(label, '') AS label,
  COALESCE(vital_status, '') AS vital_status,
  COALESCE(country, '') AS country,
  COALESCE(era, '') AS era,
  COALESCE(source_app, '') AS source_app,
  COUNT(*)::BIGINT AS cnt
FROM vertex_natural_person
GROUP BY 1, 2, 3, 4, 5
