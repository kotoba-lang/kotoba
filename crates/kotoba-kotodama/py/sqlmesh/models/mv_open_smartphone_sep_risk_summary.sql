-- Open smartphone SEP risk summary: per (RAT, standard) SEP / FRAND / pool / blocker aggregates.
MODEL (
  name dev.mv_open_smartphone_sep_risk_summary,
  kind FULL,
  dialect postgres,
  description 'Per (rat, standard): SEP totals, FRAND/pooled counts, expiring 24m, blockers, pool fee range.',
  grain [rat, standard],
  tags [open_smartphone, sep, risk, frand]
);

SELECT
  ps.rat,
  ps.standard,
  COUNT(ps.vertex_id) AS total_seps,
  SUM(CASE WHEN ps.frand_declared THEN 1 ELSE 0 END) AS frand_count,
  SUM(CASE WHEN ps.pool_id IS NOT NULL THEN 1 ELSE 0 END) AS pooled_count,
  SUM(CASE WHEN ps.expiry_date IS NOT NULL
            AND ps.expiry_date < '2028-04-28'
           THEN 1 ELSE 0 END) AS expiring_24m,
  SUM(CASE WHEN ms.blocker_status = 'active' THEN 1 ELSE 0 END) AS active_blockers,
  COUNT(DISTINCT pp.pool_id) AS pool_count,
  MIN(pp.license_fee_usd_per_unit) AS min_pool_fee_usd,
  MAX(pp.license_fee_usd_per_unit) AS max_pool_fee_usd
FROM vertex_open_smartphone_patent_sep ps
LEFT JOIN vertex_open_smartphone_modem_sep_dep ms ON ms.patent_no = ps.patent_no
LEFT JOIN vertex_open_smartphone_patent_pool pp ON pp.pool_id = ps.pool_id
GROUP BY ps.rat, ps.standard
