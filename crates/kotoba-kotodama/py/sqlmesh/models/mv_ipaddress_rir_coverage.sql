-- IP address RIR coverage: range count per regional internet registry.
MODEL (
  name dev.mv_ipaddress_rir_coverage,
  kind FULL,
  dialect postgres,
  description 'Per rir: range count and latest updated_at from vertex_ipaddress_range.',
  grain [rir],
  tags [ipaddress, rir, coverage]
);

SELECT
  rir,
  COUNT(*) AS range_count,
  MAX(updated_at) AS latest_updated_at
FROM vertex_ipaddress_range
GROUP BY rir
