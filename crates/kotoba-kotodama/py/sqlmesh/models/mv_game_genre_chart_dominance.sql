-- Game genre chart dominance: top-20 charting titles per genre per source.
MODEL (
  name dev.mv_game_genre_chart_dominance,
  kind FULL,
  dialect postgres,
  description 'Per (genre_did, source): titles in top-20 chart, avg rank, top rank, last seen week.',
  grain [genre_did, source],
  tags [game, genre, chart, dominance]
);

SELECT
  g.dst_vid AS genre_did,
  s.source,
  COUNT(DISTINCT s.title_did) AS titles_in_chart,
  CAST(AVG(s.rank) AS DOUBLE PRECISION) AS avg_rank,
  MIN(s.rank) AS top_rank,
  MAX(s.week_start) AS last_seen_week
FROM vertex_game_chart_snapshot s
JOIN edge_game_has_genre g ON g.src_vid = s.title_did
WHERE s.title_did IS NOT NULL AND s.rank <= 20
GROUP BY g.dst_vid, s.source
