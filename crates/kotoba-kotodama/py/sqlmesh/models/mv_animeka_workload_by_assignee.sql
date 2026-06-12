-- Animeka workload per assignee DID and production stage from edge_assigned_to.
MODEL (
  name dev.mv_animeka_workload_by_assignee,
  kind FULL,
  dialect postgres,
  description 'Count of assignments per assignee_did and stage from edge_assigned_to.',
  grain [assignee_did, stage],
  tags [animeka, workload, assignee, stage]
);

SELECT
  COALESCE(assignee_did, '') AS assignee_did,
  COALESCE(stage, '') AS stage,
  COUNT(*)::BIGINT AS cnt
FROM edge_assigned_to
GROUP BY 1, 2
