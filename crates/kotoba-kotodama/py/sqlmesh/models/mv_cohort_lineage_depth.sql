-- Cohort lineage depth: direct children count and last fission timestamp per cohort.
MODEL (
  name dev.mv_cohort_lineage_depth,
  kind FULL,
  dialect postgres,
  description 'Per-cohort direct child count and last fission timestamp from edge_cohort_derived.',
  grain [cohort_did],
  tags [cohort, lineage, depth, fission, children]
);

SELECT
  src_vid AS cohort_did,
  COUNT(*)::BIGINT AS direct_children,
  MAX(fission_at) AS last_fission_at
FROM edge_cohort_derived
GROUP BY src_vid
