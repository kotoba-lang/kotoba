-- Character count per anime title.
MODEL (
  name dev.mv_anime_character_depth,
  kind FULL,
  dialect postgres,
  description 'Count of characters per anime title_did from vertex_anime_character.',
  grain [title_did],
  tags [anime, character, depth, count]
);

SELECT title_did, COUNT(*)::BIGINT AS character_count
FROM vertex_anime_character
GROUP BY title_did
