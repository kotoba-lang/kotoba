-- JP Ashiba inspection result counts: inspection counts per result and severity.
MODEL (
  name dev.mv_jp_ashiba_inspection_result_counts,
  kind FULL,
  dialect postgres,
  description 'Per (overall_result, severity): inspection count from vertex_jp_ashiba_inspection.',
  grain [overall_result, severity],
  tags [jp_ashiba, inspection, result]
);

SELECT
  overall_result,
  severity,
  COUNT(*) AS cnt
FROM vertex_jp_ashiba_inspection
GROUP BY overall_result, severity
