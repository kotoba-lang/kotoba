-- Strategy timeline: milestones joined with linked goals and supporting actions.
MODEL (
  name dev.mv_strategy_timeline,
  kind FULL,
  dialect postgres,
  description 'Per milestone × linked goal: target/actual dates, status, attainment, supporting action count.',
  grain [milestone_code],
  tags [strategy, milestone, goal, timeline]
);

SELECT
  m.milestone_code,
  m.display_name AS milestone,
  m.target_date,
  m.actual_date,
  m.status AS milestone_status,
  g.goal_code,
  g.display_name AS goal,
  g.attainment_bps,
  COUNT(DISTINCT ach.src_vid) AS supporting_actions
FROM vertex_milestone m
LEFT JOIN vertex_goal g ON g.vertex_id = m.linked_goal_id
LEFT JOIN edge_achieves ach ON ach.dst_vid = g.vertex_id
GROUP BY m.milestone_code, m.display_name, m.target_date, m.actual_date, m.status,
         g.goal_code, g.display_name, g.attainment_bps
