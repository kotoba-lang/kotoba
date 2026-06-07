-- Smishing URL risk: aggregated risk score and intel counts per URL.
MODEL (
  name dev.mv_smishing_url_risk,
  kind FULL,
  dialect postgres,
  description 'Per (url_id, analysis_id, domain): max score, IOC confirmed flag, geo intel count, takedown count.',
  grain [url_id, analysis_id],
  tags [smishing, url, risk, ioc]
);

SELECT
  u.url_id,
  u.analysis_id,
  u.domain,
  MAX(u.score) AS url_score,
  BOOL_OR(COALESCE(u.ioc_confirmed, FALSE)) OR COUNT(i.dst_vid) > 0 AS ioc_confirmed,
  COUNT(DISTINCT g.dst_vid) AS geo_intel_count,
  COUNT(DISTINCT td.dst_vid) AS takedown_count
FROM vertex_smishing_url_intel u
LEFT JOIN edge_smishing_url_geo g ON g.src_vid = u.vertex_id
LEFT JOIN edge_smishing_url_takedown td ON td.src_vid = u.vertex_id
LEFT JOIN edge_smishing_url_ioc i ON i.src_vid = u.vertex_id
GROUP BY u.url_id, u.analysis_id, u.domain
