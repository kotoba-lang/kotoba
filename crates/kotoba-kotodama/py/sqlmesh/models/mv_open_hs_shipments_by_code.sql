-- Open HS shipments by code: confirmed HS classifications per code and origin.
MODEL (
  name dev.mv_open_hs_shipments_by_code,
  kind FULL,
  dialect postgres,
  description 'Per (hs_code, country_of_origin): shipment count, total USD value, avg confidence, latest classified.',
  grain [hs_code, country_of_origin],
  tags [open_hs, shipment, classification]
);

SELECT
  hs_code,
  country_of_origin,
  COUNT(*) AS shipment_count,
  SUM(value_usd) AS total_value_usd,
  AVG(confidence) AS avg_confidence,
  MAX(classified_at) AS latest_classified_at
FROM vertex_open_hs_classification
WHERE status = 'confirmed'
GROUP BY hs_code, country_of_origin
