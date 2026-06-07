-- Open patent by jurisdiction: granted patent counts per jurisdiction and verification status.
MODEL (
  name dev.mv_open_patent_by_jurisdiction,
  kind FULL,
  dialect postgres,
  description 'Per (jurisdiction, verification): granted patent count, avg novelty, latest grant date.',
  grain [jurisdiction, verification],
  tags [open_patent, jurisdiction, granted]
);

SELECT
  jurisdiction,
  verification,
  COUNT(*) AS patent_count,
  AVG(novelty_score) AS avg_novelty,
  MAX(grant_date) AS latest_grant_date
FROM vertex_open_patent_patent
WHERE status = 'granted'
GROUP BY jurisdiction, verification
