-- Telecom capacity breach: forecast counts per scope/metric/model with breach prediction.
MODEL (
  name dev.mv_telecom_capacity_breach,
  kind FULL,
  dialect postgres,
  description 'Per (scope_kind, metric, model_kind, breach_predicted): forecast count.',
  grain [scope_kind, metric, model_kind, breach_predicted],
  tags [telecom, capacity, breach, forecast]
);

SELECT
  scope_kind,
  metric,
  model_kind,
  breach_predicted,
  COUNT(*) AS forecast_count
FROM vertex_telecom_capacity_forecast
GROUP BY scope_kind, metric, model_kind, breach_predicted
