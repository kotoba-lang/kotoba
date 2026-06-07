-- Gov form extraction queue coverage: task counts per jurisdiction and procedure.
MODEL (
  name dev.mv_gov_form_extraction_queue_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (country_iso3, admin1_name, base_procedure_key, locale, task_kind, task_status): task and municipality counts.',
  grain [country_iso3, admin1_name, base_procedure_key, locale, task_kind, task_status],
  tags [gov, form, extraction, queue, coverage]
);

SELECT
  country_iso3,
  admin1_name,
  base_procedure_key,
  locale,
  task_kind,
  task_status,
  COUNT(*) AS task_count,
  COUNT(DISTINCT municipality_code) AS municipality_count,
  COUNT(DISTINCT procedure_variant_id) AS procedure_count
FROM vertex_gov_form_extraction_task
GROUP BY country_iso3, admin1_name, base_procedure_key, locale, task_kind, task_status
