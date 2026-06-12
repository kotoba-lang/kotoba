-- Mangaka members by project: membership edge count per project.
MODEL (
  name dev.mv_mangaka_members_by_project,
  kind FULL,
  dialect postgres,
  description 'Per project_vid: count of membership edges from edge_membership.',
  grain [project_vid],
  tags [mangaka, project, membership]
);

SELECT
  src_vid AS project_vid,
  COUNT(*)::BIGINT AS cnt
FROM edge_membership
GROUP BY src_vid
