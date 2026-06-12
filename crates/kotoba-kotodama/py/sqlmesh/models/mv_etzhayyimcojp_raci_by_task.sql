-- Etzhayyimcojp RACI by task: active RACI assignments grouped by task and role.
MODEL (
  name dev.mv_etzhayyimcojp_raci_by_task,
  kind FULL,
  dialect postgres,
  description 'Per (task_nsid, task_name, domain, raci_role): person count and aggregated names.',
  grain [task_nsid, raci_role],
  tags [etzhayyimcojp, raci, task]
);

SELECT
  r.task_nsid,
  r.task_name,
  r.domain,
  r.raci_role,
  COUNT(*) AS person_count,
  STRING_AGG(p.display_name, ', ') AS persons
FROM vertex_etzhayyimcojp_raci r
LEFT JOIN vertex_etzhayyimcojp_person p ON p.person_did = r.person_did
WHERE r.status = 'active'
GROUP BY r.task_nsid, r.task_name, r.domain, r.raci_role
