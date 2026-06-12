-- Anime source adaptation: title count per source kind (manga, novel, game, etc.).
MODEL (
  name dev.mv_anime_source_adaptation_ratio,
  kind FULL,
  dialect postgres,
  description 'Count of adapted anime titles per source kind from vertex_anime_source.',
  grain [source_kind],
  tags [anime, source, adaptation, ratio]
);

SELECT
  kind AS source_kind,
  COUNT(DISTINCT title_did) AS adapted_title_count
FROM vertex_anime_source
GROUP BY kind
