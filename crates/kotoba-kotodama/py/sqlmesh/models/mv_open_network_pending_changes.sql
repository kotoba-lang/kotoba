-- Open network pending changes: pending/approved change requests per target vertex.
MODEL (
  name dev.mv_open_network_pending_changes,
  kind FULL,
  dialect postgres,
  description 'Per target_vertex_id: pending change count, worst risk, CAB approval flag, latest requested.',
  grain [target_vertex_id],
  tags [open_network, change, pending, risk]
);

SELECT
  target_vertex_id,
  COUNT(*) AS pending_change_count,
  MAX(risk) AS worst_risk,
  BOOL_OR(require_cab_approval) AS any_cab_approval,
  MAX(requested_at) AS latest_requested_at
FROM vertex_open_network_change
WHERE status IN ('requested', 'approved')
GROUP BY target_vertex_id
