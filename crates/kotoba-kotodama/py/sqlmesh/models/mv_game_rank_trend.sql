-- Game rank trend: charting statistics per title and chart source.
MODEL (
  name dev.mv_game_rank_trend,
  kind FULL,
  dialect postgres,
  description 'Per (title_did, source): weeks charted, avg rank, peak rank, best rise, worst fall, last charted week.',
  grain [title_did, source],
  tags [game, chart, rank, trend]
);

SELECT
  title_did,
  source,
  COUNT(*) AS weeks_charted,
  CAST(AVG(rank) AS DOUBLE PRECISION) AS avg_rank,
  MIN(rank) AS peak_rank,
  MAX(rank_delta) AS best_rise,
  MIN(rank_delta) AS worst_fall,
  MAX(week_start) AS last_charted_week
FROM vertex_game_chart_snapshot
WHERE title_did IS NOT NULL
GROUP BY title_did, source
