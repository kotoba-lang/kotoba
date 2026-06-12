-- Game platform share: title count per platform.
MODEL (
  name dev.mv_game_platform_share,
  kind FULL,
  dialect postgres,
  description 'Per platform: distinct title count from edge_game_runs_on.',
  grain [platform_did],
  tags [game, platform, share, titles]
);

SELECT
  p.vertex_id AS platform_did,
  p.name AS platform_name,
  COUNT(DISTINCT ro.src_vid) AS title_count
FROM vertex_game_platform p
LEFT JOIN edge_game_runs_on ro ON ro.dst_vid = p.vertex_id
GROUP BY p.vertex_id, p.name
