-- Kuruma platform share: model count per platform.
MODEL (
  name dev.mv_kuruma_platform_share,
  kind FULL,
  dialect postgres,
  description 'Per platform: distinct model count from vertex_kuruma_model.',
  grain [platform_did],
  tags [kuruma, platform, share, models]
);

SELECT
  p.vertex_id AS platform_did,
  p.name AS platform_name,
  COUNT(DISTINCT m.vertex_id) AS model_count
FROM vertex_kuruma_platform p
LEFT JOIN vertex_kuruma_model m ON m.platform_did = p.vertex_id
GROUP BY p.vertex_id, p.name
