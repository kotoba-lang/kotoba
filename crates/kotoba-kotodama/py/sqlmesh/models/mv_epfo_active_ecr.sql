-- EPFO active ECR: submitted and amended electronic challan returns.
MODEL (
  name dev.mv_epfo_active_ecr,
  kind FULL,
  dialect postgres,
  description 'Active EPFO ECR filings with status submitted or amended.',
  grain [vertex_id],
  tags [epfo, ecr, india, compliance]
);

SELECT
  employer_org_id,
  establishment_pf_code,
  wage_month,
  vertex_id,
  status,
  total_members,
  total_wage_inr_paise,
  total_employer_pf_inr_paise,
  total_employee_pf_inr_paise,
  total_eps_inr_paise,
  trrn,
  approved_at
FROM vertex_epfo_ecr
WHERE status IN ('submitted', 'amended')
