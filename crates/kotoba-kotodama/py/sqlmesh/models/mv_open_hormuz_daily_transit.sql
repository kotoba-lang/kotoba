-- Open Hormuz daily transit: passage counts per day, direction, and flag.
MODEL (
  name dev.mv_open_hormuz_daily_transit,
  kind FULL,
  dialect postgres,
  description 'Per (created_date, direction, flag): passage count, laden count, latest observed.',
  grain [created_date, direction, flag],
  tags [open_hormuz, transit, daily]
);

SELECT
  created_date,
  direction,
  flag,
  COUNT(*) AS passage_count,
  SUM(CASE WHEN laden THEN 1 ELSE 0 END) AS laden_count,
  MAX(observed_at) AS latest_observed
FROM vertex_open_hormuz_transit_passage
WHERE status = 'recorded'
GROUP BY created_date, direction, flag
