-- Sashiosae stats by type: case counts per (case_type, authority, period, amount, status).
MODEL (
  name dev.mv_sashiosae_stats_by_type,
  kind FULL,
  dialect postgres,
  description 'Per (case_type, authority_did, period_ym, amount_bucket, status): JPN seizure case count.',
  grain [case_type, authority_did, period_ym, amount_bucket, status],
  tags [sashiosae, jpn, seizure, stats]
);

SELECT
  case_type,
  authority_did,
  period_ym,
  amount_bucket,
  status,
  COUNT(*) AS case_count
FROM vertex_atrecord_sashiosae_choushuu_case
GROUP BY case_type, authority_did, period_ym, amount_bucket, status
