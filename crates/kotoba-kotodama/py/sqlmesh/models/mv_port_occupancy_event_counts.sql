-- Port occupancy event counts: per-(port, event_type) port call event count.
MODEL (
  name dev.mv_port_occupancy_event_counts,
  kind FULL,
  dialect postgres,
  description 'Per (port_id, event_type): event count from vertex_port_call_event.',
  grain [port_id, event_type],
  tags [port, occupancy, event]
);

SELECT
  port_id,
  event_type,
  COUNT(*) AS event_count
FROM vertex_port_call_event
GROUP BY port_id, event_type
