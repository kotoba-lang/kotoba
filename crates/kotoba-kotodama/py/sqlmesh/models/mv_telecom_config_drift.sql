-- Telecom config drift: config snapshot counts per scope/source/drift status.
MODEL (
  name dev.mv_telecom_config_drift,
  kind FULL,
  dialect postgres,
  description 'Per (scope_kind, source_system, drift): snapshot count from vertex_telecom_config_snapshot.',
  grain [scope_kind, source_system, drift],
  tags [telecom, config, drift]
);

SELECT
  scope_kind,
  source_system,
  drift,
  COUNT(*) AS snapshot_count
FROM vertex_telecom_config_snapshot
GROUP BY scope_kind, source_system, drift
