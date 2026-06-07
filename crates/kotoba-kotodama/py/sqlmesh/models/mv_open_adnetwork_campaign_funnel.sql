-- Open ad network campaign funnel: per-campaign impressions/clicks/conversions with CTR/CVR rates.
MODEL (
  name dev.mv_open_adnetwork_campaign_funnel,
  kind FULL,
  dialect postgres,
  description 'Per campaign: distinct impression/click/conversion counts, CTR/CVR percent, and total spend USD.',
  grain [campaign_id],
  tags [open_adnetwork, campaign, funnel, ctr, cvr]
);

SELECT
  i.campaign_id,
  COUNT(DISTINCT i.imp_id) AS impressions,
  COUNT(DISTINCT c.click_id) AS clicks,
  COUNT(DISTINCT cv.conv_id) AS conversions,
  CASE WHEN COUNT(DISTINCT i.imp_id) = 0 THEN 0.0
       ELSE COUNT(DISTINCT c.click_id)::DOUBLE PRECISION / COUNT(DISTINCT i.imp_id)::DOUBLE PRECISION * 100.0
  END AS ctr_pct,
  CASE WHEN COUNT(DISTINCT c.click_id) = 0 THEN 0.0
       ELSE COUNT(DISTINCT cv.conv_id)::DOUBLE PRECISION / COUNT(DISTINCT c.click_id)::DOUBLE PRECISION * 100.0
  END AS cvr_pct,
  SUM(i.cpm_usd) / 1000.0 AS total_spend_usd
FROM vertex_open_adnetwork_impression i
LEFT JOIN vertex_open_adnetwork_click c ON c.campaign_id = i.campaign_id
LEFT JOIN vertex_open_adnetwork_conversion cv ON cv.campaign_id = i.campaign_id
GROUP BY i.campaign_id
