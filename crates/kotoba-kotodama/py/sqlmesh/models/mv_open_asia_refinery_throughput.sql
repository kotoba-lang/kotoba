-- Open Asia refinery throughput: received receipt aggregates per refinery and crude grade.
MODEL (
  name dev.mv_open_asia_refinery_throughput,
  kind FULL,
  dialect postgres,
  description 'Per (refinery_code, country, crude_grade): receipt count, total tonnes, and latest discharge.',
  grain [refinery_code, country, crude_grade],
  tags [open_asia, refinery, throughput]
);

SELECT
  refinery_code,
  country,
  crude_grade,
  COUNT(*) AS receipt_count,
  SUM(volume_tonnes) AS total_tonnes,
  MAX(discharged_at) AS latest_discharge
FROM vertex_open_asia_refinery_receipt
WHERE status = 'received'
GROUP BY refinery_code, country, crude_grade
