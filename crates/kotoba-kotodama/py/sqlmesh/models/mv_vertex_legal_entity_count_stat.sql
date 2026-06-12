-- Vertex legal entity count stat: legal entity counts per metric (total/country/source).
MODEL (
  name dev.mv_vertex_legal_entity_count_stat,
  kind FULL,
  dialect postgres,
  description 'Per (metric=total|country|source, key): legal entity count from vertex_legal_entity.',
  grain [metric, key],
  tags [legal_entity, count, stat]
);

SELECT 'total'::VARCHAR AS metric, ''::VARCHAR AS key, COUNT(*)::BIGINT AS cnt
FROM vertex_legal_entity
UNION ALL
SELECT 'country'::VARCHAR AS metric, COALESCE(country, '') AS key, COUNT(*)::BIGINT AS cnt
FROM vertex_legal_entity
GROUP BY COALESCE(country, '')
UNION ALL
SELECT 'source'::VARCHAR AS metric, COALESCE(source, '') AS key, COUNT(*)::BIGINT AS cnt
FROM vertex_legal_entity
GROUP BY COALESCE(source, '')
