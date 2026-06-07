-- Goal progress: action counts by status per goal.
MODEL (
  name dev.mv_goal_progress,
  kind FULL,
  dialect postgres,
  description 'Per goal: action counts (total/done/in_progress/blocked), target value, and attainment bps.',
  grain [vertex_id],
  tags [goal, progress, strategy, action]
);

SELECT
  g.vertex_id,
  g.goal_code,
  g.display_name,
  g.status AS goal_status,
  g.target_value_jpy,
  g.target_date,
  g.attainment_bps,
  COUNT(DISTINCT ach.src_vid) AS action_count,
  SUM(CASE WHEN a.status = 'done' THEN 1 ELSE 0 END) AS actions_done,
  SUM(CASE WHEN a.status = 'in_progress' THEN 1 ELSE 0 END) AS actions_in_progress,
  SUM(CASE WHEN a.status = 'blocked' THEN 1 ELSE 0 END) AS actions_blocked
FROM vertex_goal g
LEFT JOIN edge_achieves ach ON ach.dst_vid = g.vertex_id
LEFT JOIN vertex_action a ON a.vertex_id = ach.src_vid
GROUP BY g.vertex_id, g.goal_code, g.display_name, g.status, g.target_value_jpy, g.target_date, g.attainment_bps
