-- Iryo staff coverage gap: per-shift required vs rostered staff gap.
MODEL (
  name dev.mv_iryo_staff_coverage_gap,
  kind FULL,
  dialect postgres,
  description 'Per (hospital, dept, ward, shift_date, shift_block, role): required vs rostered count and gap.',
  grain [hospital_slug, dept_slug, ward_slug, shift_date, shift_block, role],
  tags [iryo, staff, coverage, shift]
);

SELECT
  hospital_slug,
  dept_slug,
  ward_slug,
  shift_date,
  shift_block,
  role,
  SUM(required_count) AS required_total,
  SUM(rostered_count) AS rostered_total,
  SUM(required_count) - SUM(rostered_count) AS gap
FROM vertex_iryo_staff_shift
WHERE status = 'active'
GROUP BY hospital_slug, dept_slug, ward_slug, shift_date, shift_block, role
