-- SQLMesh audit: mv_lawfirm_pipeline_funnel invariants.
-- Returns rows that FAIL the audit condition (zero rows = audit passes).

AUDIT (
  name assert_lawfirm_pipeline_lead_count_positive,
  model dev.mv_lawfirm_pipeline_funnel,
  dialect postgres,
  description 'lead_count must be > 0 (group rows imply at least one lead per stage).'
);
SELECT *
FROM dev.mv_lawfirm_pipeline_funnel
WHERE lead_count <= 0;

---

AUDIT (
  name assert_lawfirm_pipeline_value_nonnegative,
  model dev.mv_lawfirm_pipeline_funnel,
  dialect postgres,
  description 'pipeline_value_usd must be >= 0 (COALESCE to 0 for null conversion values).'
);
SELECT *
FROM dev.mv_lawfirm_pipeline_funnel
WHERE pipeline_value_usd < 0;
