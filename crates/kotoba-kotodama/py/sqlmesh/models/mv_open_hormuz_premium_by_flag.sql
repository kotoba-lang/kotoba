-- Open Hormuz war risk premium by flag: active war-risk premium quotes per flag/vessel/tier.
MODEL (
  name dev.mv_open_hormuz_premium_by_flag,
  kind FULL,
  dialect postgres,
  description 'Per (flag, vessel_type, rate_tier): quote count, avg premium bps, latest quoted.',
  grain [flag, vessel_type, rate_tier],
  tags [open_hormuz, war_risk, premium, insurance]
);

SELECT
  flag,
  vessel_type,
  rate_tier,
  COUNT(*) AS quote_count,
  AVG(premium_rate_bps) AS avg_premium_bps,
  MAX(quoted_at) AS latest_quoted
FROM vertex_open_hormuz_warrisk_premium
WHERE status = 'active'
GROUP BY flag, vessel_type, rate_tier
