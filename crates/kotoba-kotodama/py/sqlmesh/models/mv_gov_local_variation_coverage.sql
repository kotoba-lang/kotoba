-- Gov local variation coverage: procedure variant counts per jurisdiction.
MODEL (
  name dev.mv_gov_local_variation_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (country_iso3, admin1_name, locality_scope): variant, municipality, form, format, and language counts.',
  grain [country_iso3, admin1_name, locality_scope],
  tags [gov, local, variation, coverage]
);

SELECT
  country_iso3,
  admin1_name,
  locality_scope,
  COUNT(*) AS variant_count,
  COUNT(DISTINCT municipality_code) AS municipality_count,
  COUNT(DISTINCT form_key) AS form_count,
  COUNT(DISTINCT format_key) AS format_count,
  COUNT(DISTINCT language_tags) AS language_variant_count
FROM vertex_gov_procedure_variant
GROUP BY country_iso3, admin1_name, locality_scope
