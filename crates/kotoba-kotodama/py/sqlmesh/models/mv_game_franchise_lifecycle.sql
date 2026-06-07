-- Game franchise lifecycle: title count and year span per franchise.
MODEL (
  name dev.mv_game_franchise_lifecycle,
  kind FULL,
  dialect postgres,
  description 'Per franchise: title count, first release year, and last release year.',
  grain [franchise_did],
  tags [game, franchise, lifecycle, titles]
);

SELECT
  f.vertex_id AS franchise_did,
  f.name AS franchise_name,
  COUNT(DISTINCT t.vertex_id) AS title_count,
  MIN(t.release_year) AS first_year,
  MAX(t.release_year) AS last_year
FROM vertex_game_franchise f
LEFT JOIN vertex_game_title t ON t.franchise_did = f.vertex_id
GROUP BY f.vertex_id, f.name
