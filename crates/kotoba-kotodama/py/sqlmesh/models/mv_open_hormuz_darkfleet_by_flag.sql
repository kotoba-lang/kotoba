-- Open Hormuz dark fleet by flag: active darkfleet flags per current flag and risk tier.
MODEL (
  name dev.mv_open_hormuz_darkfleet_by_flag,
  kind FULL,
  dialect postgres,
  description 'Per (current_flag, risk_tier): flagged count, avg score, latest flagged_at.',
  grain [current_flag, risk_tier],
  tags [open_hormuz, darkfleet, flag]
);

SELECT
  current_flag,
  risk_tier,
  COUNT(*) AS flagged_count,
  AVG(risk_score) AS avg_score,
  MAX(flagged_at) AS latest_flagged
FROM vertex_open_hormuz_darkfleet_flag
WHERE status = 'active'
GROUP BY current_flag, risk_tier
