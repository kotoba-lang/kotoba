-- Iryo admission count by department: per-(hospital, dept, date) admission counts by type.
MODEL (
  name dev.mv_iryo_admission_count_by_dept,
  kind FULL,
  dialect postgres,
  description 'Per (hospital_slug, dept_slug, created_date): admit count split by emergency/elective/transfer.',
  grain [hospital_slug, dept_slug, created_date],
  tags [iryo, admission, dept]
);

SELECT
  hospital_slug,
  dept_slug,
  created_date,
  COUNT(*) AS admit_count,
  SUM(CASE WHEN admission_type = 'emergency' THEN 1 ELSE 0 END) AS emergency_count,
  SUM(CASE WHEN admission_type = 'elective' THEN 1 ELSE 0 END) AS elective_count,
  SUM(CASE WHEN admission_type = 'transfer' THEN 1 ELSE 0 END) AS transfer_count
FROM vertex_iryo_encounter
GROUP BY hospital_slug, dept_slug, created_date
