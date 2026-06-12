-- Open navy advisory active: active navy advisory warning counts per authority/area/severity.
MODEL (
  name dev.mv_open_navy_advisory_active,
  kind FULL,
  dialect postgres,
  description 'Per (authority, area_code, severity): warning count, broadcast flag, latest effective.',
  grain [authority, area_code, severity],
  tags [open_navy, advisory, active]
);

SELECT
  authority,
  area_code,
  severity,
  COUNT(*) AS warning_count,
  BOOL_OR(require_broadcast) AS any_broadcast,
  MAX(effective_from) AS latest_effective
FROM vertex_open_navy_advisory_warning
WHERE status = 'active'
GROUP BY authority, area_code, severity
