-- Signal entropy: per-(signal_type, minute tick) entropy aggregates across 6 signal vertices.
MODEL (
  name dev.mv_signal_entropy,
  kind FULL,
  dialect postgres,
  description 'Per (signal_type, tick=minute): h_avg, h_max, eta, axis-weighted area_contrib union over 6 signal tables.',
  grain [signal_type, tick],
  tags [signal, entropy, aria]
);

SELECT
  signal_type,
  tick,
  AVG(entropy_h) AS h_avg,
  MAX(h_max) AS h_max,
  AVG(eta) AS eta,
  SUM(axis_weight * eta) AS area_contrib
FROM (
  SELECT 'attention' AS signal_type, DATE_TRUNC('minute', captured_at) AS tick, entropy_h, h_max, eta, axis_weight FROM vertex_signal_attention
  UNION ALL
  SELECT 'request', DATE_TRUNC('minute', captured_at), entropy_h, h_max, eta, axis_weight FROM vertex_signal_request
  UNION ALL
  SELECT 'money', DATE_TRUNC('minute', captured_at), entropy_h, h_max, eta, axis_weight FROM vertex_signal_money
  UNION ALL
  SELECT 'emotion', DATE_TRUNC('minute', captured_at), entropy_h, h_max, eta, axis_weight FROM vertex_signal_emotion
  UNION ALL
  SELECT 'market', DATE_TRUNC('minute', captured_at), entropy_h, h_max, eta, axis_weight FROM vertex_signal_market
  UNION ALL
  SELECT 'influence', DATE_TRUNC('minute', captured_at), entropy_h, h_max, eta, axis_weight FROM vertex_signal_influence
) t
GROUP BY signal_type, tick
