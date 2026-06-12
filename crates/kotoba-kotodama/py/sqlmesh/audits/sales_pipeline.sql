-- SQLMesh audit: mv_open_sales_pipeline_health invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_sales_pipeline_weighted_le_total,
  model dev.mv_open_sales_pipeline_health,
  dialect postgres,
  description 'weighted_usd must not exceed total_pipeline_usd (probability_pct ≤ 100).'
);
SELECT *
FROM dev.mv_open_sales_pipeline_health
WHERE weighted_usd > total_pipeline_usd + 0.01;

---

AUDIT (
  name assert_sales_pipeline_probability_bounded,
  model dev.mv_open_sales_pipeline_health,
  dialect postgres,
  description 'avg_probability_pct must be in [0, 100].'
);
SELECT *
FROM dev.mv_open_sales_pipeline_health
WHERE avg_probability_pct < 0 OR avg_probability_pct > 100;
