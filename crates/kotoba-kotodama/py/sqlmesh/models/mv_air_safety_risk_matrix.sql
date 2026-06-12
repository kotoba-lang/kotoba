-- Airline SMS safety report count per category and severity.
MODEL (
  name dev.mv_air_safety_risk_matrix,
  kind FULL,
  dialect postgres,
  description 'Safety report count per category and severity from vertex_air_sms_safety_report.',
  grain [category, severity],
  tags [air, sms, safety, risk, matrix]
);

SELECT
  category,
  severity,
  COUNT(*) AS report_count
FROM vertex_air_sms_safety_report
GROUP BY category, severity
