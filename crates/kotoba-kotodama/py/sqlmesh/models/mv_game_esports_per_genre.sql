-- Game esports per genre: event count and total prize pool per genre.
MODEL (
  name dev.mv_game_esports_per_genre,
  kind FULL,
  dialect postgres,
  description 'Per genre: esports event count and total prize pool USD.',
  grain [genre_did],
  tags [game, esports, genre, prize]
);

SELECT
  g.vertex_id AS genre_did,
  g.name AS genre_name,
  COUNT(DISTINCT ev.vertex_id) AS esports_event_count,
  SUM(ev.prize_pool_usd) AS total_prize_pool_usd
FROM vertex_game_genre g
LEFT JOIN edge_game_has_genre hg ON hg.dst_vid = g.vertex_id
LEFT JOIN vertex_game_esports_event ev ON ev.title_did = hg.src_vid
GROUP BY g.vertex_id, g.name
