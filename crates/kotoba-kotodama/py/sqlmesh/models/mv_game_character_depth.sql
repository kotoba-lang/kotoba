-- Game character depth: character count per title.
MODEL (
  name dev.mv_game_character_depth,
  kind FULL,
  dialect postgres,
  description 'Per title_did: character count from vertex_game_character.',
  grain [title_did],
  tags [game, character, depth, titles]
);

SELECT
  title_did,
  COUNT(*)::BIGINT AS character_count
FROM vertex_game_character
GROUP BY title_did
