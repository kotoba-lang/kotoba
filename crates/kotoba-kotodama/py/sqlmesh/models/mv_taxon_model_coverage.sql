-- Taxon model coverage: per-(domain, rank) taxon model coverage ratio.
MODEL (
  name dev.mv_taxon_model_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (domain_kind, taxon_rank): total/modelled/vegetation taxa and model coverage ratio.',
  grain [domain_kind, taxon_rank],
  tags [taxon, model, coverage, kami]
);

SELECT
  domain_kind,
  taxon_rank,
  COUNT(*) AS total_taxa,
  COUNT(kami_model_def_id) AS modelled_taxa,
  COUNT(kami_canopy_shape) AS vegetation_taxa,
  CAST(COUNT(kami_model_def_id) AS DOUBLE PRECISION) / CAST(COUNT(*) AS DOUBLE PRECISION) AS model_coverage_ratio
FROM vertex_scientific_taxon
GROUP BY domain_kind, taxon_rank
