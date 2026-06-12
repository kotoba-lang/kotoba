-- Open SPR by country: published strategic petroleum reserve snapshots per country.
MODEL (
  name dev.mv_open_spr_by_country,
  kind FULL,
  dialect postgres,
  description 'Per country: SPR snapshot count, avg pct full, avg coverage days, latest measured.',
  grain [country],
  tags [open_spr, petroleum, reserve, country]
);

SELECT
  country,
  COUNT(*) AS snapshot_count,
  AVG(pct_full) AS avg_pct_full,
  AVG(coverage_days) AS avg_coverage_days,
  MAX(measured_at) AS latest_measured
FROM vertex_open_spr_level
WHERE status = 'published'
GROUP BY country
