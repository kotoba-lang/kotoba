-- Open cyber SOC alert daily: triaged alert counts per severity and triage tier.
MODEL (
  name dev.mv_open_cyber_soc_alert_daily,
  kind FULL,
  dialect postgres,
  description 'Per (severity, triage_tier): alert count and latest fired_at for triaged SOC alerts.',
  grain [severity, triage_tier],
  tags [open_cyber, soc, alert]
);

SELECT
  severity,
  triage_tier,
  COUNT(*) AS alert_count,
  MAX(fired_at) AS latest_fired_at
FROM vertex_open_cyber_soc_alert
WHERE status = 'triaged'
GROUP BY severity, triage_tier
