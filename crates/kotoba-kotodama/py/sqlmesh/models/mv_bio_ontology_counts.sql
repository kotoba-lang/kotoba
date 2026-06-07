-- Bio ontology counts: vertex count per bio entity kind.
MODEL (
  name dev.mv_bio_ontology_counts,
  kind FULL,
  dialect postgres,
  description 'Per-kind vertex count across all bio entity tables (gene, protein, cell_type, tissue, organ, body_system, pathway).',
  grain [kind],
  tags [bio, ontology, counts, gene, protein, pathway]
);

SELECT 'gene'::VARCHAR AS kind, COUNT(*)::BIGINT AS vertex_count FROM vertex_bio_gene
UNION ALL SELECT 'protein'::VARCHAR, COUNT(*)::BIGINT FROM vertex_bio_protein
UNION ALL SELECT 'cell_type'::VARCHAR, COUNT(*)::BIGINT FROM vertex_bio_cell_type
UNION ALL SELECT 'tissue'::VARCHAR, COUNT(*)::BIGINT FROM vertex_bio_tissue
UNION ALL SELECT 'organ'::VARCHAR, COUNT(*)::BIGINT FROM vertex_bio_organ
UNION ALL SELECT 'body_system'::VARCHAR, COUNT(*)::BIGINT FROM vertex_bio_body_system
UNION ALL SELECT 'pathway'::VARCHAR, COUNT(*)::BIGINT FROM vertex_bio_pathway
