-- Per-source agent: out-flow count and average control/bandwidth scores.
MODEL (
  name dev.mv_agent_information_flow_control,
  kind FULL,
  dialect postgres,
  description 'Outbound information flow count and avg control/bandwidth scores per source agent.',
  grain [src_vid],
  tags [agent, information, flow, control, bandwidth]
);

SELECT
  src_vid,
  COUNT(*)::BIGINT AS out_flow_count,
  AVG(control_score) AS avg_control_score,
  AVG(bandwidth_score) AS avg_bandwidth_score
FROM edge_agent_information_flows_to
GROUP BY src_vid
