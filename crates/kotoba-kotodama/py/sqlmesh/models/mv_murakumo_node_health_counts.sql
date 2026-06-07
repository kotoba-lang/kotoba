-- Murakumo node health counts: sample count and healthy count per node.
MODEL (
  name dev.mv_murakumo_node_health_counts,
  kind FULL,
  dialect postgres,
  description 'Per node_name: sample count, healthy count, and latest snapshot timestamp.',
  grain [node_name],
  tags [murakumo, node, health, monitoring]
);

SELECT
  node_name,
  COUNT(*) AS sample_count,
  COUNT(*) FILTER (WHERE healthy) AS healthy_count,
  MAX(snapshot_ts) AS latest_snapshot_ts
FROM edge_murakumo_fleet_node_health
GROUP BY node_name
