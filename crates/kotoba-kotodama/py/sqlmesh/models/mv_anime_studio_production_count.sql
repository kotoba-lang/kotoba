-- Anime studio production count: titles per studio with year range.
MODEL (
  name dev.mv_anime_studio_production_count,
  kind FULL,
  dialect postgres,
  description 'Per-studio anime title count with first/last year via edge_anime_produced_by.',
  grain [studio_did],
  tags [anime, studio, production, count]
);

SELECT
  s.vertex_id AS studio_did,
  s.name      AS studio_name,
  COUNT(DISTINCT t.vertex_id) AS title_count,
  MIN(t.year)                  AS first_year,
  MAX(t.year)                  AS last_year
FROM vertex_anime_studio s
LEFT JOIN edge_anime_produced_by p ON p.dst_vid = s.vertex_id
LEFT JOIN vertex_anime_title   t ON t.vertex_id = p.src_vid
GROUP BY s.vertex_id, s.name
