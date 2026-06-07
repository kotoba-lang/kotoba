-- Wellbecoming report health: aggregate process mining report metrics.
MODEL (
  name dev.mv_wellbecoming_report_health,
  kind FULL,
  dialect postgres,
  description 'Aggregate metrics from vertex_wellbecoming_process_mining_report: counts, scores, latest indexed.',
  grain [],
  tags [wellbecoming, report, health, process_mining]
);

SELECT
  COUNT(*) AS report_count,
  SUM(scored_count) AS scored_count,
  SUM(floor_violations) AS floor_violations,
  AVG(avg_spirit) AS avg_spirit,
  AVG(avg_separation_delta) AS avg_separation_delta,
  MAX(indexed_at) AS latest_indexed_at
FROM vertex_wellbecoming_process_mining_report
