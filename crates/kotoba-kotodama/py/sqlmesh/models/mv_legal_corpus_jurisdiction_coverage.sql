-- Legal corpus jurisdiction coverage: document count per jurisdiction and source.
MODEL (
  name dev.mv_legal_corpus_jurisdiction_coverage,
  kind FULL,
  dialect postgres,
  description 'Per (jurisdiction, source_id): document count and last fetch timestamp.',
  grain [jurisdiction, source_id],
  tags [legal, corpus, jurisdiction, coverage]
);

SELECT
  jurisdiction,
  source_id,
  COUNT(*) AS document_count,
  MAX(fetched_at) AS last_fetched_at
FROM vertex_legal_corpus_document
GROUP BY jurisdiction, source_id
