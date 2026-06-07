-- Fuyou active declaration: approved and amended dependent deduction declarations.
MODEL (
  name dev.mv_fuyou_active_declaration,
  kind FULL,
  dialect postgres,
  description 'Active fuyou declarations with status approved or amended.',
  grain [vertex_id],
  tags [fuyou, declaration, japan, tax]
);

SELECT
  employee_did,
  employer_org_id,
  tax_year,
  vertex_id,
  status,
  amendment_count,
  approved_at
FROM vertex_fuyou_declaration
WHERE status IN ('approved', 'amended')
