-- ESIC active contribution: submitted and amended ESI contribution records.
MODEL (
  name dev.mv_esic_active_contribution,
  kind FULL,
  dialect postgres,
  description 'Active ESIC contribution filings with status submitted or amended.',
  grain [vertex_id],
  tags [esic, contribution, india, compliance]
);

SELECT
  employer_org_id,
  establishment_esi_code,
  wage_month,
  vertex_id,
  status,
  total_members,
  total_wage_inr_paise,
  total_employee_contribution_inr_paise,
  total_employer_contribution_inr_paise,
  total_contribution_inr_paise,
  challan_reference,
  approved_at
FROM vertex_esic_contribution
WHERE status IN ('submitted', 'amended')
