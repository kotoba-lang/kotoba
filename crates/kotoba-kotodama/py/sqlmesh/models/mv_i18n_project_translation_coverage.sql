-- i18n project translation coverage: message count per project and language.
MODEL (
  name dev.mv_i18n_project_translation_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (project_id, lang): total_keys from project and message_count from translations.',
  grain [project_id, lang],
  tags [i18n, translation, coverage]
);

SELECT
  p.project_id,
  p.total_keys,
  t.lang,
  t.message_count
FROM vertex_i18n_project p
LEFT JOIN vertex_i18n_project_translation t ON t.project_id = p.project_id
