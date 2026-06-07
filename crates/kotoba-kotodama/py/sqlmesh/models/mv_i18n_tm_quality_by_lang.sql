-- i18n TM quality by language: translation memory entry counts and avg quality per lang pair.
MODEL (
  name dev.mv_i18n_tm_quality_by_lang,
  kind FULL,
  dialect postgres,
  description 'Per (source_lang, target_lang, source): entry count and avg quality from translation memory.',
  grain [source_lang, target_lang, source],
  tags [i18n, translation_memory, quality]
);

SELECT
  source_lang,
  target_lang,
  source,
  COUNT(*)::BIGINT AS entry_count,
  AVG(quality_score) AS avg_quality_score
FROM vertex_i18n_translation_memory
GROUP BY source_lang, target_lang, source
