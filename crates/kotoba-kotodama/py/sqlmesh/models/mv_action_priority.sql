-- Strategy action priority score: goal/risk impact × confidence / effort.
MODEL (
  name dev.mv_action_priority,
  kind FULL,
  dialect postgres,
  description 'Per-action priority score = (goals_served * 10 + risks_mitigated * 5) * confidence_bps / 10000 * 1000 / effort_days.',
  grain [vertex_id],
  tags [strategy, action, priority, planning]
);

SELECT
  a.vertex_id,
  a.action_code,
  a.display_name,
  a.status,
  a.phase,
  a.topo_level,
  COUNT(DISTINCT ach.dst_vid) AS goals_served,
  COUNT(DISTINCT mr.dst_vid) AS risks_mitigated,
  COALESCE(SUM(rc.monthly_reduction_jpy), 0) AS monthly_cost_reduction,
  COALESCE(SUM(gr.monthly_expected_jpy), 0) AS monthly_revenue,
  a.effort_days,
  a.confidence_bps,
  (
    (COUNT(DISTINCT ach.dst_vid) * 10 + COUNT(DISTINCT mr.dst_vid) * 5)
    * COALESCE(a.confidence_bps, 5000) / 10000
    * 1000 / GREATEST(a.effort_days, 1)
  ) AS priority_score
FROM vertex_action a
LEFT JOIN edge_achieves ach ON ach.src_vid = a.vertex_id
LEFT JOIN edge_mitigates_risk mr ON mr.src_vid = a.vertex_id
LEFT JOIN edge_reduces_cost rc ON rc.src_vid = a.vertex_id
LEFT JOIN edge_generates_revenue gr ON gr.src_vid = a.vertex_id
WHERE a.status IN ('planned', 'in_progress')
GROUP BY a.vertex_id, a.action_code, a.display_name, a.status, a.phase, a.topo_level, a.effort_days, a.confidence_bps
