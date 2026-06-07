-- Lawfirm pipeline funnel: lead count and pipeline value per stage.
MODEL (
  name dev.mv_lawfirm_pipeline_funnel,
  kind FULL,
  dialect postgres,
  description 'Per stage: lead count and total conversion_value_usd from vertex_lawfirm_lead.',
  grain [stage],
  tags [lawfirm, pipeline, funnel, sales]
);

SELECT
  stage,
  COUNT(*) AS lead_count,
  COALESCE(SUM(conversion_value_usd), 0) AS pipeline_value_usd
FROM vertex_lawfirm_lead
GROUP BY stage
