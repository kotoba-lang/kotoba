-- Bio gene expression summary: observation count and avg expression per gene-tissue-condition triple.
MODEL (
  name dev.mv_bio_gene_expression_summary,
  kind FULL,
  dialect postgres,
  description 'Per (gene, tissue, condition_label): observation count and average expression value from edge_bio_expressed_in.',
  grain [src_vid, dst_vid, condition_label],
  tags [bio, gene, expression, tissue, condition]
);

SELECT
  src_vid,
  dst_vid,
  condition_label,
  COUNT(*)::BIGINT AS observation_count,
  AVG(expression_value) AS avg_expression_value
FROM edge_bio_expressed_in
GROUP BY src_vid, dst_vid, condition_label
