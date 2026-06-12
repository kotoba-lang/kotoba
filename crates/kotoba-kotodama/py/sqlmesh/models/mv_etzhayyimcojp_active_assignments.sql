-- Etzhayyimcojp active assignments: active person-role-project assignments with display metadata.
MODEL (
  name dev.mv_etzhayyimcojp_active_assignments,
  kind FULL,
  dialect postgres,
  description 'Active personnel assignments joined with person and role display info.',
  grain [person_did, role_id, project_id],
  tags [etzhayyimcojp, personnel, assignment, active]
);

SELECT
  a.person_did,
  a.role_id,
  a.project_id,
  a.project_name,
  a.allocation_pct,
  a.start_date,
  a.end_date,
  p.display_name,
  p.display_name_ja,
  p.department,
  p.title,
  p.title_ja,
  r.role_name,
  r.role_name_ja,
  r.is_leadership
FROM vertex_etzhayyimcojp_assignment a
LEFT JOIN vertex_etzhayyimcojp_person p ON p.person_did = a.person_did
LEFT JOIN vertex_etzhayyimcojp_role r ON r.role_id = a.role_id
WHERE a.status = 'active'
