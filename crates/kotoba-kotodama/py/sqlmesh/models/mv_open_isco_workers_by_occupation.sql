-- Open ISCO workers by occupation: confirmed ISCO classifications per code and level.
MODEL (
  name dev.mv_open_isco_workers_by_occupation,
  kind FULL,
  dialect postgres,
  description 'Per (isco_code, code_level): worker count, avg confidence/years, latest classified.',
  grain [isco_code, code_level],
  tags [open_isco, worker, occupation]
);

SELECT
  isco_code,
  code_level,
  COUNT(*) AS worker_count,
  AVG(confidence) AS avg_confidence,
  AVG(years_experience) AS avg_years_experience,
  MAX(classified_at) AS latest_classified_at
FROM vertex_open_isco_classification
WHERE status = 'confirmed'
GROUP BY isco_code, code_level
