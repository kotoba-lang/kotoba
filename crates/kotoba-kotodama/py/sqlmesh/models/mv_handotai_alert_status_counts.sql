-- Handotai alert status counts: alert counts per enabled flag and tier.
MODEL (
  name dev.mv_handotai_alert_status_counts,
  kind FULL,
  dialect postgres,
  description 'Per (enabled, tier): alert count from vertex_handotai_alert.',
  grain [enabled, tier],
  tags [handotai, alert, status]
);

SELECT
  enabled,
  tier,
  COUNT(*) AS alert_count
FROM vertex_handotai_alert
GROUP BY enabled, tier
