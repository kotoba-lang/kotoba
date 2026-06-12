-- Protein taxon coverage: per-taxon protein count and KG link coverage.
MODEL (
  name dev.mv_protein_taxon_coverage,
  kind FULL,
  dialect postgres,
  description 'Per taxon_id: protein count, sum of kg_linked, first_at timestamp.',
  grain [taxon_id],
  tags [protein, taxon, coverage]
);

SELECT
  p.taxon_id,
  COUNT(*) AS protein_count,
  SUM(p.kg_linked) AS linked_count,
  MIN(p.created_at) AS first_at
FROM vertex_protein p
WHERE p.taxon_id IS NOT NULL
GROUP BY p.taxon_id
