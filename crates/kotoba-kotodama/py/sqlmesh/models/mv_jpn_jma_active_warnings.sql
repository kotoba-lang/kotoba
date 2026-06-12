-- JPN JMA active warnings: active weather warning counts per type and priority.
MODEL (
  name dev.mv_jpn_jma_active_warnings,
  kind FULL,
  dialect postgres,
  description 'Per (warning_type, priority): warning count, broadcast flag, and latest effective_from.',
  grain [warning_type, priority],
  tags [jpn, jma, weather, warning]
);

SELECT
  warning_type,
  priority,
  COUNT(*) AS warning_count,
  BOOL_OR(require_broadcast) AS any_broadcast,
  MAX(effective_from) AS latest_effective
FROM vertex_jpn_jma_weather_warning
WHERE status = 'active'
GROUP BY warning_type, priority
