-- Game engine usage: distinct title count per engine.
MODEL (
  name dev.mv_game_engine_usage,
  kind FULL,
  dialect postgres,
  description 'Per engine: distinct title count from edge_game_uses_engine.',
  grain [engine_did],
  tags [game, engine, usage, titles]
);

SELECT
  e.vertex_id AS engine_did,
  e.name AS engine_name,
  COUNT(DISTINCT ue.src_vid) AS title_count
FROM vertex_game_engine e
LEFT JOIN edge_game_uses_engine ue ON ue.dst_vid = e.vertex_id
GROUP BY e.vertex_id, e.name
