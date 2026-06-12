-- Telecom KPI breach rate: per-(node, metric) sample and breach counts.
MODEL (
  name dev.mv_telecom_kpi_breach_rate,
  kind FULL,
  dialect postgres,
  description 'Per (node_vid, metric): sample count and breach count from vertex_telecom_kpi_sample.',
  grain [node_vid, metric],
  tags [telecom, kpi, breach]
);

SELECT
  node_vid,
  metric,
  COUNT(*) AS sample_count,
  COUNT(*) FILTER (WHERE breach) AS breach_count
FROM vertex_telecom_kpi_sample
GROUP BY node_vid, metric
