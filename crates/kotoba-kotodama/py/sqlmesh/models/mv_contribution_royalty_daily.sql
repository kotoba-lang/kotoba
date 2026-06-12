-- Daily contribution royalty: earned GCC wei per contributor source hash.
MODEL (
  name dev.mv_contribution_royalty_daily,
  kind FULL,
  dialect postgres,
  description 'Per-contributor daily royalty earned in GCC wei (gcc_value_wei * royalty_bps / 10000).',
  grain [source_hash, contributor_did, distribution_date],
  tags [contribution, royalty, daily, gcc, wei]
);

SELECT
  cs.source_hash,
  cs.contributor_did,
  cs.contributor_addr,
  DATE_TRUNC('day', used_at::TIMESTAMP) AS distribution_date,
  COUNT(*)                               AS usage_count,
  SUM(
    CAST(cu.gcc_value_wei AS DOUBLE PRECISION) * cs.royalty_bps / 10000
  )                                      AS earned_wei
FROM vertex_contribution_usage cu
JOIN vertex_contribution_source cs USING (source_hash)
GROUP BY
  cs.source_hash,
  cs.contributor_did,
  cs.contributor_addr,
  DATE_TRUNC('day', used_at::TIMESTAMP)
