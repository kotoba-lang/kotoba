-- LDA model latest: converged LDA models per training corpus.
MODEL (
  name dev.mv_lda_model_latest,
  kind FULL,
  dialect postgres,
  description 'Per training_corpus: converged LDA model with k_topics, perplexity, and trained_at.',
  grain [training_corpus, model_vid],
  tags [lda, model, converged]
);

SELECT
  training_corpus,
  vertex_id AS model_vid,
  k_topics,
  perplexity,
  trained_at,
  status
FROM vertex_lda_model
WHERE status = 'converged'
