-- Smishing threat flow: URL and takedown counts per detected threat.
MODEL (
  name dev.mv_smishing_threat_flow,
  kind FULL,
  dialect postgres,
  description 'Per (analysis_id, sms_id): classification, score, URL count, takedown count, analyzed timestamp.',
  grain [analysis_id, sms_id],
  tags [smishing, threat, url, takedown]
);

SELECT
  t.analysis_id,
  t.sms_id,
  t.classification,
  t.score,
  COUNT(DISTINCT u.dst_vid) AS url_count,
  COUNT(DISTINCT td.dst_vid) AS takedown_count,
  MAX(t.created_at) AS analyzed_at
FROM vertex_smishing_threat_detection t
LEFT JOIN edge_smishing_threat_url u ON u.src_vid = t.vertex_id
LEFT JOIN edge_smishing_url_takedown td ON td.analysis_id = t.analysis_id
GROUP BY t.analysis_id, t.sms_id, t.classification, t.score
