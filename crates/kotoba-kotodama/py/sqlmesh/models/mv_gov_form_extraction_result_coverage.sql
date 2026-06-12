-- Gov form extraction result coverage: result counts per jurisdiction and procedure.
MODEL (
  name dev.mv_gov_form_extraction_result_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (country_iso3, admin1_name, base_procedure_key, locale, task_kind, extraction_status): result counts.',
  grain [country_iso3, admin1_name, base_procedure_key, locale, task_kind, extraction_status],
  tags [gov, form, extraction, result, coverage]
);

SELECT
  country_iso3,
  admin1_name,
  base_procedure_key,
  locale,
  task_kind,
  extraction_status,
  COUNT(*) AS result_count,
  COUNT(DISTINCT municipality_code) AS municipality_count,
  COUNT(DISTINCT procedure_variant_id) AS procedure_count
FROM vertex_gov_form_extraction_result
GROUP BY country_iso3, admin1_name, base_procedure_key, locale, task_kind, extraction_status
