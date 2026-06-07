-- Vertex security count: per-(source, severity) security record count.
MODEL (
  name dev.mv_vertex_security_count,
  kind FULL,
  dialect postgres,
  description 'Per (source, severity): security record count from vertex_security.',
  grain [source, severity],
  tags [security, count, severity]
);

SELECT
  COALESCE(source, '') AS source,
  COALESCE(severity, '') AS severity,
  COUNT(*)::BIGINT AS cnt
FROM vertex_security
GROUP BY 1, 2
