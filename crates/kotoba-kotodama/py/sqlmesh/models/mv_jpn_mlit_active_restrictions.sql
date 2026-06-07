-- JPN MLIT active road restrictions: active road restriction counts per road and type.
MODEL (
  name dev.mv_jpn_mlit_active_restrictions,
  kind FULL,
  dialect postgres,
  description 'Per (road_code, restriction_type): restriction count, public notice flag, and latest effective_from.',
  grain [road_code, restriction_type],
  tags [jpn, mlit, road, restriction]
);

SELECT
  road_code,
  restriction_type,
  COUNT(*) AS restriction_count,
  BOOL_OR(require_public_notice) AS any_public_notice,
  MAX(effective_from) AS latest_effective
FROM vertex_jpn_mlit_road_restriction
WHERE status = 'active'
GROUP BY road_code, restriction_type
