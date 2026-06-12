-- Ossekai signal recent: per-target signal aggregates with sentiment and relevance.
MODEL (
  name dev.mv_ossekai_signal_recent,
  kind FULL,
  dialect postgres,
  description 'Per target_did: signal count, avg sentiment, avg relevance, last observed.',
  grain [target_did],
  tags [ossekai, signal, recent]
);

SELECT
  target_did,
  COUNT(*) AS signal_count,
  AVG(sentiment_score) AS avg_sentiment,
  AVG(relevance_score) AS avg_relevance,
  MAX(observed_at) AS last_observed_at
FROM vertex_ossekai_signal
GROUP BY target_did
