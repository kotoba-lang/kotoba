-- Open ad network publisher daily KPI: flat projection of daily revenue snapshots.
MODEL (
  name dev.mv_open_adnetwork_publisher_daily_kpi,
  kind FULL,
  dialect postgres,
  description 'Per (publisher_did, date): impressions, clicks, conversions, revenue, RPM, CTR, CVR.',
  grain [publisher_did, date],
  tags [open_adnetwork, publisher, daily, kpi]
);

SELECT
  r.publisher_did,
  r.date,
  r.impressions,
  r.clicks,
  r.conversions,
  r.total_revenue_usd,
  r.rpm_usd,
  r.ctr_pct,
  r.cvr_pct
FROM vertex_open_adnetwork_revenue_snapshot r
